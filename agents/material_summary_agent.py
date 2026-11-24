"""提取出的资料要点汇总；当前输入仍使用网页候选契约。"""
import json
import logging
from langchain_core.language_models import BaseChatModel
from openai import LengthFinishReasonError
from diagnostics.operation_logging import log_operation
from models.web.web_research_summary import WebResearchSummary

logger = logging.getLogger(__name__)


class MaterialSummaryAgent:
    """合并已提炼要点并核对候选编号；目前仅接入网页资料。"""

    def __init__(self, *, model: BaseChatModel, prompt: str, summary_prompt: str,
                 output_tokens: int = 4096) -> None:
        """单次输出预算由调用方注入；预算只是分批估算依据。"""
        if output_tokens < 1:
            raise ValueError("输出预算必须大于零。")
        self._summary_model = model.with_structured_output(WebResearchSummary, method="json_mode")
        self._prompt = prompt
        self._summary_prompt = summary_prompt
        # 每条预留约1024输出token（包括推理、JSON等），只是保守经验值。
        # 此值不能保证模型实际输出不超限，超限时仍需拆分或中断。
        self._batch_points = min(20, max(1, output_tokens // 1024))

    @log_operation("agent.web_research_summary")
    async def summarize(self, *, question: str, extractions: list[dict]) -> WebResearchSummary:
        """合并单页要点并检查缺口；只接受本次实际提炼过的来源编号。"""
        if not extractions:
            raise ValueError("没有可整理的网页提炼结果。")
        # 按要点拆分而非按网页拆分：单篇网页也可能包含很多要点。
        records = [{**item, "points": [point]} for item in extractions for point in item["points"]]
        if not records:
            return await self._summarize_batch(question, extractions)
        batches = [records[i:i + self._batch_points] for i in range(0, len(records), self._batch_points)]
        if len(batches) == 1:
            return await self._summarize_with_split(question, batches[0])
        partials = []
        for batch in batches:
            partials.append(await self._summarize_with_split(question, batch))
        # 最终检查需要同时看到各批结果，才能判断跨批重复与整体缺口。
        # 如果最终步骤超限，向上报告中断；原始提炼记录仍保存在工作流状态中。
        combined = [{**item, "points": []} for item in extractions]
        merged_points = [point.model_dump() for partial in partials for point in partial.points]
        for record in combined:
            record["points"] = [point for point in merged_points if record["candidate_id"] in point["candidate_ids"]]
        logger.info("event=research_summary_batches batch_count=%d point_count=%d", len(batches), len(records))
        return await self._summarize_batch(question, combined)

    async def _summarize_with_split(self, question: str, records: list[dict]) -> WebResearchSummary:
        """输出超限时二分重试；单条仍失败则交由工作流报告中断。"""
        try:
            return await self._summarize_batch(question, records)
        except LengthFinishReasonError:
            if len(records) <= 1:
                raise
            logger.warning("event=research_summary_batch_split point_count=%d", len(records))
            middle = len(records) // 2
            left = await self._summarize_with_split(question, records[:middle])
            right = await self._summarize_with_split(question, records[middle:])
            # 拆分结果只作为中间结果；整体缺口必须在最终汇总时重新判断。
            points = [point.model_dump() for point in left.points + right.points]
            # 同一来源被拆成多条记录时只生成一个来源项，避免重复放大要点。
            sources = {record["candidate_id"]: record for record in records}
            combined = [{**record, "points": [point for point in points
                         if source_id in point["candidate_ids"]]}
                        for source_id, record in sources.items()]
            return await self._summarize_batch(question, combined)

    async def _summarize_batch(self, question: str, extractions: list[dict]) -> WebResearchSummary:
        """调用一次模型并验证来源；不把模型编造的编号交给下游。"""
        result = await self._summary_model.ainvoke(self._prompt + "\n" + self._summary_prompt + "\n用户要求：" + question
                                                     + "\n单页提炼：" + json.dumps(extractions, ensure_ascii=False))
        if not isinstance(result, WebResearchSummary):
            raise ValueError("模型未返回有效的网页整理结果。")
        valid_ids = {item["candidate_id"] for item in extractions}
        point_ids = {item["candidate_id"] for item in extractions if item["points"]}
        if any(not set(point.candidate_ids).issubset(point_ids) for point in result.points):
            raise ValueError("模型要点引用了未提炼的网页编号。")
        if any(not set(issue.candidate_ids).issubset(valid_ids) for issue in result.issues):
            raise ValueError("模型问题引用了未提炼的网页编号。")
        # 跟进链接由单页提炼阶段核对；汇总模型不能再生成新链接。
        result.follow_links = []
        return result
