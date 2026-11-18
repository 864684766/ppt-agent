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

    def __init__(self, *, query_agent: ResearchQueryAgentContract, review_agent: ResearchReviewAgentContract,
                 engines: tuple[str, ...]) -> None:
        """创建图但不运行；调用run才会请求模型或搜索服务。

        Args:
            query_agent: 提供search方法的查询子Agent，由它生成搜索词并执行工具。
            review_agent: 提供review方法的检查子Agent，由它判断候选是否相关。
            engines: 指定引擎名称的有序元组；例如("bing", "baidu kaifa")。
                每个名称必须与query_agent注入的tools键一致，实际可用性需测试。

        Raises:
            ValueError: 引擎列表为空、有重复，或使用保留标记server_default。
        """
        if not engines or len(set(engines)) != len(engines) or "server_default" in engines:
            raise ValueError("引擎列表必须非空、不能重复，也不能使用预留名称server_default。")
        self._query_agent = query_agent
        self._review_agent = review_agent
        self._engines = engines
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
        合并到状态。首轮不指定引擎，后续按列表轮换。
        搜索工具抛ToolException时记录失败并继续；模型输出等其他错误传播。
        """
        # 第一轮让服务器选择；后续从列表下标0开始，超出列表后循环。
        if state["attempt"] == 0:
            engine = None
            label = "server_default"
        else:
            engine_index = (state["attempt"] - 1) % len(self._engines)
            engine = self._engines[engine_index]
            label = engine
        logger.info("event=research_search attempt=%d server_default=%s", state["attempt"] + 1, engine is None)
        # None是调用查询Agent时约定的默认搜索标记；返回状态中使用可读字符串。
        try:
            query, candidates = await self._query_agent.search(
                question=state["question"], feedback=state["feedback"], engine=engine,
            )
        except ToolException:
            return {"attempt": state["attempt"] + 1, "engine": label, "query": "", "candidates": [],
                    "failed_engines": [*state["failed_engines"], label],
                    "feedback": "上一引擎调用失败，请调整搜索词并尝试下一个引擎。"}
        return {"attempt": state["attempt"] + 1, "engine": label, "query": query, "candidates": candidates}

    async def _review(self, state: ResearchState) -> dict[str, Any]:
        """执行图中的检查节点，返回已合并候选和下一轮反馈。

        state.candidates来自本轮搜索；review输出编号后，仅保留本轮实际存在
        的编号。按完整URL去重：同一URL重复出现时只保留一条并记录发现策略。
        不比较网页正文；不同URL指向同一篇转载文章时仍可能被当成不同候选。
        """
        if not state["candidates"]:
            return {"feedback": "本轮没有候选或搜索失败，请调整搜索词并尝试其他引擎。"}
        review = await self._review_agent.review(question=state["question"], candidates=state["candidates"])
        # 每轮都与正式池和备用池比较，确保同一URL不会重复计数。
        accepted, alternatives = merge_research_candidates(
            accepted=state["accepted"], alternatives=state["alternatives"],
            candidates=state["candidates"], review=review, strategy=state["engine"],
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
            max_attempts: 搜索总轮数，包含首轮服务器默认搜索，范围1至20，默认6。

        Returns:
            ResearchState。accepted和alternatives分别为去重后的正式与备用候选，status为completed、awaiting_user
            或failed，message解释结果；attempt为总次数，failed_engines
            记录失败策略。completed只代表数量达标，不代表网页内容可信。

        Raises:
            ValueError: 参数越界、问题为空，或没有注入默认工具。
            模型调用、结构化解析和未被工具转换的其他异常继续向调用方传播。
        """
        if not question.strip() or not 1 <= target_count <= 20 or not 1 <= max_attempts <= 20:
            raise ValueError("问题不能为空；目标数量和最大搜索次数必须为1至20。")
        if not self._query_agent.has_default_tool:
            raise ValueError("首轮服务器默认搜索需要注入不指定引擎的工具。")
        # 初始化一次任务所需的状态；这些字段不是持久化数据库或长期会话。
        state: ResearchState = {"question": question.strip(), "target_count": target_count, "max_attempts": max_attempts,
            "attempt": 0, "engine": "", "query": "", "feedback": "", "candidates": [], "accepted": [], "alternatives": [],
            "failed_engines": [], "status": "running", "message": "", "user_options": []}
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
            if result["accepted"]:
                result["message"] = f"本次仅找到{len(result['accepted'])}条候选，是否补充资料或使用当前资料？"
                result["user_options"] = ["provide_materials", "use_current"]
            else:
                if len(result["failed_engines"]) == result["attempt"]:
                    result["message"] = "本次搜索全部失败，未能取得候选。是否自行提供资料？如果不提供，本次对话将结束。"
                else:
                    result["message"] = "本次未找到可用候选，是否自行提供资料？如果不提供，本次对话将结束。"
                result["user_options"] = ["provide_materials", "end_conversation"]
        return result

    @staticmethod
    def apply_user_decision(state: ResearchState, decision: str) -> ResearchState:
        """处理调用方传入的真实选择；不上传文件，也不保存或恢复会话。"""
        if state["status"] != "awaiting_user" or decision not in state["user_options"]:
            raise ValueError("当前状态或用户选择无效。")
        result = dict(state)
        result["user_options"] = []
        if decision == "provide_materials":
            result["status"] = "needs_materials"
            result["message"] = "请提供参考资料，收到并解析后再继续。"
        elif decision == "use_current":
            result["status"] = "completed"
            result["message"] = "用户选择使用当前候选；正文和来源仍需核对。"
        else:
            result["status"] = "cancelled"
            result["message"] = "当前信息不足，本次对话结束；可以换一个主题试试。"
        return cast(ResearchState, result)
