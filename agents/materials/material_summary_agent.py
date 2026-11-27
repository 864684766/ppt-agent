"""汇总已提炼资料；只处理要点，不读取文件或网页正文。"""

import asyncio
import json
import logging
from time import perf_counter

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_openai.chat_models.base import OpenAIConnectionError, OpenAITimeoutError
from openai import LengthFinishReasonError
from pydantic import ValidationError

from diagnostics.operation_logging import log_operation
from domain.materials.material_model_identifiers import MaterialModelIdentifiers
from models.materials.material_summary import MaterialInputPoint, MaterialMergedPoint, MaterialOutlineDraft, MaterialSummary
from models.outlines.presentation_outline import OutlineBullet, OutlineSlide, PresentationOutline

logger = logging.getLogger(__name__)


class MaterialSummaryOutputError(ValueError):
    """模型返回的结构或引用无效，调用方可根据已提炼资料编排草稿。"""


class MaterialSummaryAgent:
    """汇总资料并按需形成大纲；模型资源由调用方管理。"""

    def __init__(self, *, model: BaseChatModel, prompt: str, retry_prompt: str, output_tokens: int = 4096,
                 timeout_seconds: float = 120, batch_concurrency: int = 1) -> None:
        """注入正常和超限重试提示词；模型资源由调用方持有。"""
        if output_tokens < 1 or timeout_seconds <= 0 or not 1 <= batch_concurrency <= 3 or not retry_prompt.strip():
            raise ValueError("输出预算和超时须大于零，并发数须为1至3，重试提示词不能为空。")
        self._model = model.with_structured_output(MaterialSummary, method="json_mode")
        self._outline_model = model.with_structured_output(MaterialOutlineDraft, method="json_mode")
        # 模型只安排主题和编号，正文由程序从已提炼要点填入。
        self._prompt, _, self._final_prompt = prompt.partition("\n## 最终资料汇总与大纲\n")
        self._final_retry_prompt = retry_prompt
        # 以紧凑 JSON 的字符数估算输入规模，避免少量短内容被拆成很多批。
        self._batch_char_budget = min(12_000, output_tokens)
        self._timeout_seconds = timeout_seconds
        self._final_call_timeout = min(60, timeout_seconds)
        self._batch_concurrency = batch_concurrency

    @log_operation("agent.material_summary")
    async def summarize(self, *, question: str, points: list[MaterialInputPoint],
                        final: bool = False, target_count: int = 5,
                        use_current: bool = False, include_outline: bool = True) -> MaterialSummary:
        """最终汇总同时生成可选大纲；大量要点仍需先分批处理。"""
        if not question.strip() or not points:
            raise ValueError("用户问题和资料要点不能为空。")
        # 内部使用短编号减少模型输入和输出；返回前恢复原编号，来源追溯不变。
        identifiers = MaterialModelIdentifiers(points)
        data = identifiers.model_data()
        ids = set(identifiers.source_map())
        if final and not self._final_prompt.strip():
            raise ValueError("缺少最终汇总提示词。")
        # 聊天汇总的总时限覆盖分批、拆分和重试，避免逐批等待数分钟后才交付。
        summary_timeout = self._final_call_timeout * 2 if final else self._timeout_seconds * 4
        async with asyncio.timeout(summary_timeout):
            batches = self._split_batches(data)
            if len(batches) > 1:
                data = await self._summarize_batches(question, batches, ids)
            if not data:
                return MaterialSummary(points=[], issues=[])
            referenced = dict.fromkeys(point_id for item in data for point_id in item["point_ids"])
            source_map = identifiers.source_map(referenced)
            result = await self._call(question, data, ids, final=final, source_map=source_map,
                                      target_count=target_count, use_current=use_current, include_outline=include_outline)
            if final and include_outline and not result.outline and (use_current or not result.issues):
                raise MaterialSummaryOutputError("模型未返回大纲或资料缺口。")
            if final:
                logger.info("event=material_final_result points=%d slides=%d issues=%d", len(result.points),
                            len(result.outline.slides) if result.outline else 0, len(result.issues))
            return identifiers.restore_summary(result)

    def _split_batches(self, data: list[dict]) -> list[list[dict]]:
        """用紧凑 JSON 的字符数分批，并保留要点顺序。"""
        batches: list[list[dict]] = [[]]
        size = 2  # JSON 数组括号。
        for item in data:
            cost = len(json.dumps(item, ensure_ascii=False, separators=(",", ":"))) + 1
            if batches[-1] and size + cost > self._batch_char_budget:
                batches.append([])
                size = 2
            batches[-1].append(item)
            size += cost
        return batches

    async def _summarize_batches(self, question: str, batches: list[list[dict]], ids: set[str]) -> list[dict]:
        """限制并发并保持批次顺序；失败时取消并等待其他批次，避免后台继续消耗。"""
        logger.info("event=material_batches_start batch_count=%d point_count=%d concurrency=%d",
                    len(batches), sum(map(len, batches)), self._batch_concurrency)
        semaphore = asyncio.Semaphore(self._batch_concurrency)

        async def process(index: int, batch: list[dict]) -> list[dict]:
            async with semaphore:
                started = perf_counter()
                logger.info("event=material_batch_start batch=%d total=%d points=%d", index, len(batches), len(batch))
                result = await self._batch(question, batch, ids)
                logger.info("event=material_batch_completed batch=%d total=%d points=%d duration_ms=%.2f",
                            index, len(batches), len(result), (perf_counter() - started) * 1000)
                return result

        tasks = [asyncio.create_task(process(index, batch)) for index, batch in enumerate(batches, 1)]
        try:
            results = await asyncio.gather(*tasks)
        except BaseException:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        return [point for batch in results for point in batch]

    async def _batch(self, question: str, data: list[dict], ids: set[str]) -> list[dict]:
        """单批超限时递归二分；单条或最终整体汇总超限由调用方处理。"""
        try:
            limit = max(1, min(8, len(data) // 2))
            result = await self._call(question, data, ids, point_limit=limit)
            if len(result.points) > limit:
                # 模型未按要求压缩时保留原始证据，避免按输出顺序截掉事实。
                logger.warning("event=material_batch_not_compacted input_points=%d output_points=%d",
                               len(data), len(result.points))
                return data
            return [point.model_dump() for point in result.points]
        except LengthFinishReasonError:
            if len(data) <= 1:
                raise
            middle = len(data) // 2
            return await self._batch(question, data[:middle], ids) + await self._batch(question, data[middle:], ids)

    async def _call(self, question: str, data: list[dict], ids: set[str], *, final: bool = False,
                    source_map: dict | None = None, target_count: int = 5, use_current: bool = False,
                    include_outline: bool = True, point_limit: int | None = None) -> MaterialSummary:
        """选择模型输出结构并校验结果确实引用本次发送的要点。"""
        allowed = {point_id for item in data for point_id in item["point_ids"]} & ids
        make_outline = final and include_outline
        instruction = self._final_prompt if make_outline else self._prompt
        if final:
            instruction += "\n生成设置与来源：" + json.dumps(
                {"target_count": target_count, "sources": source_map, "use_current": use_current},
                ensure_ascii=False, separators=(",", ":"))
        if point_limit is not None:
            instruction += f"\n本批最多返回{point_limit}条精简要点，保留主题所需的事实和来源编号。"
        if make_outline:
            data = [{"key": f"k{index}", **item} for index, item in enumerate(data, 1)]
        message = instruction + "\n用户要求：" + question + "\n资料要点：" + json.dumps(
            data, ensure_ascii=False, separators=(",", ":"))
        model = self._outline_model if make_outline else self._model
        if final:
            logger.info("event=material_final_start input_points=%d input_chars=%d include_outline=%s target_sources=%d",
                        len(data), len(message), make_outline, target_count)
        try:
            response = await self._invoke_with_retry(model, message, retry_connection=not final)
        except LengthFinishReasonError:
            if not final or make_outline:
                raise
            logger.warning("event=material_final_length_retry")
            response = await self._invoke_with_retry(model, message + "\n" + self._final_retry_prompt, retry_connection=False)
        try:
            result = self._to_summary(response, data)
        except ValidationError as error:
            raise MaterialSummaryOutputError("模型返回的大纲结构无效。") from error
        if (any(not set(point.point_ids).issubset(allowed) for point in result.points)
                or any(not set(issue.point_ids).issubset(allowed) for issue in result.issues)):
            raise MaterialSummaryOutputError("汇总或大纲引用了不存在的要点编号。")
        return result

    @staticmethod
    def _to_summary(response: object, data: list[dict]) -> MaterialSummary:
        """把模型选择的页标题和编号转换成含原有要点正文的大纲。"""
        if isinstance(response, MaterialOutlineDraft) and response.sections:
            # 批次合并后，同一输入编号可能支持多个要点。建立独立编号见 _call。
            bullets = {item["key"]: OutlineBullet(content=item["content"], point_ids=item["point_ids"]) for item in data}
            slides = []
            for section in response.sections:
                if any(key not in bullets for key in section.keys):
                    raise MaterialSummaryOutputError("大纲引用了不存在的要点编号。")
                slides.append(OutlineSlide(role="content", title=section.title,
                    bullets=[bullets[key].model_copy(deep=True) for key in dict.fromkeys(section.keys)]))
            outline = PresentationOutline(title=response.title, slides=slides)
            points = [MaterialMergedPoint(content=bullet.content, point_ids=bullet.point_ids.copy())
                      for slide in slides for bullet in slide.bullets]
            return MaterialSummary(points=points, issues=response.issues, outline=outline)
        if isinstance(response, (MaterialSummary, MaterialOutlineDraft)):
            return MaterialSummary(points=response.points, issues=response.issues)
        raise MaterialSummaryOutputError("模型未返回有效的资料汇总。")

    async def _invoke_with_retry(self, model: Runnable, message: str, *, retry_connection: bool) -> object:
        """中间批次遇到超时或连接失败可重试一次，最终生成由调用方决定如何交付。"""
        for attempt in range(1 + int(retry_connection)):
            try:
                deadline = self._timeout_seconds if retry_connection else self._final_call_timeout
                async with asyncio.timeout(deadline):
                    return await model.ainvoke(message)
            except (OutputParserException, ValidationError) as error:
                raise MaterialSummaryOutputError("模型返回的汇总格式无效。") from error
            except (TimeoutError, OpenAITimeoutError, OpenAIConnectionError) as error:
                if attempt or not retry_connection:
                    raise
                # 只重试当前批次；已完成的批次仍保存在本轮任务中。
                kind = "connection" if isinstance(error, OpenAIConnectionError) else "timeout"
                logger.warning("event=material_model_retry reason=%s max_retries=1", kind)
        raise RuntimeError("模型调用未返回结果。")
