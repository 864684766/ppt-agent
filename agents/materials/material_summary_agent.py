"""汇总已提炼资料；只处理要点，不读取文件或网页正文。"""

import json

from langchain_core.language_models import BaseChatModel
from openai import LengthFinishReasonError

from diagnostics.operation_logging import log_operation
from models.materials.material_summary import MaterialInputPoint, MaterialSummary


class MaterialSummaryAgent:
    """根据用户问题合并要点并检查来源引用；模型资源由调用方管理。"""

    def __init__(self, *, model: BaseChatModel, prompt: str, output_tokens: int = 4096) -> None:
        if output_tokens < 1:
            raise ValueError("输出预算必须大于零。")
        self._model = model.with_structured_output(MaterialSummary, method="json_mode")
        self._prompt = prompt
        self._batch_size = min(20, max(1, output_tokens // 1024))

    @log_operation("agent.material_summary")
    async def summarize(self, *, question: str, points: list[MaterialInputPoint]) -> MaterialSummary:
        """返回合并结果；重复编号、模型引用不存在的要点或模型错误均明确失败。"""
        if not question.strip() or not points:
            raise ValueError("用户问题和资料要点不能为空。")
        ids = {point.point_id for point in points}
        if len(ids) != len(points):
            raise ValueError("资料要点编号必须在本次汇总中唯一。")
        data = [{"point_ids": [point.point_id], "content": point.content} for point in points]
        if len(data) <= self._batch_size:
            return await self._call(question, data, ids)
        # 中间结果继续引用原要点编号；最后一次整体检查跨批重复和缺口。
        partials = []
        for index in range(0, len(data), self._batch_size):
            partials.extend(await self._batch(question, data[index:index + self._batch_size], ids))
        return await self._call(question, partials, ids)

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

    async def _call(self, question: str, data: list[dict], ids: set[str]) -> MaterialSummary:
        """发送要点而非正文；仅允许引用本次实际发送的数据所含编号。"""
        allowed = {point_id for item in data for point_id in item["point_ids"]}
        result = await self._model.ainvoke(self._prompt + "\n用户要求：" + question + "\n资料要点：" + json.dumps(data, ensure_ascii=False))
        if not isinstance(result, MaterialSummary):
            raise ValueError("模型未返回有效的资料汇总。")
        if any(not set(item.point_ids).issubset(allowed & ids) for item in [*result.points, *result.issues]):
            raise ValueError("汇总引用了不存在的要点编号。")
        return result
