"""提取出的资料要点汇总；当前输入仍使用网页候选契约。"""
import json
from langchain_core.language_models import BaseChatModel
from diagnostics.operation_logging import log_operation
from models.web.web_research_summary import WebResearchSummary


class MaterialSummaryAgent:
    """合并已提炼要点并核对候选编号；目前仅接入网页资料。"""

    def __init__(self, *, model: BaseChatModel, prompt: str, summary_prompt: str) -> None:
        self._summary_model = model.with_structured_output(WebResearchSummary, method="json_mode")
        self._prompt = prompt
        self._summary_prompt = summary_prompt

    @log_operation("agent.web_research_summary")
    async def summarize(self, *, question: str, extractions: list[dict]) -> WebResearchSummary:
        """合并单页要点并检查缺口；只接受本次实际提炼过的来源编号。"""
        if not extractions:
            raise ValueError("没有可整理的网页提炼结果。")
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
