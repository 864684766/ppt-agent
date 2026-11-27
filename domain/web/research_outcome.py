"""根据网页研究状态生成结束结果；不调用模型、网络或LangGraph。"""

from models.web.research_contract import ResearchState
from domain.web.research_report_builder import build_research_report


def finalize_research(state: ResearchState, *, question_id: str) -> ResearchState:
    """汇总状态、检查报告和待回答问题；返回新字典，不修改输入。"""
    result = state.copy()
    _set_result_status(result)
    if result["unreviewed"]:
        result["message"] += f" 另有{len(result['unreviewed'])}条候选因模型输出超限未完成检查。"
    result["report"] = build_research_report(result)
    if result["status"] == "awaiting_user" and result["defer_user_question"]:
        # 此时网页不足仅是上层的输入；不能创建问题或宣称正在等待用户。
        result["status"] = "insufficient"
        result["message"] = "网页资料未达到本次收集条件；请结合其他资料和检查报告继续判断。"
        result["user_options"] = []
    result["waiting_question"] = _build_question(result, question_id) if result["status"] == "awaiting_user" else None
    return result


def _set_result_status(result: ResearchState) -> None:
    """按执行失败、目标达成、资料不足的优先级设置结果。"""
    if result["workflow_error_kind"]:
        result["status"] = "interrupted"
        result["stop_reason"] = "workflow_error"
        result["user_options"] = []
        descriptions = {"model_connection": "模型连接失败", "model_timeout": "模型请求超时",
                        "model_service_error": "模型服务返回错误", "execution_failed": "网页处理发生错误"}
        reason = descriptions.get(result["workflow_error_kind"], "网页处理发生错误")
        stage = {"fetch": "网页读取或内容提炼阶段", "query": "搜索阶段", "review": "候选检查阶段",
                 "summarize": "网页汇总阶段"}.get(result["workflow_error_stage"] or "", "网页处理阶段")
        result["message"] = f"{stage}{reason}，网页资料处理未完成；已保留完成的结果，请检查服务日志或重试。"
        if result["workflow_error_stage"] == "fetch":
            result["message"] += " 当前网页可能仅完成部分分段，不代表全文已处理。"
    elif result["summary_length_exceeded"]:
        result["status"] = "interrupted"
        result["stop_reason"] = "summary_length_exceeded"
        result["user_options"] = []
        result["message"] = "网页资料汇总因模型输出超限未完成；已保留单页要点及上一次成功的汇总，不能据此判断资料是否充分。"
    elif result["review_timeout_candidates"]:
        result["status"] = "interrupted"
        result["stop_reason"] = "model_timeout"
        result["user_options"] = []
        result["message"] = "模型检查超时，当前批次及后续候选未完成检查；已保留本次已完成的结果。"
    elif result["summary_deferred"]:
        result["status"] = "collected"
        result["stop_reason"] = "summary_deferred"
        result["user_options"] = []
        result["message"] = "网页提炼已结束，内容汇总和充分性判断交由上层处理。"
    elif _target_reached(result):
        result["status"] = "completed"
        result["stop_reason"] = "target_reached"
        result["message"] = f"已整理{result['effective_count']}个有效来源；来源权威性和事实仍需核对。"
    else:
        _set_insufficient_result(result)


def _target_reached(state: ResearchState) -> bool:
    """数量达标且没有模型报告的问题，才可视为已达到本轮收集目标。"""
    summary = state["summary"]
    return bool((not state["provided_urls_only"] or state["read_index"] >= len(state["accepted"]))
                and state["effective_count"] >= state["target_count"] and summary
                and summary["points"] and not summary["gaps"] and not summary["issues"])


def _set_insufficient_result(result: ResearchState) -> None:
    """根据已有正文、搜索和读取情况，生成需要用户决定的结果。"""
    result["status"] = "awaiting_user"
    if result["attempt"] > 0 and result["failed_attempts"] == result["attempt"]:
        result["stop_reason"] = "search_failed"
    elif result["read_index"] >= result["max_pages"]:
        result["stop_reason"] = "page_limit"
    elif result["provided_urls_only"]:
        result["stop_reason"] = "provided_pages_exhausted"
    else:
        result["stop_reason"] = "search_limit"
    options = ["provide_materials"]
    if result["summary"] and result["summary"]["points"]:
        result["message"] = f"本次得到{result['effective_count']}个有效来源，目标为{result['target_count']}；请查看缺口，可补充资料或使用当前资料。"
        options.append("use_current")
    else:
        result["message"] = _no_content_message(result)
    if result["alternatives"]:
        result["message"] += f" 另有{len(result['alternatives'])}条备用候选；逐项选择将在后续接入。"
        options.append("use_alternatives")
    options.append("end_conversation")
    result["user_options"] = options


def _no_content_message(state: ResearchState) -> str:
    """没有已整理要点时，优先说明搜索失败和尚未完成的检查。"""
    if state["attempt"] > 0 and state["failed_attempts"] == state["attempt"]:
        return "本次搜索全部失败，未能取得候选。是否自行提供资料？如果不提供，本次对话将结束。"
    if state["unreviewed"]:
        return "部分候选尚未完成检查，目前无法确定是否有可用资料；可提供资料或结束。"
    if state["read_failures"]:
        return "候选网页读取失败，没有可用的正文要点；可提供资料或结束。"
    return "本次未找到可用候选，是否自行提供资料？如果不提供，本次对话将结束。"


def _build_question(state: ResearchState, question_id: str) -> dict:
    """将报告转成稳定问题；编号由图节点创建并保存到检查点。"""
    options = [option for option in state["user_options"] if option != "use_alternatives"]
    issues = state["report"]["issues"] if state["report"] else []
    issue_text = "；".join(issue["message"] for issue in issues[:3])
    reason = (state["message"] + (" " + issue_text if issue_text else ""))[:1000]
    question = ("资料不足。请选择补充资料、使用现有资料或结束任务；选项以返回的代码为准。"
                if "use_current" in options else "尚无可用资料。请选择补充资料或结束任务；选项以返回的代码为准。")
    return {"question_id": question_id, "question": question, "reason": reason,
            "options": options, "allow_free_text": False}
