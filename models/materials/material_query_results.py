"""资料查询的内部结果：目录分页与正文检索，不是工具的公开返回字典。

这些结果保留内部资料或正文块，供业务查询与工具适配之间传递。
工具适配器另行选择允许公开的字段，避免把 project_id 等内部信息交给模型。
本模块仅依赖标准库数据类型和业务实体，不导入 Pydantic 或 Agent 框架。
"""

from dataclasses import dataclass

from models.materials.material_fragment import MaterialFragment
from models.materials.material_source import MaterialSummary


@dataclass(frozen=True, slots=True)
class MaterialPage:
    """筛选后的目录页；total 为筛选后总数，next_offset 为下一页偏移。"""

    items: tuple[MaterialSummary, ...]
    total: int
    next_offset: int | None


@dataclass(frozen=True, slots=True)
class MaterialSearchMatch:
    """一个命中块及截取文本；matched_queries针对完整块，不只是截取文本。"""

    fragment: MaterialFragment
    matched_queries: tuple[str, ...]
    text: str
    text_truncated: bool


@dataclass(frozen=True, slots=True)
class MaterialSearchResult:
    """total_matches是命中块总数，truncated仅表示结果条数被截断。"""

    matches: tuple[MaterialSearchMatch, ...]
    total_matches: int
    truncated: bool
