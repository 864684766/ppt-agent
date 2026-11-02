"""当前项目正文的字面检索；标准库实现，不访问网络、磁盘或模型。

此处处理跨记录关系与检索规则。扫描件OCR、文件解析以及来源登记
都由外层完成；将来更换检索后端也不应改变模型可见的工具含义。
"""

import re
from collections.abc import Sequence
from typing import Literal

from domain.materials.material_validator import validate_material_content_data
from models.materials.material_fragment import MaterialFragment
from models.materials.material_query_results import MaterialSearchMatch, MaterialSearchResult
from models.materials.material_source import MaterialSummary


def search_project_materials(
    *, project_id: str, materials: Sequence[MaterialSummary],
    fragments: Sequence[MaterialFragment], queries: Sequence[str],
    source_ids: Sequence[str] | None = None,
    origin: Literal["all", "uploaded", "web"] = "all",
    max_results: int = 10, max_chars_per_match: int = 300,
) -> MaterialSearchResult:
    """任意关键词命中即选中该块，稳定排序后返回受限结果。

    queries是字面子串，re.escape会转义正则符号；IGNORECASE用于
    忽略大小写，并保留匹配在原文中的字符位置。不是正则搜索接口。
    total_matches统计块数而非词出现次数；不做相关性或权威性排名。
    不存在/未就绪/正文未载入与零命中不同，前几种情况明确抛ValueError。
    """
    validate_material_content_data(project_id=project_id, materials=materials, fragments=fragments)
    # 独立Python调用不经过Pydantic，因此业务入口也守住基本输入约束。
    terms = _normalize_strings(queries, "queries", max_items=8)
    requested = None if source_ids is None else _normalize_strings(source_ids, "source_ids", max_items=100)
    if origin not in ("all", "uploaded", "web"):
        raise ValueError("origin必须为all、uploaded或web。")
    if type(max_results) is not int or not 1 <= max_results <= 50:
        raise ValueError("max_results必须为1至50的整数。")
    if type(max_chars_per_match) is not int or not 50 <= max_chars_per_match <= 1000:
        raise ValueError("max_chars_per_match必须为50至1000的整数。")

    sources = {item.source_id: item for item in materials if item.project_id == project_id}
    if requested is not None:
        if any(source_id not in sources for source_id in requested):
            raise ValueError("source_ids包含当前项目未登记的来源。")
        if any(sources[source_id].status != "ready" for source_id in requested):
            raise ValueError("指定来源尚未ready，请先查看解析状态。")
    selected = {
        source_id for source_id, source in sources.items()
        if source.status == "ready"
        and (requested is None or source_id in requested)
        and (origin == "all" or source.origin == origin)
    }
    blocks = [
        block for block in fragments
        if block.project_id == project_id and block.source_id in selected
    ]
    if selected - {block.source_id for block in blocks}:
        raise ValueError("目标资料正文尚未载入当前快照，不能进行检索。")
    # 页码未知的块排在已知页码之后；排序是确定顺序，不代表内容重要性。
    blocks.sort(key=lambda block: (block.source_id, block.page is None, block.page or 0, block.block_id))
    patterns = [(term, re.compile(re.escape(term), re.IGNORECASE)) for term in terms]
    matches: list[MaterialSearchMatch] = []
    total_matches = 0
    for block in blocks:
        # 逐词检查当前块，记录命中词及其在完整原文中的首次位置。
        found: list[tuple[str, int]] = []
        for term, pattern in patterns:
            match = pattern.search(block.text)
            if match is not None:
                found.append((term, match.start()))
        if not found:
            continue
        total_matches += 1
        if len(matches) >= max_results:
            continue
        # 长块围绕最早命中位置取窗口；不strip原文，不手动添加省略号。
        first_hit = min(position for _, position in found)
        start = max(0, first_hit - max_chars_per_match // 3)
        end = min(len(block.text), start + max_chars_per_match)
        matches.append(MaterialSearchMatch(
            fragment=block,
            matched_queries=tuple(term for term, _ in found),
            text=block.text[start:end],
            text_truncated=start > 0 or end < len(block.text),
        ))
    return MaterialSearchResult(tuple(matches), total_matches, total_matches > len(matches))


def _normalize_strings(values: Sequence[str], field: str, *, max_items: int) -> list[str]:
    """内部辅助：检查字符串列表并去首尾空白、精确去重，保留输入顺序。"""
    if isinstance(values, (str, bytes)) or not 1 <= len(values) <= max_items:
        raise ValueError(f"{field}数量不合法。")
    if any(not isinstance(value, str) or not 1 <= len(value.strip()) <= 200 for value in values):
        raise ValueError(f"{field}每项必须为1至200字符的非空字符串。")
    return list(dict.fromkeys(value.strip() for value in values))
