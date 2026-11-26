"""将网页和文件提炼结果转换为通用汇总输入；不调用模型或登记资料。"""

from collections.abc import Mapping, Sequence
from typing import Any

from models.materials.file_extraction import FileExtraction
from models.materials.material_summary import MaterialInputPoint, MaterialReference


def file_summary_points(*, extraction: FileExtraction, source_id: str) -> list[MaterialInputPoint]:
    """转换单份已完成文件；source_id由调用方保证本次唯一，块号只在该文件内有效。"""
    if extraction.status != "completed":
        raise ValueError("文件提炼尚未完成，不能当作完整资料汇总。")
    if not source_id.strip():
        raise ValueError("文件来源编号不能为空。")
    return [MaterialInputPoint(point_id=f"file:{source_id}:{index}", content=point.content,
            references=[MaterialReference(kind="file", source_id=source_id, block_ids=point.block_ids)])
            for index, point in enumerate(extraction.points, 1)]


def web_summary_points(*, extractions: Sequence[Mapping[str, Any]]) -> list[MaterialInputPoint]:
    """转换网页单页要点；检查每条要点只引用对应的实际网页候选编号。"""
    result = []
    seen = set()
    for item in extractions:
        source_id = item["candidate_id"]
        if not source_id or source_id in seen:
            raise ValueError("网页候选编号不能为空或重复。")
        seen.add(source_id)
        for index, point in enumerate(item["points"], 1):
            if set(point["candidate_ids"]) != {source_id}:
                raise ValueError("网页要点来源与对应候选不一致。")
            result.append(MaterialInputPoint(point_id=f"web:{source_id}:{index}", content=point["content"],
                          references=[MaterialReference(kind="web", source_id=source_id)]))
    return result
