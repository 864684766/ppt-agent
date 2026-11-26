"""汇总已提炼资料；只处理要点，不读取文件或网页正文。"""

import json
import logging
import asyncio
from time import perf_counter

from langchain_core.language_models import BaseChatModel
from openai import LengthFinishReasonError

from diagnostics.operation_logging import log_operation
from models.materials.material_summary import MaterialInputPoint, MaterialSummary

logger = logging.getLogger(__name__)

class MaterialSummaryAgent:
    """汇总资料并按需形成大纲；模型资源由调用方管理。"""

    def __init__(self, *, model: BaseChatModel, prompt: str, retry_prompt: str, output_tokens: int = 4096,
                 timeout_seconds: float = 120, batch_concurrency: int = 1) -> None:
        """注入正常和超限重试提示词；模型资源由调用方持有。"""
        if output_tokens < 1 or timeout_seconds <= 0 or not 1 <= batch_concurrency <= 3 or not retry_prompt.strip():
            raise ValueError("输出预算和超时须大于零，并发数须为1至3，重试提示词不能为空。")
        self._model = model.with_structured_output(MaterialSummary, method="json_mode")
        # 中间批次只汇总；最终调用使用同一模型同时返回汇总、问题和大纲。
        self._prompt, _, self._final_prompt = prompt.partition("\n## 最终资料汇总与大纲\n")
        self._final_retry_prompt = retry_prompt
        self._batch_size = min(20, max(1, output_tokens // 1024))
        self._timeout_seconds = timeout_seconds
        self._batch_concurrency = batch_concurrency

    @log_operation("agent.material_summary")
    async def summarize(self, *, question: str, points: list[MaterialInputPoint],
                        final: bool = False, target_count: int = 5,
                        use_current: bool = False, include_outline: bool = True) -> MaterialSummary:
        """最终汇总同时生成可选大纲；大量要点仍需先分批处理。"""
        if not question.strip() or not points:
            raise ValueError("用户问题和资料要点不能为空。")
        ids = {point.point_id for point in points}
        if len(ids) != len(points):
            raise ValueError("资料要点编号必须在本次汇总中唯一。")
        data = [{"point_ids": [point.point_id], "content": point.content} for point in points]
        if final and not self._final_prompt.strip():
            raise ValueError("缺少最终汇总提示词。")
        # 总预算覆盖所有批次、拆分和重试，防止流持续输出导致单次任务长时间不结束。
        async with asyncio.timeout(self._timeout_seconds * 4):
            if len(data) > self._batch_size:
                data = await self._summarize_batches(question, data, ids)
            source_map = {point.point_id: [f"{ref.kind}:{ref.source_id}" for ref in point.references] for point in points}
            return await self._call(question, data, ids, final=final, source_map=source_map,
                                    target_count=target_count, use_current=use_current, include_outline=include_outline)

    async def _summarize_batches(self, question: str, data: list[dict], ids: set[str]) -> list[dict]:
        """限制并发并保持批次顺序；失败时取消并等待其他批次，避免后台继续消耗。"""
        batches = [data[index:index + self._batch_size] for index in range(0, len(data), self._batch_size)]
        logger.info("event=material_batches_start batch_count=%d point_count=%d concurrency=%d",
                    len(batches), len(data), self._batch_concurrency)
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
            result = await self._call(question, data, ids)
            return [point.model_dump() for point in result.points]
        except LengthFinishReasonError:
            if len(data) <= 1:
                raise
            middle = len(data) // 2
            return await self._batch(question, data[:middle], ids) + await self._batch(question, data[middle:], ids)

    async def _call(self, question: str, data: list[dict], ids: set[str], *, final: bool = False,
                    source_map: dict | None = None, target_count: int = 5, use_current: bool = False,
                    include_outline: bool = True) -> MaterialSummary:
        """发送要点而非正文；仅允许引用本次实际发送的数据所含编号。"""
        allowed = {point_id for item in data for point_id in item["point_ids"]}
        instruction = self._prompt
        if final:
            instruction += "\n" + self._final_prompt + "\n来源目标与对应关系：" + json.dumps(
                {"target_count": target_count, "sources": source_map, "use_current": use_current,
                 "include_outline": include_outline}, ensure_ascii=False)
        message = instruction + "\n用户要求：" + question + "\n资料要点：" + json.dumps(data, ensure_ascii=False)
        try:
            async with asyncio.timeout(self._timeout_seconds):
                result = await self._model.ainvoke(message)
        except LengthFinishReasonError:
            if not final or not self._final_retry_prompt.strip():
                raise
            logger.warning("event=material_final_length_retry")
            async with asyncio.timeout(self._timeout_seconds):
                result = await self._model.ainvoke(message + "\n" + self._final_retry_prompt)
        if not isinstance(result, MaterialSummary):
            raise ValueError("模型未返回有效的资料汇总。")
        if (any(not set(item.point_ids).issubset(allowed & ids) for item in result.points)
                or any(not set(item.point_ids).issubset(allowed & ids) for item in result.issues)):
            raise ValueError("汇总引用了不存在的要点编号。")
        summarized = {point_id for point in result.points for point_id in point.point_ids}
        if final and result.outline and any(not set(bullet.point_ids).issubset(summarized)
                                            for slide in result.outline.slides for bullet in slide.bullets):
            raise ValueError("大纲引用了未进入汇总的资料要点编号。")
        if not final:
            result.outline = None
        return result
