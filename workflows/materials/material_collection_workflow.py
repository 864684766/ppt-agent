"""编排网页、文件、汇总及人工决定；不负责HTTP或资源创建。"""

from uuid import uuid4
import logging
from typing import cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from agents.materials.file_extraction_agent import FileExtractionAgent
from agents.materials.material_summary_agent import MaterialSummaryAgent
from diagnostics.operation_logging import log_operation, safe_error_location
from domain.materials.material_summary_inputs import file_summary_points, web_summary_points
from models.interaction.user_question import UserQuestion
from models.materials.file_extraction import FileExtraction
from models.materials.material_collection_state import MaterialCollectionState
from workflows.interaction.ask_user import ask_user
from workflows.web.web_research_workflow import WebResearchWorkflow

logger = logging.getLogger(__name__)


class MaterialCollectionWorkflow:
    """同一实例管理内存检查点；调用方管理模型、网络连接和实例生命周期。"""

    def __init__(self, *, web_workflow: WebResearchWorkflow, file_agent: FileExtractionAgent,
                 summary_agent: MaterialSummaryAgent, target_count: int = 5) -> None:
        if not 1 <= target_count <= 20:
            raise ValueError("目标来源数须为1至20。")
        self._web = web_workflow
        self._file = file_agent
        self._summary = summary_agent
        self._target_count = target_count
        graph = StateGraph(MaterialCollectionState)
        graph.add_node("web", self._collect_web)
        graph.add_node("file", self._extract_file)
        graph.add_node("summarize", self._summarize)
        graph.add_node("finalize", self._finalize)
        graph.add_node("ask", self._ask)
        graph.add_edge(START, "web")
        graph.add_edge("web", "file")
        graph.add_edge("file", "summarize")
        graph.add_edge("summarize", "finalize")
        graph.add_conditional_edges("finalize", lambda s: "ask" if s["waiting_question"] else END)
        graph.add_edge("ask", END)
        self._graph = graph.compile(checkpointer=InMemorySaver())

    @log_operation("workflow.material_collection")
    async def run(self, *, thread_id: str, question: str, file_name: str | None = None,
                  file_content: bytes | None = None) -> MaterialCollectionState:
        """启动联网收集，可选一份附件；文件字节仅保存在本实例内存检查点。"""
        if not thread_id.strip() or not question.strip():
            raise ValueError("任务编号和用户问题不能为空。")
        if (file_name is None) != (file_content is None) or (file_name is not None and not file_name.strip()):
            raise ValueError("附件文件名和字节必须同时提供。")
        config = {"configurable": {"thread_id": thread_id}}
        if (await self._graph.aget_state(config)).values:
            raise ValueError("任务编号已存在。")
        state: MaterialCollectionState = {"question": question, "file_name": file_name, "file_content": file_content,
            "target_count": self._target_count, "web": None, "file": None, "summary": None,
            "summary_inputs": [], "status": "running", "message": "", "report": None, "waiting_question": None}
        try:
            result = await self._graph.ainvoke(state, config=config)
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
        return cast(MaterialCollectionState, result)

    async def _collect_web(self, state: MaterialCollectionState, config: RunnableConfig) -> dict:
        """先收集网页，不让网页子图提前询问；子图编号独立于上层编号。"""
        task_id = config["configurable"]["thread_id"]
        try:
            web = await self._web.run(thread_id=f"material-web-{task_id}", question=state["question"],
                                      target_count=state["target_count"], defer_user_question=True)
            return {"web": web}
        except Exception as error:
            logger.error("event=material_web_failed error_location=%s", safe_error_location(error))
            return {"status": "interrupted", "message": "网页资料处理失败，请检查日志。"}

    async def _extract_file(self, state: MaterialCollectionState) -> dict:
        """网页阶段失败时仍处理文件；附件不参与时不调用文件Agent。"""
        if state["file_name"] is None:
            return {}
        try:
            result = await self._file.extract_file(question=state["question"], file_name=state["file_name"],
                                                   content=state["file_content"] or b"")
            return {"file": result.model_dump(mode="json"), "file_content": None}
        except Exception as error:
            logger.error("event=material_file_failed error_location=%s", safe_error_location(error))
            return {"status": "interrupted", "message": "文件提炼失败，请检查日志。", "file_content": None}

    async def _summarize(self, state: MaterialCollectionState) -> dict:
        """仅完整阶段可进入汇总；故障与资料不足分开处理。"""
        web = state["web"]
        file = FileExtraction.model_validate(state["file"]) if state["file"] else None
        if state["status"] == "interrupted":
            return {}
        if not web or web["status"] == "interrupted" or web["stop_reason"] == "search_failed" or web["unreviewed"]:
            return {"status": "interrupted", "message": "网页资料处理未完成；已有结果已保留。"}
        if file and file.status != "completed":
            return {"status": "interrupted", "message": "文件处理未完成；已有结果已保留。"}
        points = web_summary_points(extractions=web["page_extractions"])
        if file:
            points.extend(file_summary_points(extraction=file, source_id="uploaded_file"))
        if not points:
            return {"summary_inputs": []}
        try:
            summary = await self._summary.summarize(question=state["question"], points=points)
        except Exception as error:
            logger.error("event=material_summary_failed error_location=%s", safe_error_location(error))
            return {"status": "interrupted", "message": "资料汇总未完成，请检查日志。",
                    "summary_inputs": [item.model_dump() for item in points]}
        return {"summary": summary.model_dump(), "summary_inputs": [item.model_dump() for item in points]}

    @staticmethod
    def _finalize(state: MaterialCollectionState) -> dict:
        """统一生成客观报告；缺口由模型判断，来源数由代码统计。"""
        summary = state["summary"]
        referenced = {p for item in (summary or {}).get("points", []) for p in item["point_ids"]}
        sources = {(ref["kind"], ref["source_id"]) for item in state["summary_inputs"]
                   if item["point_id"] in referenced for ref in item["references"]}
        issues = (summary or {}).get("issues", [])
        report = {"web": state["web"]["report"] if state["web"] else None,
                  "file": state["file"]["report"] if state["file"] else None,
                  "source_count": len(sources), "target_source_count": state["target_count"], "issues": issues}
        if state["status"] == "interrupted":
            return {"report": report, "waiting_question": None}
        if summary and summary["points"] and len(sources) >= state["target_count"] and not issues:
            return {"status": "completed", "message": "资料整理已达到当前条件。", "report": report}
        options = ["provide_materials"]
        if summary and summary["points"]:
            options.append("use_current")
        options.append("end_conversation")
        details = [f"已引用{len(sources)}个来源，目标为{state['target_count']}个。"]
        details.extend(item["message"] for item in issues[:3])
        if summary and summary["points"]:
            details.append("使用现有资料时PPT可能少于8–12页。")
        question = {"question_id": uuid4().hex, "question": "资料不足，请选择补充资料或其他可用操作。",
                    "reason": " ".join(details)[:1000],
                    "options": options, "allow_free_text": False}
        return {"status": "awaiting_user", "message": "资料不足，等待用户决定。", "report": report,
                "waiting_question": question}

    @staticmethod
    def _ask(state: MaterialCollectionState) -> dict:
        data = state["waiting_question"]
        if not data:
            raise ValueError("没有等待回答的问题。")
        answer = ask_user(UserQuestion(**{**data, "options": tuple(data["options"])}))
        if answer == "provide_materials":
            return {"status": "needs_materials", "message": "等待用户提供资料。", "waiting_question": None}
        if answer == "use_current":
            return {"status": "completed", "message": "按现有资料继续，PPT可能少于8–12页。", "waiting_question": None}
        return {"status": "cancelled", "message": "资料不足，任务已结束。", "waiting_question": None}

    @log_operation("workflow.material_collection_answer")
    async def answer(self, *, thread_id: str, question_id: str, answer: str) -> MaterialCollectionState:
        """恢复等待中的问题；补充资料后的实际处理尚未接入。"""
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = await self._graph.aget_state(config)
        if "ask" not in snapshot.next or not snapshot.values.get("waiting_question"):
            raise ValueError("任务不存在或没有等待中的问题。")
        if snapshot.values["waiting_question"]["question_id"] != question_id:
            raise ValueError("问题编号不匹配。")
        result = await self._graph.ainvoke(Command(resume={"question_id": question_id, "answer": answer}), config=config)
        return cast(MaterialCollectionState, result)
