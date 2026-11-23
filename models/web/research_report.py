"""网页资料检查报告：供后续询问卡片使用，不代表事实已核验。"""

from typing import Literal, TypedDict


class ResearchIssue(TypedDict):
    """一项检查问题；同一次任务可以有多个问题。"""

    type: Literal["no_usable_content", "source_count_insufficient", "content_gap", "search_failed", "search_partially_failed", "webpage_read_failed", "webpage_truncated", "review_unfinished", "review_timeout"]  # 问题类别。
    message: str  # 可展示的简短说明；模型缺口为模型判断，未经事实核验。
    candidate_ids: list[str]  # 关联网页候选编号；全局问题为空列表，不是资料库source_id。


class ResearchReport(TypedDict):
    """一次网页收集的检查结果，由程序在图结束后创建。"""

    has_usable_content: bool  # 是否有模型根据已读网页整理出的要点；不保证真实性。
    source_count: int  # 整理要点引用的网页数；不是全部搜索候选数。
    target_source_count: int  # 本次期望来源数。
    stop_reason: Literal["target_reached", "search_limit", "page_limit", "search_failed", "model_timeout"]  # 程序停止收集的主要原因。
    issues: list[ResearchIssue]  # 检查发现的问题；没有时为空列表，不包含内部搜索feedback。
