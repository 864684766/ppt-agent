"""对资料收集结果应用用户决定，不依赖图或HTTP。"""

from typing import cast

from models.web.research_contract import ResearchState


def apply_research_decision(state: ResearchState, decision: str, *,
                        alternative_ids: list[str] | None = None) -> ResearchState:
    """处理调用方的选择，返回新状态；不实现前端交互或会话恢复。

    use_alternatives须提供用户选中的备用candidate_id；至少一项且必须属于
    当前备用池。正式候选保留，选中的备用单独记录，不能伪装成正式资料。
    其他选择不接受alternative_ids，避免把错误的调用误认为用户已确认。
    """
    if state["status"] != "awaiting_user" or decision not in state["user_options"]:
        raise ValueError("当前状态或用户选择无效。")
    # 先建立编号索引，确保后面的校验和选取都使用同一份候选列表。
    available = {item["candidate_id"]: item for item in state["alternatives"]}
    if decision == "use_alternatives":
        if not alternative_ids or len(set(alternative_ids)) != len(alternative_ids) or any(
            item not in available for item in alternative_ids
        ):
            raise ValueError("请选择当前备用池中至少一个不重复的候选编号。")
    elif alternative_ids is not None:
        raise ValueError("只有选择备用资料时才能传入备用候选编号。")
    result = dict(state)
    result["user_options"] = []
    if decision == "provide_materials":
        result["status"] = "needs_materials"
        result["message"] = "请提供参考资料，收到并解析后再继续。"
    elif decision == "use_current":
        result["status"] = "completed"
        result["message"] = "用户选择使用当前资料；最终PPT可能少于8至12页，内容和来源仍需核对。"
    elif decision == "use_alternatives":
        # 根据已校验的编号选择，不修改原备用池，也不把它们加入accepted。
        assert alternative_ids is not None
        result["selected_alternatives"] = [available[item] for item in alternative_ids]
        result["status"] = "completed"
        result["message"] = "用户已选择备用候选；其未满足的要求、正文和来源仍需核对。"
    else:
        result["status"] = "cancelled"
        result["message"] = "当前信息不足，本次对话结束；可以换一个主题试试。"
    return cast(ResearchState, result)
