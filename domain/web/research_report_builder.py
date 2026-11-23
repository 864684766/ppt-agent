"""把网页研究结果整理为面向调用方的检查报告，不调用模型或网络。"""

from models.web.research_contract import ResearchState
from models.web.research_report import ResearchIssue, ResearchReport


def build_research_report(state: ResearchState) -> ResearchReport:
    """汇总现有网页结果；只接受已经确定停止原因的状态。

    统计类问题由程序计算；内容缺口原样来自模型summary.gaps，不视为事实核验。
    链接读取错误保留可公开的原因及候选编号；不会把内部搜索feedback放入报告。
    本步骤不负责真正向用户询问，也不处理尚未接入的文件解析结果。
    """
    stop = state["stop_reason"]
    if not stop:
        raise ValueError("资料收集尚未结束，无法生成检查报告。")
    issues: list[ResearchIssue] = []
    summary = state["summary"]
    usable = bool(summary and summary["points"])
    if not usable:
        issues.append({"type": "no_usable_content", "message": "当前没有整理出可用的网页正文内容。", "candidate_ids": []})
    if state["effective_count"] < state["target_count"]:
        issues.append({"type": "source_count_insufficient", "message": f"当前有{state['effective_count']}个有效网页来源，目标为{state['target_count']}个。", "candidate_ids": []})
    if summary:
        for gap in dict.fromkeys(summary["gaps"]):
            if gap.strip():
                issues.append({"type": "content_gap", "message": gap, "candidate_ids": []})
    if state["failed_attempts"]:
        all_failed = state["failed_attempts"] == state["attempt"]
        issues.append({"type": "search_failed" if all_failed else "search_partially_failed",
                       "message": f"{state['failed_attempts']}次搜索调用失败。", "candidate_ids": []})
    for failure in state["read_failures"]:
        issues.append({"type": "webpage_read_failed", "message": failure["reason"], "candidate_ids": [failure["candidate_id"]]})
    for page in state["pages"]:
        if page["truncated"]:
            issues.append({"type": "webpage_truncated", "message": "该网页正文超过返回长度，已截断。", "candidate_ids": [page["candidate_id"]]})
    for item in state["unreviewed"]:
        issues.append({"type": "review_unfinished", "message": "该网页候选因模型输出超限未完成检查。", "candidate_ids": [item["candidate_id"]]})
    return {"has_usable_content": usable, "source_count": state["effective_count"],
            "target_source_count": state["target_count"], "stop_reason": stop, "issues": issues}
