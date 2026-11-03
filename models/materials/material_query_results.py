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

    # 本次目录页的内部资料对象，含project_id，工具需挑选公开字段。
    items: tuple[MaterialSummary, ...]
    # 应用筛选条件后的资料总条数，不是本页条数。
    total: int
    # 下一页跳过的条数，从0计数；None表示没有下一页。
    next_offset: int | None


@dataclass(frozen=True, slots=True)
class MaterialSearchMatch:
    """一个命中块及截取文本；matched_queries针对完整块，不只是截取文本。"""

    # 内部完整正文块，保留来源与定位，不直接对模型整体序列化。
    fragment: MaterialFragment
    # 完整原块命中的查询词，保持查询顺序。
    matched_queries: tuple[str, ...]
    # 截取后返回的命中文本，长度受max_chars_per_match限制。
    text: str
    # True表示text未包含该块完整原文。
    text_truncated: bool


@dataclass(frozen=True, slots=True)
class MaterialSearchResult:
    """total_matches是命中块总数，truncated仅表示结果条数被截断。"""

    # 本次返回的命中块结果，受max_results限制。
    matches: tuple[MaterialSearchMatch, ...]
    # 限制条数前的命中块总数，不是关键词出现次数。
    total_matches: int
    # True表示命中块未全部返回；与单块文本截断不同。
    truncated: bool


@dataclass(frozen=True, slots=True)
class MaterialReadResult:
    """一次块内读取结果；保留原块定位，end_offset不包含该字符。

    next_offset为None表示已读到块尾；总长度取自fragment.text。
    工具另行选择公开字段，不直接序列化包含project_id的原块。
    """

    # 被读取的内部完整原块，包含内部项目范围。
    fragment: MaterialFragment
    # 本次实际读出的原文子串，不改变空白或添加省略号。
    text: str
    # 本次读取起点，相对完整块，从0开始，单位为Python字符。
    offset: int
    # 实际读取终点，不包含该位置，单位为Python字符。
    end_offset: int
    # 续读起点；None表示已到块末尾。
    next_offset: int | None
