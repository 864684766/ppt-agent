"""资料目录查询规则：范围隔离、过滤、排序与分页，仅依赖标准库。

数据定义放 models/materials/material_summary.py；这里不关心数据来自数据库、上传还是测试样本。
"""

from collections.abc import Sequence
from typing import Literal

from models.materials.material_page import MaterialPage
from models.materials.material_summary import MaterialSummary


def list_project_materials(
    materials: Sequence[MaterialSummary],
    *,
    project_id: str,
    origin: Literal["all", "uploaded", "web"] = "all",
    name_contains: str = "",
    offset: int = 0,
    limit: int = 20,
) -> MaterialPage:
    """在调用方提供的目录快照中筛选和分页，不改变原数据。

    先限制项目，再按来源和名称筛选，按 source_id 排序后分页。
    name_contains 使用不区分大小写的字面子串，不是正则表达式。
    offset 从 0 开始；超过结果数量返回空页。非法参数抛 ValueError。
    调用方拥有快照；若要在多次调用之间看到新增资料，需重新提供快照。
    """
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("project_id 必须为非空字符串。")
    if origin not in ("all", "uploaded", "web"):
        raise ValueError("origin 必须为 all、uploaded 或 web。")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset 必须为非负整数。")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit 必须为 1–100 的整数。")
    if not isinstance(name_contains, str):
        raise ValueError("name_contains 必须为字符串。")

    keyword = name_contains.strip().casefold()
    # 项目范围来自宿主，不允许模型通过过滤参数访问其他项目。
    scoped = [item for item in materials if item.project_id == project_id]
    if len({item.source_id for item in scoped}) != len(scoped):
        raise ValueError("同一目录快照内 source_id 不得重复。")
    # 来源过滤和名称过滤共同生效；空关键词会匹配所有名称。
    # casefold 比 lower 更适合做不区分大小写的 Unicode 文本比较。
    matched = [
        item for item in scoped
        if (origin == "all" or item.origin == origin)
        and keyword in item.name.casefold()
    ]
    # 固定排序保证同一快照翻页时顺序一致；不改变调用方的原序列。
    matched.sort(key=lambda item: item.source_id)
    total = len(matched)
    # end_offset 是切片右端点，不包含该位置；超出长度时 Python 自动截断。
    end_offset = offset + limit
    next_offset = end_offset if end_offset < total else None
    return MaterialPage(tuple(matched[offset:end_offset]), total, next_offset)
