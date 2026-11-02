"""目录查询与正文检索共享的跨记录业务校验。

只依赖资料实体与标准库，不依赖目录查询、正文检索或 Agent 框架。
单份实体的字段校验仍在 validators/materials/；这里处理项目范围和多记录唯一性。
"""

from collections.abc import Sequence

from models.materials.material_source import MaterialSummary


def validate_material_catalog(
    *, project_id: str, materials: Sequence[MaterialSummary],
) -> None:
    """校验目录的项目编号及项目内来源编号唯一性。

    project_id 由宿主绑定；其他项目的资料不参与重复编号检查。
    校验通过时正常结束，返回 None；不合法时抛出 ValueError。
    本函数不执行名称过滤、排序或分页，也不创建查询结果。
    这是跨记录的业务约束，供目录查询和正文检索共同使用；
    单份资料的字段合法性仍由 MaterialSummary 构造时校验。
    """
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("project_id 必须为非空字符串。")

    # 不同项目允许使用相同 source_id；只记录当前项目已经出现的编号。
    seen_source_ids: set[str] = set()
    for item in materials:
        if item.project_id != project_id:
            continue
        if item.source_id in seen_source_ids:
            raise ValueError("同一目录快照内 source_id 不得重复。")
        seen_source_ids.add(item.source_id)
