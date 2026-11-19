"""LangGraph调度查询和检查子Agent，累积候选直到达到目标或尝试次数耗尽。"""

import logging
from typing import Any, Literal, cast

from langchain_core.tools import ToolException
from langgraph.graph import END, START, StateGraph

from diagnostics.operation_logging import log_operation
from domain.web.research_agents_contract import ResearchQueryAgentContract, ResearchReviewAgentContract
from domain.web.research_candidate_merge import merge_research_candidates
from models.web.research_contract import ResearchState


logger = logging.getLogger(__name__)


class WebResearchWorkflow:
    """用LangGraph编排查询和检查，按目标数量收集初筛候选。

    每次run创建新的ResearchState；图中节点接收状态、返回需要更新的字段。
    本类不读取环境变量、不创建模型或连接，也不负责关闭外层资源。
    当前只处理搜索标题与摘要，未读取正文、验证事实或接入chat接口。
    """

    def __init__(self, *, query_agent: ResearchQueryAgentContract, review_agent: ResearchReviewAgentContract) -> None:
        """创建图但不运行；调用run才会请求模型或搜索服务。

        Args:
            query_agent: 提供search方法的查询子Agent，由它生成搜索词并执行工具。
            review_agent: 提供review方法的检查子Agent，由它判断候选是否相关。
        """
        self._query_agent = query_agent
        self._review_agent = review_agent
        # StateGraph像一张执行路线图：State定义节点之间共享哪些字段。
        # add_node注册步骤，add_edge连接固定路线；条件边决定循环或结束。
        graph = StateGraph(ResearchState)
        graph.add_node("query", self._query)
        graph.add_node("review", self._review)
        graph.add_edge(START, "query")
        graph.add_edge("query", "review")
        # 路由函数直接返回目标节点名或END；无需额外的路径映射。
        graph.add_conditional_edges("review", self._next)
        # compile将路线图编译为可调用对象；此时不会运行节点。
        self._graph = graph.compile()

    async def _query(self, state: ResearchState) -> dict[str, Any]:
        """执行图中的查询节点，返回需要更新到ResearchState的字段。

        state是当前图状态；返回字典只包含本节点修改的字段，LangGraph会
        合并到状态。每轮都使用宿主注入的同一个搜索工具。
        搜索工具抛ToolException时记录失败并继续；模型输出等其他错误传播。
        """
        logger.info("event=research_search attempt=%d", state["attempt"] + 1)
        try:
            query, candidates = await self._query_agent.search(
                question=state["question"], feedback=state["feedback"],
            )
        except ToolException:
            return {"attempt": state["attempt"] + 1, "query": "", "candidates": [],
                    "failed_attempts": state["failed_attempts"] + 1,
                    "feedback": "上次搜索调用失败，请重新尝试。"}
        return {"attempt": state["attempt"] + 1, "query": query, "candidates": candidates}

    async def _review(self, state: ResearchState) -> dict[str, Any]:
        """执行图中的检查节点，返回已合并候选和下一轮反馈。

        state.candidates来自本轮搜索；review输出编号后，仅保留本轮实际存在
        的编号。按完整URL去重：同一URL重复出现时只保留一条并记录发现策略。
        不比较网页正文；不同URL指向同一篇转载文章时仍可能被当成不同候选。
        """
        if not state["candidates"]:
            return {"feedback": "本轮没有候选或搜索失败，请调整搜索词后重试。"}
        review = await self._review_agent.review(question=state["question"], candidates=state["candidates"])
        # 每轮都与正式池和备用池比较，确保同一URL不会重复计数。
        accepted, alternatives = merge_research_candidates(
            accepted=state["accepted"], alternatives=state["alternatives"],
            candidates=state["candidates"], review=review, strategy="server_default",
        )
        logger.info("event=research_review accepted_count=%d alternative_count=%d attempt=%d",
                    len(accepted), len(alternatives), state["attempt"])
        # 只保留简短反馈供下轮搜索；备用原因在alternatives中单独保存。
        return {"accepted": accepted, "alternatives": alternatives, "feedback": review.feedback[:300]}

    @staticmethod
    def _next(state: ResearchState) -> Literal["query", "__end__"]:
        """条件边路由：返回query继续下一轮，返回END结束图。"""
        if len(state["accepted"]) >= state["target_count"]:
            return END
        return "query" if state["attempt"] < state["max_attempts"] else END

    @log_operation("workflow.web_research")
    async def run(self, *, question: str, target_count: int = 5, max_attempts: int = 6) -> ResearchState:
        """启动一次独立搜索任务并返回完整ResearchState。

        Args:
            question: 非空用户需求；会发送给模型，不应包含不应外传的内容。
            target_count: 希望返回的初筛候选数量，1至20，默认5；不足时不会凑数。
            max_attempts: 搜索总轮数，范围1至20，默认6；每轮使用服务器默认搜索。

        Returns:
            ResearchState。accepted和alternatives分别为去重后的正式与备用候选，status为completed、awaiting_user
            或failed，message解释结果；attempt为总次数，failed_attempts
            为搜索工具失败次数。completed只代表数量达标，不代表网页内容可信。

        Raises:
            ValueError: 参数越界或问题为空。
            模型调用、结构化解析和未被工具转换的其他异常继续向调用方传播。
        """
        if not question.strip() or not 1 <= target_count <= 20 or not 1 <= max_attempts <= 20:
            raise ValueError("问题不能为空；目标数量和最大搜索次数必须为1至20。")
        # 初始化一次任务所需的状态；这些字段不是持久化数据库或长期会话。
        state: ResearchState = {"question": question.strip(), "target_count": target_count, "max_attempts": max_attempts,
            "attempt": 0, "query": "", "feedback": "", "candidates": [], "accepted": [], "alternatives": [], "selected_alternatives": [],
            "failed_attempts": 0, "status": "running", "message": "", "user_options": []}
        # 每轮包含query和review两个节点；recursion_limit限制图的步数，
        # 不是模型输出token或单次HTTP超时。
        # LangGraph的通用接口返回类型较宽；该图以ResearchState构建，
        # cast只向类型检查器说明约定，不会在运行时执行字段校验。
        result = cast(ResearchState, await self._graph.ainvoke(
            state, config={"recursion_limit": max(25, max_attempts * 2 + 2)},
        ))
        if len(result["accepted"]) >= target_count:
            # 最后一轮可能一次返回多条，只交付请求的数量，保持引擎原有顺序。
            result["accepted"] = result["accepted"][:target_count]
            result["status"] = "completed"
            result["message"] = "已达到候选数量；正文、权威性和事实仍需核对。"
        else:
            result["status"] = "awaiting_user"
            # 按已有结果提供选项；备用资料必须由用户明确选择，不能自动混入正式池。
            options = ["provide_materials"]
            if result["accepted"]:
                result["message"] = f"本次仅找到{len(result['accepted'])}条候选，是否补充资料或使用当前资料？"
                options.append("use_current")
            else:
                if result["failed_attempts"] == result["attempt"]:
                    result["message"] = "本次搜索全部失败，未能取得候选。是否自行提供资料？如果不提供，本次对话将结束。"
                else:
                    result["message"] = "本次未找到可用候选，是否自行提供资料？如果不提供，本次对话将结束。"
            if result["alternatives"]:
                result["message"] = f"找到{len(result['accepted'])}条正式候选和{len(result['alternatives'])}条备用候选；备用资料未完全满足要求，请查看原因后选择。"
                options.append("use_alternatives")
            options.append("end_conversation")
            result["user_options"] = options
        return result

    @staticmethod
    def apply_user_decision(state: ResearchState, decision: str, *,
                            alternative_ids: list[str] | None = None) -> ResearchState:
        """处理调用方的选择，返回新状态；不实现前端交互或会话恢复。

        use_alternatives须提供用户选中的备用candidate_id；至少一项且必须属于
        当前备用池。正式候选保留，选中的备用单独记录，不能伪装成正式资料。
        其他选择不接受alternative_ids，避免把错误的调用误认为用户已确认。
        """
        if state["status"] != "awaiting_user" or decision not in state["user_options"]:
            raise ValueError("当前状态或用户选择无效。")
        if decision == "use_alternatives":
            available = {item["candidate_id"]: item for item in state["alternatives"]}
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
            result["message"] = "用户选择使用当前候选；正文和来源仍需核对。"
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
