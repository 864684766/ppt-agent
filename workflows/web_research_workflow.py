"""LangGraph调度查询和检查子Agent，累积候选直到达到目标或尝试次数耗尽。"""

import logging
from hashlib import sha256
from urllib.parse import urlsplit
from typing import Any, Literal, cast

from langchain_core.tools import BaseTool, ToolException
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from openai import LengthFinishReasonError

from diagnostics.operation_logging import log_operation
from domain.web.research_agents_contract import ResearchQueryAgentContract, ResearchReviewAgentContract
from domain.web.research_candidate_merge import merge_research_candidates
from domain.web.research_report_builder import build_research_report
from models.web.research_contract import ResearchState
from agents.web_research_summary_agent import WebResearchSummaryAgent


logger = logging.getLogger(__name__)


class WebResearchWorkflow:
    """用LangGraph编排查询和检查，按目标数量收集初筛候选。

    每次run创建新的ResearchState；图中节点接收状态、返回需要更新的字段。
    本类不读取环境变量、不创建模型或连接，也不负责关闭外层资源。
    搜索后逐页读取正式候选并整理正文；未验证事实或接入chat接口。
    """

    def __init__(self, *, query_agent: ResearchQueryAgentContract, review_agent: ResearchReviewAgentContract,
                 fetch_tool: BaseTool, summary_agent: WebResearchSummaryAgent,
                 target_count: int = 5, max_attempts: int = 6, max_pages: int = 15) -> None:
        """创建图但不运行；调用run才会请求模型或搜索服务。

        Args:
            query_agent: 提供search方法的查询子Agent，由它生成搜索词并执行工具。
            review_agent: 提供review方法的检查子Agent，由它判断候选是否相关。
            fetch_tool: 已由宿主绑定网页读取器的工具；网络资源由宿主管理。
            summary_agent: 根据已读正文整理要点的Agent。
            target_count、max_attempts、max_pages: 宿主注入的默认目标和上限；run传值可覆盖。
        """
        self._query_agent = query_agent
        self._review_agent = review_agent
        self._fetch_tool = fetch_tool
        self._summary_agent = summary_agent
        self._target_count = target_count
        self._max_attempts = max_attempts
        self._max_pages = max_pages
        # StateGraph像一张执行路线图：State定义节点之间共享哪些字段。
        # add_node注册步骤，add_edge连接固定路线；条件边决定循环或结束。
        graph = StateGraph(ResearchState)
        graph.add_node("query", self._query)
        graph.add_node("review", self._review)
        graph.add_node("fetch", self._fetch)
        graph.add_node("summarize", self._summarize)
        graph.add_edge(START, "query")
        graph.add_edge("query", "review")
        # 路由函数直接返回目标节点名或END；无需额外的路径映射。
        graph.add_conditional_edges("review", self._next)
        graph.add_conditional_edges("fetch", self._after_fetch)
        graph.add_conditional_edges("summarize", self._after_summary)
        # compile将路线图编译为可调用对象；此时不会运行节点。
        # 检查点保存在这个工作流实例的内存中。节点成功结束后，LangGraph
        # 保存状态和下一节点；实例销毁或进程退出后无法再恢复。
        self._checkpointer = InMemorySaver()
        self._graph = graph.compile(checkpointer=self._checkpointer)

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
            return {"attempt": state["attempt"] + 1, "query": "", "candidates": [], "review_batches": [],
                    "failed_attempts": state["failed_attempts"] + 1,
                    "feedback": "上次搜索调用失败，请重新尝试。"}
        # 每批最多两条：列表切片允许最后一批不足两条，不会遗漏候选。
        batches = [candidates[index:index + 2] for index in range(0, len(candidates), 2)]
        return {"attempt": state["attempt"] + 1, "query": query, "candidates": candidates, "review_batches": batches}

    async def _review(self, state: ResearchState) -> dict[str, Any]:
        """执行图中的检查节点，返回已合并候选和下一轮反馈。

        state.candidates来自本轮搜索；review输出编号后，仅保留本轮实际存在
        的编号。按完整URL去重：同一URL重复出现时只保留一条并记录发现策略。
        不比较网页正文；不同URL指向同一篇转载文章时仍可能被当成不同候选。
        """
        if not state["review_batches"]:
            return {"feedback": "本轮没有候选或搜索失败，请调整搜索词后重试。"}
        # 节点每次只处理队首一批；返回后LangGraph会保存状态和下一节点。
        batch, remaining = state["review_batches"][0], state["review_batches"][1:]
        try:
            review = await self._review_agent.review(question=state["question"], candidates=batch)
        except LengthFinishReasonError:
            if len(batch) > 1:
                # 二分后先检查左半，再检查右半；每次拆分都会减少批次大小。
                middle = len(batch) // 2
                logger.warning("event=research_review_split batch_size=%d", len(batch))
                return {"review_batches": [batch[:middle], batch[middle:], *remaining]}
            # 单条仍超限时跳过这次检查并明确记录，不能归类成不相关。
            item = batch[0]
            unreviewed = [x for x in state["unreviewed"] if x["url"] != item["url"]]
            logger.warning("event=research_review_unfinished count=1")
            return {"review_batches": remaining, "unreviewed": [*unreviewed, item]}
        # 每轮都与正式池和备用池比较，确保同一URL不会重复计数。
        accepted, alternatives = merge_research_candidates(
            accepted=state["accepted"], alternatives=state["alternatives"],
            candidates=batch, review=review, strategy="server_default",
        )
        # 本次成功检查过的URL不再属于未检查；即使模型判断为无关也已检查。
        checked_urls = {item["url"] for item in batch}
        unreviewed = [item for item in state["unreviewed"] if item["url"] not in checked_urls]
        logger.info("event=research_review accepted_count=%d alternative_count=%d attempt=%d",
                    len(accepted), len(alternatives), state["attempt"])
        # 只保留简短反馈供下轮搜索；备用原因在alternatives中单独保存。
        return {"accepted": accepted, "alternatives": alternatives, "feedback": review.feedback[:300],
                "review_batches": remaining, "unreviewed": unreviewed}

    @staticmethod
    def _next(state: ResearchState) -> Literal["query", "review", "fetch", "__end__"]:
        """条件边路由：返回query继续下一轮，返回END结束图。"""
        if state["review_batches"]:
            return "review"
        if state["read_index"] >= state["max_pages"]:
            return END
        if state["read_index"] < len(state["accepted"]) and state["read_index"] < state["max_pages"]:
            return "fetch"
        if state["attempt"] < state["max_attempts"]:
            return "query"
        return END

    async def _fetch(self, state: ResearchState) -> dict[str, Any]:
        """读取一条正式候选；每次节点完成后检查点记录进度和结果。"""
        candidate = state["accepted"][state["read_index"]]
        try:
            page = await self._fetch_tool.ainvoke({"url": candidate["url"], "max_chars": 3000})
        except ToolException as error:
            logger.warning("event=research_page_failed")
            failure = {"candidate_id": candidate["candidate_id"], "url": candidate["url"], "reason": str(error)}
            return {"read_index": state["read_index"] + 1, "read_failures": [*state["read_failures"], failure]}
        if not page["text"].strip():
            failure = {"candidate_id": candidate["candidate_id"], "url": candidate["url"], "reason": "网页未提取到正文。"}
            return {"read_index": state["read_index"] + 1, "read_failures": [*state["read_failures"], failure]}
        # 相同最终地址或完全相同的可见文字不重复计数；近义内容仍需模型判断。
        if any(old["final_url"] == page["final_url"] or old["text"] == page["text"] for old in state["pages"]):
            logger.info("event=research_page_duplicate")
            return {"read_index": state["read_index"] + 1}
        logger.info("event=research_page_read count=%d truncated=%s", state["read_index"] + 1, page["truncated"])
        return {"read_index": state["read_index"] + 1,
                "pages": [*state["pages"], {"candidate_id": candidate["candidate_id"], **page}]}

    @staticmethod
    def _after_fetch(state: ResearchState) -> Literal["query", "fetch", "summarize", "__end__"]:
        """优先处理剩余候选；没有可读正文时不请求整理模型。"""
        if state["pages"]:
            return "summarize"
        if state["read_index"] < len(state["accepted"]) and state["read_index"] < state["max_pages"]:
            return "fetch"
        return "query" if state["attempt"] < state["max_attempts"] and state["read_index"] < state["max_pages"] else END

    async def _summarize(self, state: ResearchState) -> dict[str, Any]:
        """只整理真实读到的正文；模型异常向外传播以便恢复节点。"""
        summary = await self._summary_agent.summarize(question=state["question"], pages=state["pages"])
        # 仅统计模型要点实际引用的网页，不把导航页或无关正文按来源计数。
        used = {candidate_id for point in summary.points for candidate_id in point.candidate_ids}
        # 只接收已读页面中真实存在的同站链接；避免模型凭空构造地址。
        existing = {item["url"] for item in state["accepted"]}
        pages = {page["candidate_id"]: page for page in state["pages"]}
        extra = []
        for follow in summary.follow_links:
            page = pages[follow.candidate_id]
            url = follow.url
            link = next(link for link in page["links"] if link["url"] == url)
            origin = page["final_url"]
            if url not in existing and urlsplit(url).hostname == urlsplit(origin).hostname:
                extra.append({"candidate_id": "web_" + sha256(url.encode()).hexdigest(), "url": url,
                              "title": link["text"], "snippet": "", "engines": [],
                              "search_strategies": ["site_link"]})
                existing.add(url)
        return {"summary": summary.model_dump(), "effective_count": len(used),
                "accepted": [*state["accepted"], *extra], "feedback": "；".join(summary.gaps)[:300]}

    @staticmethod
    def _after_summary(state: ResearchState) -> Literal["query", "fetch", "__end__"]:
        """有效来源和明确缺口共同决定是否停止；上限用尽时交给调用方。"""
        if state["effective_count"] >= state["target_count"] and not state["summary"]["gaps"]:
            return END
        if state["read_index"] >= state["max_pages"]:
            return END
        if state["read_index"] < len(state["accepted"]):
            return "fetch"
        return "query" if state["attempt"] < state["max_attempts"] else END

    @log_operation("workflow.web_research")
    async def run(self, *, thread_id: str, question: str, target_count: int | None = None, max_attempts: int | None = None,
                  max_pages: int | None = None) -> ResearchState:
        """启动一次独立搜索任务并返回完整ResearchState。

        Args:
            thread_id: 调用方为本次任务创建的非空唯一编号；出错后用它恢复。
            question: 非空用户需求；会发送给模型，不应包含不应外传的内容。
            target_count: 希望得到的有效网页来源数量，1至20，默认5；不足时不会凑数。
            max_attempts: 搜索总轮数，范围1至20，默认6；每轮使用服务器默认搜索。
            max_pages: 最多读取网页次数（包含失败），范围1至50，默认15。

        Returns:
            ResearchState。accepted和alternatives分别为去重后的正式与备用候选，status为completed、awaiting_user
            或failed，message解释结果；attempt为总次数，failed_attempts
            为搜索工具失败次数。completed只代表数量达标，不代表网页内容可信。

        Raises:
            ValueError: 参数越界或问题为空。
            模型调用、结构化解析和未被工具转换的其他异常继续向调用方传播。
        """
        # None采用宿主注入的默认值；显式传值优先，不能用or替换，否则0会被误接受。
        target_count = self._target_count if target_count is None else target_count
        max_attempts = self._max_attempts if max_attempts is None else max_attempts
        max_pages = self._max_pages if max_pages is None else max_pages
        if not question.strip() or not 1 <= target_count <= 20 or not 1 <= max_attempts <= 20 or not 1 <= max_pages <= 50:
            raise ValueError("问题不能为空；目标数量和最大搜索次数必须为1至20。")
        if not thread_id or not thread_id.strip():
            raise ValueError("任务编号不能为空。")
        # 每轮最多5条候选：批次检查、拆分及搜索均计入图步数。
        # RunnableConfig是LangChain的配置类型，明确声明后编辑器能识别
        # configurable和recursion_limit分别允许字典与整数。
        config: RunnableConfig = {"configurable": {"thread_id": thread_id},
                                  "recursion_limit": max(25, max_attempts * 12 + max_pages * 2 + 4)}
        # 同一实例内不得覆盖已有任务；失败后应调用resume，而不是重新run。
        if (await self._graph.aget_state(config)).values:
            raise ValueError("任务编号已存在，请使用新编号或恢复原任务。")
        # 初始化一次任务所需的状态；这些字段不是持久化数据库或长期会话。
        state: ResearchState = {"question": question.strip(), "target_count": target_count, "max_attempts": max_attempts, "max_pages": max_pages,
            "attempt": 0, "query": "", "feedback": "", "candidates": [], "review_batches": [], "unreviewed": [], "accepted": [], "alternatives": [], "selected_alternatives": [],
            "failed_attempts": 0, "read_index": 0, "pages": [], "read_failures": [], "summary": None, "effective_count": 0,
            "status": "running", "message": "", "user_options": [], "stop_reason": "", "report": None}
        # 每轮包含query和review两个节点；recursion_limit限制图的步数，
        # 不是模型输出token或单次HTTP超时。
        # LangGraph的通用接口返回类型较宽；该图以ResearchState构建，
        # cast只向类型检查器说明约定，不会在运行时执行字段校验。
        result = cast(ResearchState, await self._graph.ainvoke(
            state, config=config,
        ))
        return self._finalize(result)

    @log_operation("workflow.web_research_resume")
    async def resume(self, *, thread_id: str) -> ResearchState:
        """恢复同一实例中未完成的任务；失败的节点会从头执行。

        thread_id必须与run一致。状态仅存在本实例内存中，进程退出无法恢复；
        没有检查点或任务已完成时抛ValueError，不自动重试或恢复用户交互。
        """
        if not thread_id or not thread_id.strip():
            raise ValueError("任务编号不能为空。")
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        snapshot = await self._graph.aget_state(config)
        if not snapshot.values or not snapshot.next:
            raise ValueError("任务不存在或没有待恢复的节点。")
        # 输入None表示继续检查点中的待执行节点，不重新提交初始状态。
        config["recursion_limit"] = max(25, snapshot.values["max_attempts"] * 12 + snapshot.values["max_pages"] * 2 + 4)
        result = cast(ResearchState, await self._graph.ainvoke(None, config=config))
        return self._finalize(result)

    @staticmethod
    def _finalize(result: ResearchState) -> ResearchState:
        """将图运行完成的状态整理为供调用方读取的结果。"""
        target_count = result["target_count"]
        if (result["effective_count"] >= target_count and result["summary"]
                and result["summary"]["points"] and not result["summary"]["gaps"]):
            # 最后一轮可能一次返回多条，只交付请求的数量，保持引擎原有顺序。
            result["status"] = "completed"
            result["stop_reason"] = "target_reached"
            result["message"] = f"已整理{result['effective_count']}个有效来源；来源权威性和事实仍需核对。"
        else:
            result["status"] = "awaiting_user"
            if result["failed_attempts"] == result["attempt"]:
                result["stop_reason"] = "search_failed"
            elif result["read_index"] >= result["max_pages"]:
                result["stop_reason"] = "page_limit"
            else:
                result["stop_reason"] = "search_limit"
            # 按已有结果提供选项；备用资料必须由用户明确选择，不能自动混入正式池。
            options = ["provide_materials"]
            if result["summary"] and result["summary"]["points"]:
                result["message"] = f"本次得到{result['effective_count']}个有效来源，目标为{target_count}；请查看缺口，可补充资料或使用当前资料。"
                options.append("use_current")
            else:
                if result["failed_attempts"] == result["attempt"]:
                    result["message"] = "本次搜索全部失败，未能取得候选。是否自行提供资料？如果不提供，本次对话将结束。"
                elif result["unreviewed"]:
                    result["message"] = "部分候选尚未完成检查，目前无法确定是否有可用资料；可提供资料或结束。"
                elif result["read_failures"]:
                    result["message"] = "候选网页读取失败，没有可用的正文要点；可提供资料或结束。"
                else:
                    result["message"] = "本次未找到可用候选，是否自行提供资料？如果不提供，本次对话将结束。"
            if result["alternatives"]:
                result["message"] += f" 另有{len(result['alternatives'])}条备用候选，请查看原因后选择。"
                options.append("use_alternatives")
            options.append("end_conversation")
            result["user_options"] = options
        if result["unreviewed"]:
            result["message"] += f" 另有{len(result['unreviewed'])}条候选因模型输出超限未完成检查。"
        # 图已经停止后再汇总已知问题；不把下一轮搜索用的feedback交给卡片。
        result["report"] = build_research_report(result)
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
