"""编排网页、文件、汇总及人工决定；不负责HTTP或资源创建。"""

from uuid import uuid4
import asyncio
import logging
from collections.abc import Set
from typing import cast

from langchain_core.runnables import RunnableConfig
from langchain_core.callbacks import BaseCallbackHandler
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from agents.materials.file_extraction_agent import FileExtractionAgent
from agents.materials.material_summary_agent import MaterialSummaryAgent, MaterialSummaryOutputError
from agents.materials.request_analysis_agent import RequestAnalysisAgent
from langchain_openai.chat_models.base import OpenAIConnectionError, OpenAITimeoutError
from openai import LengthFinishReasonError
from diagnostics.operation_logging import log_operation, safe_error_location
from domain.materials.material_outline_draft import draft_from_material_points
from domain.materials.material_summary_inputs import file_summary_points, web_summary_points
from domain.web.provided_web_addresses import provided_web_candidates
from models.interaction.user_question import UserQuestion
from models.materials.file_extraction import FileExtraction
from models.materials.material_collection_state import MaterialCollectionState
from models.materials.material_summary import MaterialInputPoint
from workflows.interaction.ask_user import ask_user
from workflows.web.web_research_workflow import WebResearchWorkflow
from workflows.web.research_progress import notify_progress

logger = logging.getLogger(__name__)


class PreviousMaterialTaskNotFound(ValueError):
    """上一轮任务不存在，或尚未形成可供续接的结果。"""


class MaterialCollectionWorkflow:
    """同一实例管理内存检查点；调用方管理模型、网络连接和实例生命周期。"""

    def __init__(self, *, request_agent: RequestAnalysisAgent, web_workflow: WebResearchWorkflow, file_agent: FileExtractionAgent,
                 summary_agent: MaterialSummaryAgent, target_count: int = 5) -> None:
        if not 1 <= target_count <= 20:
            raise ValueError("目标来源数须为1至20。")
        self._web = web_workflow
        self._request = request_agent
        self._file = file_agent
        self._summary = summary_agent
        self._target_count = target_count
        graph = StateGraph(MaterialCollectionState)
        graph.add_node("analyze", self._analyze)
        graph.add_node("parallel", self._collect_parallel)
        graph.add_node("web", self._collect_web)
        graph.add_node("file", self._extract_file)
        graph.add_node("summarize", self._summarize)
        graph.add_node("finalize", self._finalize)
        graph.add_node("ask", self._ask)
        graph.add_edge(START, "analyze")
        graph.add_conditional_edges("analyze", self._route_analysis)
        graph.add_edge("web", "summarize")
        graph.add_edge("parallel", "summarize")
        graph.add_conditional_edges("file", self._route_after_file)
        graph.add_edge("summarize", "finalize")
        graph.add_conditional_edges("finalize", self._route_finalized)
        graph.add_conditional_edges("ask", self._route_answer)
        self._graph = graph.compile(checkpointer=InMemorySaver())

    @log_operation("workflow.material_collection")
    async def run(self, *, thread_id: str, question: str, file_name: str | None = None,
                  file_content: bytes | None = None, allow_web: bool | None = None,
                  callbacks: list[BaseCallbackHandler] | None = None,
                  previous_task_id: str | None = None) -> MaterialCollectionState:
        """收集一轮资料。指定上一轮时，沿用提炼要点和来源并创建新检查点。"""
        if not thread_id.strip() or not question.strip():
            raise ValueError("任务编号和用户问题不能为空。")
        if (file_name is None) != (file_content is None) or (file_name is not None and not file_name.strip()):
            raise ValueError("附件文件名和字节必须同时提供。")
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        if callbacks:
            config["callbacks"] = callbacks
        if (await self._graph.aget_state(config)).values:
            raise ValueError("任务编号已存在。")
        previous = await self._previous_materials(previous_task_id) if previous_task_id else {}
        file_sources = dict(previous.get("file_sources", {}))
        source_id = None
        if file_name is not None:
            source_id = "uploaded_file" if not file_sources else f"uploaded_file_{thread_id}"
            file_sources[source_id] = file_name
        state: MaterialCollectionState = {"question": question, "allow_web": allow_web, "analysis": None, "question_kind": None, "use_current": False,
            "prior_topic": previous.get("prior_topic", ""), "prior_inputs": previous.get("prior_inputs", []),
            "prior_pages": previous.get("prior_pages", []), "file_sources": file_sources,
            "file_source_id": source_id,
            "file_name": file_name, "file_content": file_content,
            "target_count": self._target_count, "web": None, "file": None, "summary": None,
            "summary_inputs": [], "outline": None, "outline_error": None,
            "status": "running", "message": "", "report": None, "waiting_question": None}
        try:
            # 复制图的返回状态，避免清理内部字段时修改图返回的原对象。
            # LangGraph 的泛型存根未保留此图的 TypedDict 输入类型。
            result = dict(await self._graph.ainvoke(state, config=config))  # type: ignore[arg-type]
        except Exception as error:
            # 图故障返回安全报告；保留检查点，取消不在Exception内，不转成成功。
            logger.error("event=material_collection_failed error_location=%s", safe_error_location(error))
            snapshot = await self._graph.aget_state(config)
            result = dict(snapshot.values or state)
            result.update(status="interrupted", message="资料整理发生错误，请检查服务日志。",
                          waiting_question=None, file_content=None)
            web = result.get("web")
            file = result.get("file")
            result["report"] = {"web": web.get("report") if web else None,
                                "file": file.get("report") if file else None,
                                "source_count": None, "target_source_count": self._target_count, "issues": []}
        result.pop("__interrupt__", None)
        # 不向调用方暴露附件字节；暂停后的检查点仍保留原始文件供恢复使用。
        result["file_content"] = None
        return cast(MaterialCollectionState, result)

    async def _previous_materials(self, task_id: str) -> dict:
        """从检查点复制资料。等待澄清或补充的轮次也可以接收新一轮消息。"""
        snapshot = await self._graph.aget_state({"configurable": {"thread_id": task_id}})
        previous = snapshot.values
        if previous.get("status") not in {"completed", "interrupted", "awaiting_user"}:
            raise PreviousMaterialTaskNotFound
        pages = {page["candidate_id"]: page for page in previous.get("prior_pages", [])}
        pages.update({page["candidate_id"]: page for page in (previous.get("web") or {}).get("pages", [])})
        topic = previous.get("prior_topic") or previous["question"]
        return {"prior_topic": topic, "prior_inputs": previous.get("summary_inputs") or previous.get("prior_inputs", []),
                "prior_pages": list(pages.values()), "file_sources": previous.get("file_sources", {})}

    @staticmethod
    def _turn_question(state: MaterialCollectionState) -> str:
        """保留前轮主题，续轮新增的要求排在最后。"""
        previous = state["prior_topic"]
        if not previous:
            return state["question"]
        return f"原始主题：{previous}\n本轮用户要求：{state['question']}"

    async def _analyze(self, state: MaterialCollectionState) -> dict:
        """先判断需求；分析失败直接中断，不进入资料收集。"""
        notify_progress("analyze")
        outcome = await self._request.analyze(message=self._turn_question(state), has_file=state["file_name"] is not None,
                                              allow_web=state["allow_web"])
        data = outcome.model_dump()
        if outcome.status != "completed" or outcome.plan is None:
            return {"analysis": data, "status": "interrupted", "message": outcome.message, "waiting_question": None}
        plan = outcome.plan
        if plan.needs_clarification:
            question = {"question_id": uuid4().hex, "question": plan.clarification, "reason": plan.reason,
                        "options": [], "allow_free_text": True}
            return {"analysis": data, "status": "awaiting_user", "message": "需要补充需求。",
                    "question_kind": "clarification", "waiting_question": question}
        return {"analysis": data, "status": "running", "waiting_question": None, "question_kind": None}

    @staticmethod
    def _route_analysis(state: MaterialCollectionState) -> str:
        """失败结束；需澄清先询问；否则按来源和顺序选择节点。"""
        if state["status"] == "interrupted":
            return END
        if state["waiting_question"]:
            return "ask"
        analysis = state["analysis"]
        if not analysis or not analysis.get("plan"):
            raise ValueError("需求分析未生成可执行计划。")
        plan = analysis["plan"]
        if plan["source_mode"] == "web":
            return "web"
        if plan["source_mode"] == "file" or plan["execution_order"] == "file_then_web":
            return "file"
        return "parallel"

    @staticmethod
    def _route_after_file(state: MaterialCollectionState) -> str:
        """仅文件直接汇总；先文件后网页必须在文件成功后才搜索。"""
        file = state["file"]
        if state["status"] == "interrupted" or not file or file["status"] != "completed":
            return "summarize"
        analysis = state["analysis"]
        if not analysis or not analysis.get("plan"):
            raise ValueError("需求分析未生成可执行计划。")
        if analysis["plan"]["execution_order"] == "file_then_web":
            return "web"
        return "summarize"

    async def _collect_parallel(self, state: MaterialCollectionState, config: RunnableConfig) -> dict:
        """并发收集两个独立来源，等待两者结束后汇总。"""
        web, file = await asyncio.gather(self._collect_web(state, config), self._extract_file(state))
        result = {**web, **file}
        if web.get("status") == "interrupted" or file.get("status") == "interrupted":
            result.update(status="interrupted", message="资料处理未完成，请检查日志。")
        return result

    async def _collect_web(self, state: MaterialCollectionState, config: RunnableConfig) -> dict:
        """先收集网页，不让网页子图提前询问；子图编号独立于上层编号。"""
        task_id = config["configurable"]["thread_id"]
        try:
            # 只有本轮明确提供的地址可以触发直接读取；前轮主题仅用于搜索上下文。
            question = state["question"]
            if state["prior_topic"]:
                topic = state["prior_topic"]
                for item in provided_web_candidates(topic):
                    topic = topic.replace(item["url"], "")
                question = f"上一轮主题：{topic}\n本轮需要补充：{question}"
            file = state["file"]
            analysis = state["analysis"]
            if file and analysis and analysis.get("plan") and analysis["plan"]["execution_order"] == "file_then_web":
                points = file.get("points", [])
                if not points:
                    return {"status": "interrupted", "message": "文件未提炼出可用于搜索的内容。"}
                file_context = "\n".join(item["content"] for item in points)[:4000]
                question += "\n请根据以下文件要点确定搜索主题：\n" + file_context
            web = await self._web.run(thread_id=f"material-web-{task_id}", question=question,
                                      target_count=state["target_count"], defer_user_question=True)
            return {"web": web}
        except Exception as error:
            logger.error("event=material_web_failed error_location=%s", safe_error_location(error))
            return {"status": "interrupted", "message": "网页资料处理失败，请检查日志。"}

    async def _extract_file(self, state: MaterialCollectionState) -> dict:
        """按选定分支提炼文件；并行分支与网页独立执行。"""
        file_name = state["file_name"]
        if file_name is None:
            return {}
        notify_progress("file")
        try:
            result = await self._file.extract_file(question=state["question"], file_name=file_name,
                                                   content=state["file_content"] or b"")
            return {"file": result.model_dump(mode="json"), "file_content": None}
        except Exception as error:
            logger.error("event=material_file_failed error_location=%s", safe_error_location(error))
            return {"status": "interrupted", "message": "文件提炼失败，请检查日志。", "file_content": None}

    async def _summarize(self, state: MaterialCollectionState) -> dict:
        """合并跨轮要点并生成当轮大纲，来源目标与获取故障记入报告。"""
        web = state["web"]
        file = FileExtraction.model_validate(state["file"]) if state["file"] else None
        points = self._collected_points(state, file)
        partial_inputs = [item.model_dump() for item in points]
        if not points:
            if state["status"] == "interrupted":
                return {"summary_inputs": []}
            if web and (web["status"] == "interrupted" or web["stop_reason"] == "search_failed" or web["unreviewed"]):
                return {"status": "interrupted", "message": web["message"], "summary_inputs": []}
            if file and file.status != "completed":
                return {"status": "interrupted", "message": "文件提炼未完成，暂时没有可编排的要点。", "summary_inputs": []}
            return {"summary_inputs": []}
        notify_progress("summarize")
        try:
            summary = await self._summary.summarize(question=self._turn_question(state), points=points,
                final=True, target_count=self._source_target(state), use_current=state["use_current"])
        except Exception as error:
            logger.error("event=material_summary_failed error_location=%s", safe_error_location(error))
            code = ("model_timeout" if isinstance(error, (OpenAITimeoutError, TimeoutError)) else
                    "model_connection" if isinstance(error, OpenAIConnectionError) else
                    "output_too_long" if isinstance(error, LengthFinishReasonError) else "generation_failed")
            if code == "generation_failed" and not isinstance(error, MaterialSummaryOutputError):
                return {"status": "interrupted", "message": "资料汇总和大纲生成未完成，已保留原始提炼要点。",
                        "outline_error": code, "summary_inputs": partial_inputs}
            summary = draft_from_material_points(points)
            if summary.outline is None:
                return {"status": "interrupted", "message": "资料汇总未完成，暂无可编排的要点。",
                        "outline_error": code, "summary_inputs": partial_inputs}
            return {"summary": summary.model_dump(exclude={"outline"}), "outline": summary.outline.model_dump(),
                    "outline_error": code, "summary_inputs": partial_inputs}
        if summary.outline is None and summary.points:
            # 模型确认了可用内容但没有分页时，从其选出的依据组织草稿，保留缺口。
            selected = {point_id for point in summary.points for point_id in point.point_ids}
            draft = draft_from_material_points([point for point in points if point.point_id in selected])
            return {"summary": summary.model_dump(exclude={"outline"}), "outline": draft.outline.model_dump() if draft.outline else None,
                    "outline_error": "generation_failed", "summary_inputs": partial_inputs}
        return {"summary": summary.model_dump(exclude={"outline"}), "outline": summary.outline.model_dump() if summary.outline else None,
                "outline_error": None, "summary_inputs": partial_inputs}

    @staticmethod
    def _collected_points(state: MaterialCollectionState, file: FileExtraction | None) -> list[MaterialInputPoint]:
        """沿用旧编号。同一网页跨轮重新提炼时追加新要点，保留不同内容。"""
        points = [MaterialInputPoint.model_validate(item) for item in state["prior_inputs"]]
        web = state["web"]
        additions = web_summary_points(extractions=web["page_extractions"]) if web else []
        if file and state["file_source_id"]:
            additions.extend(file_summary_points(extraction=file, source_id=state["file_source_id"], allow_partial=True))
        if not points:
            return additions
        used_ids = {point.point_id for point in points}
        seen = {(ref.kind, ref.source_id, point.content) for point in points for ref in point.references}
        for point in additions:
            reference = point.references[0]
            key = (reference.kind, reference.source_id, point.content)
            if point.references[0].kind == "web" and key in seen:
                continue
            if point.point_id in used_ids:
                point.point_id += f":{len(points) + 1}"
            points.append(point)
            used_ids.add(point.point_id)
            seen.add(key)
        return points

    @staticmethod
    def _source_target(state: MaterialCollectionState) -> int:
        """只使用指定文件或网页时，以请求提供的资料数为目标。"""
        analysis = state["analysis"] or {}
        plan = analysis.get("plan") or {}
        if plan.get("source_mode") == "file":
            return 1
        if state["web"] and state["web"].get("provided_urls_only"):
            supplied = provided_web_candidates(state["question"])
            return max(1, len(supplied)) + int(plan.get("source_mode") == "both")
        return state["target_count"]

    @staticmethod
    def _covers_requested_sources(state: MaterialCollectionState, sources: Set[tuple[str, str]]) -> bool:
        """明确指定的文件及网址应各有引用，补充链接不能替代指定资料。"""
        plan = (state["analysis"] or {}).get("plan") or {}
        mode = plan.get("source_mode")
        if mode in {"file", "both"} and state["file_source_id"] and ("file", state["file_source_id"]) not in sources:
            return False
        if mode == "both" and not any(kind == "web" for kind, _ in sources):
            return False
        web = state["web"]
        if not web or not web.get("provided_urls_only"):
            return True
        requested = {item["url"] for item in provided_web_candidates(state["question"])}
        cited_urls = {url for page in web["pages"] if ("web", page["candidate_id"]) in sources
                      for url in (page["requested_url"], page["final_url"])}
        return requested <= cited_urls

    @staticmethod
    def _finalize(state: MaterialCollectionState) -> dict:
        """统一生成客观报告；缺口由模型判断，来源数由代码统计。"""
        summary = state["summary"]
        referenced = {p for item in (summary or {}).get("points", []) for p in item["point_ids"]}
        sources = {(ref["kind"], ref["source_id"]) for item in state["summary_inputs"]
                   if item["point_id"] in referenced for ref in item["references"]}
        issues = list((summary or {}).get("issues", []))
        target = MaterialCollectionWorkflow._source_target(state)
        web = state["web"]
        file = state["file"]
        web_report = web.get("report") if web else None
        if web_report:
            issues.extend({"type": "content_gap", "message": issue["message"], "point_ids": []}
                          for issue in web_report["issues"]
                          if issue["type"] in {"followup_unread", "webpage_read_failed", "search_failed",
                                              "search_partially_failed", "workflow_failed", "review_timeout", "review_unfinished"})
        if file and file.get("report") and file["status"] != "completed":
            issues.append({"type": "content_gap", "message": file["report"]["message"], "point_ids": []})
        if state["status"] == "interrupted" and state["outline"]:
            issues.append({"type": "content_gap", "message": state["message"], "point_ids": []})
        if state["outline"] and not MaterialCollectionWorkflow._covers_requested_sources(state, sources):
            issues.append({"type": "source_requirement", "message": "本版大纲尚未覆盖全部指定资料。", "point_ids": []})
        report = {"web": web["report"] if web else None,
                  "file": file["report"] if file else None,
                  "source_count": len(sources) if state["outline"] or state["status"] != "interrupted" else None,
                  "target_source_count": target, "issues": issues}
        if state["outline"]:
            if state["outline_error"]:
                reason = {"model_timeout": "超时", "model_connection": "连接失败",
                          "output_too_long": "输出超限"}.get(state["outline_error"], "失败")
                return {"status": "interrupted", "message": f"模型整理{reason}，已按提炼顺序生成带来源的草稿。",
                        "report": report, "waiting_question": None}
            message = ("已根据现有资料生成大纲，可继续补充完善。"
                       if issues or len(sources) < target else "大纲已生成。")
            return {"status": "completed", "message": message, "report": report, "waiting_question": None}
        if state["status"] == "interrupted":
            return {"report": report, "waiting_question": None}
        options = ["provide_materials"]
        if summary and summary["points"]:
            options.append("use_current")
        options.append("end_conversation")
        details = ["本轮没有形成可用大纲。"]
        details.extend(item["message"] for item in issues[:3])
        question = {"question_id": uuid4().hex, "question": "本轮暂无可用大纲，可以继续补充资料。",
                    "reason": " ".join(details)[:1000],
                    "options": options, "allow_free_text": False}
        return {"status": "awaiting_user", "message": "本轮暂无可用大纲，可在下一轮补充资料。", "report": report, "question_kind": "materials", "outline": None,
                "waiting_question": question}

    @staticmethod
    def _route_finalized(state: MaterialCollectionState) -> str:
        """资料不足时询问；充分或中断则结束。"""
        if state["waiting_question"]:
            return "ask"
        return END

    @staticmethod
    def _route_answer(state: MaterialCollectionState) -> str:
        """澄清后重新分析；选择使用现有资料后重新汇总并生成大纲。"""
        if state["status"] == "running":
            return "summarize" if state["use_current"] else "analyze"
        return END

    @staticmethod
    def _ask(state: MaterialCollectionState) -> dict:
        data = state["waiting_question"]
        if not data:
            raise ValueError("没有等待回答的问题。")
        answer = ask_user(UserQuestion(**{**data, "options": tuple(data["options"])}))
        if state["question_kind"] == "clarification":
            return {"question": state["question"] + "\n用户补充：" + answer, "status": "running",
                    "waiting_question": None, "question_kind": None}
        if answer == "provide_materials":
            return {"status": "needs_materials", "message": "等待用户提供资料。", "waiting_question": None}
        if answer == "use_current":
            return {"status": "running", "use_current": True, "message": "正在按现有资料整理大纲。", "waiting_question": None}
        return {"status": "cancelled", "message": "资料不足，任务已结束。", "waiting_question": None}

    @log_operation("workflow.material_collection_answer")
    async def answer(self, *, thread_id: str, question_id: str, answer: str) -> MaterialCollectionState:
        """恢复等待中的问题；补充资料后的实际处理尚未接入。"""
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        snapshot = await self._graph.aget_state(config)
        question = snapshot.values.get("waiting_question")
        if "ask" not in snapshot.next or not question:
            raise ValueError("任务不存在或没有等待中的问题。")
        if question["question_id"] != question_id:
            raise ValueError("问题编号不匹配。")
        result = dict(await self._graph.ainvoke(Command(resume={"question_id": question_id, "answer": answer}), config=config))
        result.pop("__interrupt__", None)
        result["file_content"] = None
        return cast(MaterialCollectionState, result)
