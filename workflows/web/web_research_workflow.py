"""LangGraph调度查询和检查子Agent，累积候选直到达到目标或尝试次数耗尽。"""

import logging
from hashlib import sha256
from typing import Any, Literal, cast
from uuid import uuid4

from langchain_core.tools import BaseTool, ToolException
from langchain_core.runnables import RunnableConfig
from langchain_core.callbacks import BaseCallbackHandler
from langchain_openai.chat_models.base import OpenAIConnectionError, OpenAITimeoutError
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from openai import LengthFinishReasonError

from diagnostics.operation_logging import log_operation, safe_error_location
from domain.web.research_agents_contract import ResearchQueryAgentContract, ResearchReviewAgentContract
from domain.web.research_candidate_merge import merge_research_candidates
from domain.web.research_outcome import finalize_research
from domain.web.research_decision import apply_research_decision
from domain.web.research_follow_links import select_followup_candidates
from domain.web.provided_web_addresses import provided_web_candidates
from models.web.research_contract import ResearchState
from models.web.web_research_summary import WebFollowLink, WebPageExtraction, WebResearchSummary, WebSummaryPoint
from agents.web.webpage_extraction_agent import WebpageExtractionAgent
from agents.materials.material_summary_agent import MaterialSummaryAgent
from domain.materials.material_summary_inputs import web_summary_points
from domain.web.research_summary_mapping import to_web_research_summary
from models.interaction.user_question import UserQuestion
from workflows.interaction.ask_user import ask_user
from workflows.web.research_progress import notify_progress


logger = logging.getLogger(__name__)


class PartialPageExtractionError(Exception):
    """网页某分段失败时携带已完成要点；不把部分内容视为整页完成。"""

    def __init__(self, *, extraction: WebPageExtraction, kind: str) -> None:
        super().__init__("网页分段提炼未完成。")
        self.extraction = extraction
        self.kind = kind


class WebResearchWorkflow:
    """用LangGraph编排查询和检查，按目标数量收集初筛候选。

    每次run创建新的ResearchState；图中节点接收状态、返回需要更新的字段。
    本类不读取环境变量、不创建模型或连接，也不负责关闭外层资源。
    搜索后逐页读取正式候选并整理正文；未验证事实或接入chat接口。
    """

    def __init__(self, *, query_agent: ResearchQueryAgentContract, review_agent: ResearchReviewAgentContract,
                 fetch_tool: BaseTool, webpage_extraction_agent: WebpageExtractionAgent,
                 material_summary_agent: MaterialSummaryAgent,
                 target_count: int = 5, max_attempts: int = 6, max_pages: int = 15) -> None:
        """创建图但不运行；调用run才会请求模型或搜索服务。

        Args:
            query_agent: 提供search方法的查询子Agent，由它生成搜索词并执行工具。
            review_agent: 提供review方法的检查子Agent，由它判断候选是否相关。
            fetch_tool: 已由宿主绑定网页读取器的工具；网络资源由宿主管理。
            webpage_extraction_agent: 根据单篇已读正文提炼要点的Agent。
            target_count、max_attempts、max_pages: 宿主注入的默认目标和上限；run传值可覆盖。
        """
        self._query_agent = query_agent
        self._review_agent = review_agent
        self._fetch_tool = fetch_tool
        self._webpage_extraction_agent = webpage_extraction_agent
        self._material_summary_agent = material_summary_agent
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
        graph.add_node("finalize", self._finalize)
        graph.add_node("ask", self._ask)
        graph.add_conditional_edges(START, lambda state: "fetch" if state["accepted"] else "query")
        graph.add_edge("query", "review")
        # 路由函数直接返回目标节点名或END；无需额外的路径映射。
        graph.add_conditional_edges("review", self._next)
        graph.add_conditional_edges("fetch", self._after_fetch)
        graph.add_conditional_edges("summarize", self._after_summary)
        graph.add_conditional_edges("finalize", self._after_finalize)
        graph.add_edge("ask", END)
        # compile将路线图编译为可调用对象；此时不会运行节点。
        # 检查点保存在这个工作流实例的内存中。节点成功结束后，LangGraph
        # 保存状态和下一节点；实例销毁或进程退出后无法再恢复。
        self._checkpointer = InMemorySaver()
        self._graph = graph.compile(checkpointer=self._checkpointer)

    async def _query(self, state: ResearchState) -> dict[str, Any]:
        """执行图中的查询节点，返回需要更新到ResearchState的字段。

        state是当前图状态；返回字典只包含本节点修改的字段，LangGraph会
        合并到状态。每轮都使用宿主注入的同一个搜索工具。
        搜索工具抛ToolException时记录失败并继续；其他故障交给图运行边界处理。
        """
        notify_progress("search")
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
        notify_progress("review")
        if not state["review_batches"]:
            return {"feedback": "本轮没有候选或搜索失败，请调整搜索词后重试。"}
        # 节点每次只处理队首一批；返回后LangGraph会保存状态和下一节点。
        batch, remaining = state["review_batches"][0], state["review_batches"][1:]
        try:
            review = await self._review_agent.review(question=state["question"], candidates=batch)
        except OpenAITimeoutError:
            # 当前批次及后续批次均尚未完成；按编号去重，不能误称不相关。
            pending = {item["candidate_id"]: item for group in state["review_batches"] for item in group}
            logger.warning("event=research_review_timeout unfinished_count=%d", len(pending))
            return {"review_timeout_candidates": list(pending.values()), "review_batches": []}
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
    def _next(state: ResearchState) -> Literal["query", "review", "fetch", "finalize"]:
        """检查候选后按优先级选择下一节点；从上往下，第一个满足的条件生效。

        返回值是已注册的节点名称；LangGraph会根据它运行对应节点。
        read_index是下一条待读候选的下标，也表示已经尝试读取的候选数。
        """
        # 检查候选时模型超时：保留未检查候选并进入finalize报告中断。
        if state["review_timeout_candidates"]:
            return "finalize"
        # 本轮还有尚未检查的候选批次：返回review继续逐批检查。
        if state["review_batches"]:
            return "review"
        # 已尝试读取的网页数达到上限（失败也计数）：进入finalize。
        if state["read_index"] >= state["max_pages"]:
            return "finalize"
        # 正式候选池中还有未读取的网页，且未达到读取上限：进入fetch读取下一条。
        if state["read_index"] < len(state["accepted"]) and state["read_index"] < state["max_pages"]:
            return "fetch"
        # 已无待读候选，但搜索轮数还没用完：进入query生成下一轮搜索。
        if state["attempt"] < state["max_attempts"]:
            return "query"
        # 无待读候选且搜索次数已用完：进入finalize生成结果和报告。
        return "finalize"

    async def _fetch(self, state: ResearchState) -> dict[str, Any]:
        """读取一条正式候选；每次节点完成后检查点记录进度和结果。"""
        notify_progress("read_webpage")
        candidate = state["accepted"][state["read_index"]]
        try:
            page = await self._fetch_tool.ainvoke({"url": candidate["url"], "max_chars": 50000})
        except ToolException as error:
            logger.warning("event=research_page_failed")
            failure = {"candidate_id": candidate["candidate_id"], "url": candidate["url"], "reason": str(error)}
            return {"read_index": state["read_index"] + 1, "read_failures": [*state["read_failures"], failure], "needs_summary": False}
        if not page["text"].strip():
            failure = {"candidate_id": candidate["candidate_id"], "url": candidate["url"], "reason": "网页未提取到正文。"}
            return {"read_index": state["read_index"] + 1, "read_failures": [*state["read_failures"], failure], "needs_summary": False}
        # 只保存正文指纹用于精确去重，不把原文写入图状态或检查点。
        digest = sha256(page["text"].encode("utf-8")).hexdigest()
        if any(old["final_url"] == page["final_url"] or old["text_hash"] == digest for old in state["pages"]):
            logger.info("event=research_page_duplicate")
            return {"read_index": state["read_index"] + 1, "needs_summary": False}
        # 此模型调用只接收当前网页；成功后只保存提炼要点和必要的网页元数据。
        notify_progress("extract")
        metadata = {key: page[key] for key in ("requested_url", "final_url", "title", "truncated",
                    "returned_chars", "extracted_chars", "fetched_at")}
        metadata.update(candidate_id=candidate["candidate_id"], text_hash=digest)
        try:
            extraction = await self._extract_page_chunks(question=state["question"], candidate_id=candidate["candidate_id"], page=page)
        except PartialPageExtractionError as error:
            # 保存已完成分段并标记中断，后续不能将它们当成完整网页汇总。
            return {"pages": [*state["pages"], metadata], "page_extractions": [*state["page_extractions"], {
                "candidate_id": candidate["candidate_id"], "title": page["title"], "url": page["final_url"],
                "truncated": page["truncated"], "points": [point.model_dump() for point in error.extraction.points]}],
                "workflow_error_stage": "fetch", "workflow_error_kind": error.kind, "needs_summary": False}
        extra = select_followup_candidates(page=page, follow_links=extraction.follow_links,
                                           accepted=state["accepted"])
        logger.info("event=research_page_read count=%d truncated=%s points=%d", state["read_index"] + 1,
                    page["truncated"], len(extraction.points))
        if not extraction.points:
            logger.info("event=research_summary_skipped reason=no_new_points")
        return {"read_index": state["read_index"] + 1, "pages": [*state["pages"], metadata],
                # 空要点不能改变累计汇总；仍保留页面、截断标记和跟进链接。
                "accepted": [*state["accepted"], *extra], "needs_summary": bool(extraction.points),
                "page_extractions": [*state["page_extractions"], {
                    "candidate_id": candidate["candidate_id"], "title": page["title"],
                    "url": page["final_url"], "truncated": page["truncated"],
                    "points": [point.model_dump() for point in extraction.points]}]}

    async def _extract_page_chunks(self, *, question: str, candidate_id: str, page: dict) -> WebPageExtraction:
        """每3000字符单独提炼，汇总全部段落要点；只在首段选择链接。

        每段保留同一网页编号，单段调用失败则该网页处理未完成，不将部分结果冒充全文。
        读取上限仍为50000字符，超出时由网页报告注明截断。
        """
        points: list[WebSummaryPoint] = []
        links: list[WebFollowLink] = []
        text = page["text"]
        total_chunks = (len(text) + 2999) // 3000
        for offset in range(0, len(text), 3000):
            part_text = text[offset:offset + 3000]
            chunk = {**page, "candidate_id": candidate_id, "text": part_text, "returned_chars": len(part_text),
                     "segment_index": offset // 3000 + 1, "segment_count": total_chunks,
                     "links": page["links"] if offset == 0 else []}
            try:
                part = await self._webpage_extraction_agent.extract_page(question=question, page=chunk)
            except (OpenAITimeoutError, OpenAIConnectionError, TimeoutError) as error:
                kind = "model_connection" if isinstance(error, OpenAIConnectionError) else "model_timeout"
                logger.warning("event=webpage_segment_incomplete segment=%d total=%d reason=%s",
                               offset // 3000 + 1, total_chunks, kind)
                raise PartialPageExtractionError(extraction=WebPageExtraction(points=points, follow_links=links), kind=kind) from error
            points.extend(part.points)
            links.extend(part.follow_links)
        return WebPageExtraction(points=points, follow_links=links)

    @staticmethod
    def _after_fetch(state: ResearchState) -> Literal["query", "fetch", "summarize", "finalize"]:
        """仅有新要点时汇总；空要点、读取失败后继续处理其他候选。"""
        if state["workflow_error_kind"]:
            return "finalize"
        if state["provided_urls_only"]:
            # 用户指定的栏目先读取已选文章，避免每读一篇都重复汇总；上限内按队列顺序处理。
            if state["read_index"] < len(state["accepted"]) and state["read_index"] < state["max_pages"]:
                return "fetch"
            if state["defer_user_question"]:
                return "finalize"
            # 最后一页即使失败或没有要点，前面已经提炼的内容仍需汇总。
            if any(item["points"] for item in state["page_extractions"]):
                return "summarize"
            return "finalize"
        if state["defer_user_question"]:
            # 聊天工作流将在上层统一汇总，网页阶段按有要点的独立来源数控制收集。
            source_ids = {item["candidate_id"] for item in state["page_extractions"] if item["points"]}
            if len(source_ids) >= state["target_count"]:
                return "finalize"
        elif state["needs_summary"]:
            # 独立网页研究仍由模型评估内容是否充分，反馈可用于下一轮搜索。
            return "summarize"
        # 未达到收集条件且仍有候选时，优先读取已有候选。
        if state["read_index"] < len(state["accepted"]) and state["read_index"] < state["max_pages"]:
            return "fetch"
        # 无待读候选：仍可搜索且仍可读取时回query，否则进入finalize。
        return "query" if not state["provided_urls_only"] and state["attempt"] < state["max_attempts"] and state["read_index"] < state["max_pages"] else "finalize"

    async def _summarize(self, state: ResearchState) -> dict[str, Any]:
        """根据累计单页要点判断充分性；绝不再次发送原网页正文。"""
        notify_progress("summarize")
        try:
            points = web_summary_points(extractions=state["page_extractions"])
            result = await self._material_summary_agent.summarize(question=state["question"], points=points)
            summary = to_web_research_summary(result, points)
        except LengthFinishReasonError:
            # 不覆盖上一次成功汇总或最新单页提炼；本次检查未完成，不判断资料是否充分。
            logger.warning("event=research_summary_length_interrupted page_count=%d", len(state["page_extractions"]))
            return {"summary_length_exceeded": True, "needs_summary": False}
        used = {candidate_id for point in summary.points for candidate_id in point.candidate_ids}
        # 问题也用于下一轮搜索方向；报告仍不展示这个内部反馈字符串。
        feedback = [*summary.gaps, *(issue.message for issue in summary.issues)]
        return {"summary": summary.model_dump(), "effective_count": len(used), "needs_summary": False,
                "feedback": "；".join(feedback)[:300]}

    @staticmethod
    def _after_summary(state: ResearchState) -> Literal["query", "fetch", "finalize"]:
        """有效来源数、缺口和内容问题共同决定是否停止；上限用尽时交给调用方。"""
        # 汇总模型输出超限：进入finalize报告中断，不能当作资料不足。
        if state["summary_length_exceeded"]:
            return "finalize"
        # 有效来源达到目标，且汇总没有缺口和问题：进入finalize。
        summary = state["summary"]
        if (summary is not None and state["effective_count"] >= state["target_count"] and not summary["gaps"] and not summary["issues"]
                and (not state["provided_urls_only"] or state["read_index"] >= len(state["accepted"]))):
            return "finalize"
        # 资料尚不足，但网页读取次数已经用完：进入finalize。
        if state["read_index"] >= state["max_pages"]:
            return "finalize"
        # 已有尚未读取的正式候选：优先进入fetch读取，不立即重新搜索。
        if state["read_index"] < len(state["accepted"]):
            return "fetch"
        # 没有待读候选：搜索轮数未用完就回query，否则进入finalize。
        return "query" if not state["provided_urls_only"] and state["attempt"] < state["max_attempts"] else "finalize"

    @log_operation("workflow.web_research")
    async def run(self, *, thread_id: str, question: str, target_count: int | None = None, max_attempts: int | None = None,
                  max_pages: int | None = None,
                  callbacks: list[BaseCallbackHandler] | None = None, defer_user_question: bool = False) -> ResearchState:
        """启动一次独立搜索任务并返回完整ResearchState。

        Args:
            thread_id: 调用方为本次任务创建的非空唯一编号；出错后用它恢复。
            question: 非空用户需求；会发送给模型，不应包含不应外传的内容。
            target_count: 希望得到的有效网页来源数量，1至20，默认5；不足时不会凑数。
            max_attempts: 搜索总轮数，范围1至20，默认6；每轮使用服务器默认搜索。
            max_pages: 最多读取网页次数（包含失败），范围1至50，默认15。
            callbacks: 本次任务的LangChain回调，可用于接收模型流；默认不注册。
            defer_user_question: 默认False，由本图汇总并在资料不足时询问。True时交出单页要点，由上层汇总和判断。

        Returns:
            ResearchState。accepted和alternatives分别为去重后的正式与备用候选，status为completed、awaiting_user
            、collected（上层汇总）、insufficient（上层判断且没有要点）或interrupted，message解释结果；attempt为总次数，failed_attempts
            为搜索工具失败次数。completed只代表数量达标，不代表网页内容可信。

        Raises:
            ValueError: 参数越界或问题为空。
            图执行异常转换为interrupted报告；参数错误和任务取消不转换为正常结果。
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
        # 回调由本次调用方注入并传递给图内模型，不写入共享状态。
        if callbacks:
            config["callbacks"] = callbacks
        # 同一实例内不得覆盖已有任务；失败后应调用resume，而不是重新run。
        if (await self._graph.aget_state(config)).values:
            raise ValueError("任务编号已存在，请使用新编号或恢复原任务。")
        # 初始化一次任务所需的状态；这些字段不是持久化数据库或长期会话。
        supplied = provided_web_candidates(question)
        state: ResearchState = {"question": question.strip(), "provided_urls_only": bool(supplied), "defer_user_question": defer_user_question, "workflow_error_stage": None, "workflow_error_kind": None, "target_count": target_count, "max_attempts": max_attempts, "max_pages": max_pages,
            "attempt": 0, "query": "", "feedback": "", "candidates": [], "review_batches": [], "unreviewed": [], "review_timeout_candidates": [], "accepted": supplied, "alternatives": [], "selected_alternatives": [],
            "failed_attempts": 0, "read_index": 0, "pages": [], "page_extractions": [], "needs_summary": False, "summary_deferred": False, "summary_length_exceeded": False, "read_failures": [], "summary": None, "effective_count": 0,
            "status": "running", "message": "", "user_options": [], "stop_reason": "", "report": None,
            "waiting_question": None}
        # 每轮包含query和review两个节点；recursion_limit限制图的步数，
        # 不是模型输出token或单次HTTP超时。
        # LangGraph的通用接口返回类型较宽；该图以ResearchState构建，
        # cast只向类型检查器说明约定，不会在运行时执行字段校验。
        try:
            result = cast(ResearchState, await self._graph.ainvoke(cast(Any, state), config=config))
        except Exception as error:
            # 捕获图运行故障，不捕获取消；保留最近成功检查点供调用方恢复。
            result = await self._execution_error(config=config, fallback=state, error=error)
        # LangGraph的Interrupt对象不是JSON；公开问题字段已保存在waiting_question中。
        result.pop("__interrupt__", None)  # type: ignore[typeddict-item]
        return result

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
        if "ask" in snapshot.next:
            raise ValueError("任务正在等待用户回答，请使用回答恢复方法。")
        # 输入None表示继续检查点中的待执行节点，不重新提交初始状态。
        config["recursion_limit"] = max(25, snapshot.values["max_attempts"] * 12 + snapshot.values["max_pages"] * 2 + 4)
        try:
            result = cast(ResearchState, await self._graph.ainvoke(None, config=config))
        except Exception as error:
            result = await self._execution_error(config=config, fallback=cast(ResearchState, snapshot.values), error=error)
        result.pop("__interrupt__", None)  # type: ignore[typeddict-item]
        return result

    async def _execution_error(self, *, config: RunnableConfig, fallback: ResearchState, error: Exception) -> ResearchState:
        """读取最后成功的检查点并生成安全报告；不覆盖图状态或吞掉取消。"""
        logger.error("event=research_execution_failed error_location=%s", safe_error_location(error))
        snapshot = await self._graph.aget_state(config)
        result = cast(ResearchState, dict(snapshot.values or fallback))
        result["workflow_error_stage"] = snapshot.next[0] if snapshot.next else None
        result["workflow_error_kind"] = ("model_timeout" if isinstance(error, (OpenAITimeoutError, TimeoutError)) else
                                          "model_connection" if isinstance(error, OpenAIConnectionError) else "execution_failed")
        return finalize_research(result, question_id=uuid4().hex)

    @staticmethod
    def _after_finalize(state: ResearchState) -> str:
        """仅资料不足时暂停；模型故障与正常完成均直接结束。"""
        return "ask" if state["waiting_question"] is not None else END

    def _ask(self, state: ResearchState) -> ResearchState:
        """调用通用询问；恢复时节点重跑，问题编号来自此前保存的状态。"""
        data = state["waiting_question"]
        if data is None:
            raise ValueError("任务没有待回答的问题。")
        question = UserQuestion(**{**data, "options": tuple(data["options"])})
        answer = ask_user(question)
        result = self.apply_user_decision(state, answer)
        result["waiting_question"] = None
        return result

    @log_operation("workflow.web_research_answer")
    async def answer(self, *, thread_id: str, question_id: str, answer: str) -> ResearchState:
        """在同一实例中恢复待回答任务；此方法不接收文件，也不是HTTP接口。"""
        if not thread_id.strip() or not question_id.strip():
            raise ValueError("任务编号和问题编号不能为空。")
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        snapshot = await self._graph.aget_state(config)
        if not snapshot.values or "ask" not in snapshot.next:
            raise ValueError("任务不存在或当前没有等待回答的问题。")
        # 先核对编号，错误请求不能触发图执行或覆盖已保存的暂停状态。
        question = snapshot.values.get("waiting_question")
        if not question or question["question_id"] != question_id:
            raise ValueError("问题编号与当前等待的问题不一致。")
        config["recursion_limit"] = max(25, snapshot.values["max_attempts"] * 12 + snapshot.values["max_pages"] * 2 + 4)
        return cast(ResearchState, await self._graph.ainvoke(
            Command(resume={"question_id": question_id, "answer": answer}), config=config))

    async def get_pending_question(self, *, thread_id: str) -> dict | None:
        """查询本实例中真正处于暂停状态的问题；不存在或未暂停时返回None。"""
        if not thread_id.strip():
            raise ValueError("任务编号不能为空。")
        snapshot = await self._graph.aget_state({"configurable": {"thread_id": thread_id}})
        if "ask" not in snapshot.next:
            return None
        return snapshot.values.get("waiting_question")

    @staticmethod
    def _finalize(state: ResearchState) -> ResearchState:
        """图节点分配问题编号，结束规则和报告由领域模块负责。"""
        if (state["defer_user_question"] and not state["workflow_error_kind"]
                and not state["review_timeout_candidates"] and not state["summary_length_exceeded"]):
            # 只在确实收集到要点时标记上层汇总，保留无结果或搜索失败时的停止原因。
            extracted = [WebSummaryPoint.model_validate(point)
                         for page in state["page_extractions"] for point in page["points"]]
            if extracted:
                summary = WebResearchSummary(points=extracted, gaps=[], issues=[], follow_links=[])
                source_ids = {source for point in extracted for source in point.candidate_ids}
                state = state.copy()
                state["summary"] = summary.model_dump()
                state["effective_count"] = len(source_ids)
                state["needs_summary"] = False
                state["summary_deferred"] = True
                logger.info("event=research_summary_deferred pages=%d points=%d",
                            len(state["page_extractions"]), len(extracted))
        return finalize_research(state, question_id=uuid4().hex)

    # 保持已有Python调用入口；实现与工作流编排分离。
    apply_user_decision = staticmethod(apply_research_decision)
