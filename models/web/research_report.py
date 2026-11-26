"""网页资料检查报告：供后续询问卡片使用，不代表事实已核验。"""

from typing import Literal, TypedDict


class ResearchIssue(TypedDict):
    """一项检查问题；同一次任务可以有多个问题。"""

    type: Literal["no_usable_content", "source_count_insufficient", "content_gap", "source_conflict", "version_issue", "source_requirement", "search_failed", "search_partially_failed", "webpage_read_failed", "webpage_truncated", "review_unfinished", "review_timeout", "summary_unfinished", "workflow_failed", "followup_unread", "content_review_deferred"]  # 问题类别；内容问题是模型判断。
    message: str  # 可展示的简短说明；模型缺口为模型判断，未经事实核验。
    candidate_ids: list[str]  # 关联网页候选编号；全局问题为空列表，不是资料库source_id。


class ResearchReport(TypedDict):
    """一次网页收集的检查结果，由程序在图结束后创建。"""

    has_usable_content: bool  # 是否有已提炼或汇总的网页要点；不保证真实性或充分性。
    source_count: int  # 通常为汇总要点引用的网页数；中断且未汇总时为成功提炼出要点的网页数。
    target_source_count: int  # 本次期望来源数。
    stop_reason: Literal["target_reached", "search_limit", "page_limit", "search_failed", "provided_pages_exhausted", "summary_deferred", "model_timeout", "summary_length_exceeded", "workflow_error"]  # summary_deferred表示交由上层汇总；不代表资料充分。
    issues: list[ResearchIssue]  # 检查发现的问题；没有时为空列表，不包含内部搜索feedback。
