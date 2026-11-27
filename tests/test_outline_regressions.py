"""离线验证大纲引用还原与模型故障后的资料草稿。"""

import json
from unittest.mock import Mock

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool, ToolException
import pytest

from agents.materials.file_extraction_agent import FileExtractionAgent
from agents.materials.material_summary_agent import MaterialSummaryAgent
from agents.materials.request_analysis_agent import RequestAnalysisAgent
from api.chat.chat_response_builder import build_chat_response
from config.settings import PROJECT_ROOT
from domain.web.provided_web_addresses import provided_web_candidates
from models.chat.chat_request import ChatAttachmentInput, ChatSubmission
from models.materials.file_extraction import FileExtraction, FileExtractionPoint
from models.materials.material_summary import (
    MaterialInputPoint,
    MaterialMergedPoint,
    MaterialOutlineDraft,
    MaterialOutlineSection,
    MaterialReference,
    MaterialSummary,
)
from models.materials.request_analysis import RequestAnalysis, RequestAnalysisResult
from models.outlines.presentation_outline import OutlineBullet, OutlineSlide, PresentationOutline
from models.web.web_research_summary import WebPageExtraction, WebSummaryPoint
from agents.web.webpage_extraction_agent import WebpageExtractionAgent
from workflows.materials.material_collection_workflow import MaterialCollectionWorkflow
from workflows.web.web_research_workflow import WebResearchWorkflow


@pytest.mark.asyncio
async def test_model_outline_restores_a_point_cited_on_multiple_pages() -> None:
    reference = MaterialReference(kind="web", source_id="original_web_id")
    point = MaterialInputPoint(point_id="web:original_web_id:1", content="资料中的事实。", references=[reference])
    model = Mock(spec=BaseChatModel)
    summary_model = Mock(spec=BaseChatModel)
    outline_model = Mock(spec=BaseChatModel)
    model_outputs = {MaterialSummary: summary_model, MaterialOutlineDraft: outline_model}
    model.with_structured_output.side_effect = lambda schema, **kwargs: model_outputs[schema]
    outline_model.ainvoke.return_value = MaterialOutlineDraft.model_validate({
        "title": "资料大纲",
        "sections": [{"title": "背景", "keys": ["k1"]}, {"title": "结论", "keys": ["k1"]}],
        "issues": [{"type": "content_gap", "message": "缺少案例。", "point_ids": ["p1"]}],
    })
    agent = MaterialSummaryAgent(
        model=model,
        prompt=(PROJECT_ROOT / "prompts/materials/material_summary.md").read_text(encoding="utf-8"),
        retry_prompt=(PROJECT_ROOT / "prompts/materials/material_summary_retry.md").read_text(encoding="utf-8"),
    )

    result = await agent.summarize(question="根据资料写一份大纲。", points=[point], final=True, target_count=1)

    summary_model.ainvoke.assert_not_awaited()
    outline_model.ainvoke.assert_awaited_once()
    prompt = outline_model.ainvoke.await_args.args[0]
    assert "original_web_id" not in prompt
    payload = json.loads(prompt.split("\n资料要点：", 1)[1])
    assert payload == [{"key": "k1", "point_ids": ["p1"], "content": point.content}]
    assert result.outline is not None
    assert [slide.bullets[0].point_ids for slide in result.outline.slides] == [[point.point_id], [point.point_id]]
    assert all(item.point_ids == [point.point_id] for item in result.points)
    assert result.issues[0].point_ids == [point.point_id]


@pytest.mark.asyncio
async def test_summarization_timeout_keeps_the_cited_file_draft_in_the_response() -> None:
    request_agent = Mock(spec=RequestAnalysisAgent)
    request_agent.analyze.return_value = RequestAnalysisResult(
        status="completed",
        plan=RequestAnalysis(source_mode="file", execution_order="single", needs_clarification=False,
                             clarification=None, reason="只用文件。"),
        error_code=None,
        message="需求分析完成。",
    )
    file_agent = Mock(spec=FileExtractionAgent)
    file_agent.extract_file.return_value = FileExtraction(
        file_name="材料.txt",
        points=[FileExtractionPoint(content="资料中的事实。", block_ids=["b000001"])],
        warnings=[], pages_without_text=[], status="completed", processed_characters=7, total_characters=7,
    )
    summary_agent = Mock(spec=MaterialSummaryAgent)
    summary_agent.summarize.side_effect = TimeoutError
    web_workflow = Mock(spec=WebResearchWorkflow)
    workflow = MaterialCollectionWorkflow(request_agent=request_agent, web_workflow=web_workflow,
                                          file_agent=file_agent, summary_agent=summary_agent, target_count=2)
    submission = ChatSubmission(message="只根据附件写PPT大纲。", attachment=ChatAttachmentInput(
        file_name="材料.txt", format="txt", content="资料中的事实。".encode(),
    ))
    attachment = submission.attachment
    assert attachment is not None
    state = await workflow.run(thread_id="file-draft", question=submission.message,
                               file_name=attachment.file_name, file_content=attachment.content)
    response = build_chat_response(submission=submission, task_id="file-draft", result=state, template=None)

    web_workflow.run.assert_not_awaited()
    summary_agent.summarize.assert_awaited_once()
    assert summary_agent.summarize.await_args.kwargs["target_count"] == 1
    assert response.status == "interrupted"
    assert response.outline_error == "model_timeout"
    assert response.waiting_question is None
    assert response.outline is not None
    assert response.summary is not None
    assert response.report is not None and response.report["source_count"] == 1
    bullet = response.outline.slides[0].bullets[0]
    assert bullet.content == "资料中的事实。"
    assert bullet.point_ids == [response.summary_inputs[0].point_id]
    assert response.summary.references_for(response.summary.points[0], response.summary_inputs) == [
        MaterialReference(kind="file", source_id="uploaded_file", block_ids=["b000001"]),
    ]


@pytest.mark.asyncio
async def test_missing_requested_page_is_reported_with_available_outline() -> None:
    first = "https://example.org/first"
    second = "https://example.org/second"
    related = "https://example.org/related"
    question = f"根据 {first} 和 {second} 制作PPT大纲。"
    requested_sources = provided_web_candidates(question)
    related_source = provided_web_candidates(related)[0]
    sources = [*requested_sources, related_source]
    request_agent = Mock(spec=RequestAnalysisAgent)
    request_agent.analyze.return_value = RequestAnalysisResult(
        status="completed",
        plan=RequestAnalysis(source_mode="web", execution_order="single", needs_clarification=False,
                             clarification=None, reason="只用指定网页。"),
        error_code=None,
        message="需求分析完成。",
    )
    web_workflow = Mock(spec=WebResearchWorkflow)
    web_workflow.run.return_value = {
        "status": "collected",
        "stop_reason": "summary_deferred",
        "provided_urls_only": True,
        "unreviewed": [],
        "report": None,
        "pages": [
            {"candidate_id": source["candidate_id"], "requested_url": source["url"],
             "final_url": source["url"], "title": source["title"], "truncated": False}
            for source in sources
        ],
        "page_extractions": [
            {"candidate_id": source["candidate_id"], "points": [] if index == 0 else [
                {"content": f"第{index + 1}份网页中的事实。", "candidate_ids": [source["candidate_id"]]},
            ]}
            for index, source in enumerate(sources)
        ],
    }
    summary_agent = Mock(spec=MaterialSummaryAgent)
    merged = [
        MaterialMergedPoint(content="网页中的事实。", point_ids=[f"web:{source['candidate_id']}:1"])
        for source in sources[1:]
    ]
    summary_agent.summarize.return_value = MaterialSummary(points=merged, issues=[], outline=PresentationOutline(
        title="已读资料", slides=[OutlineSlide(role="content", title="可用资料",
            bullets=[OutlineBullet(content=point.content, point_ids=point.point_ids) for point in merged])],
    ))
    workflow = MaterialCollectionWorkflow(request_agent=request_agent, web_workflow=web_workflow,
                                          file_agent=Mock(spec=FileExtractionAgent), summary_agent=summary_agent)

    result = await workflow.run(thread_id="requested-pages", question=question)
    response = build_chat_response(submission=ChatSubmission(message=question), task_id="requested-pages",
                                   result=result, template=None)

    assert response.status == "completed"
    assert response.outline is not None
    assert response.report is not None
    assert response.report["source_count"] == response.report["target_source_count"] == 2
    assert response.waiting_question is None
    assert "未覆盖全部指定资料" in response.report["issues"][0]["message"]


@pytest.mark.asyncio
@pytest.mark.parametrize("has_outline", [True, False], ids=["optional-gap", "essential-gap"])
async def test_outline_with_file_and_search_evidence_completes_with_both_citations(has_outline: bool) -> None:
    question = "结合附件与网上资料制作PPT大纲。"
    fact = "检索与附件均记录的事实。"
    web_id = "web_article"
    url = "https://example.org/article"
    request_agent = Mock(spec=RequestAnalysisAgent)
    request_agent.analyze.return_value = RequestAnalysisResult(
        status="completed",
        plan=RequestAnalysis(source_mode="both", execution_order="parallel", needs_clarification=False,
                             clarification=None, reason="使用附件与网页。"),
        error_code=None,
        message="需求分析完成。",
    )
    web_workflow = Mock(spec=WebResearchWorkflow)
    web_workflow.run.return_value = {
        "status": "collected", "stop_reason": "summary_deferred", "provided_urls_only": False,
        "unreviewed": [], "report": None,
        "pages": [{"candidate_id": web_id, "requested_url": url, "final_url": url,
                   "title": "检索文章", "truncated": False}],
        "page_extractions": [{"candidate_id": web_id, "points": [{"content": fact, "candidate_ids": [web_id]}]}],
    }
    file_agent = Mock(spec=FileExtractionAgent)
    file_agent.extract_file.return_value = FileExtraction(
        file_name="材料.txt", points=[FileExtractionPoint(content=fact, block_ids=["b000001"])],
        warnings=[], pages_without_text=[], status="completed",
        processed_characters=len(fact), total_characters=len(fact),
    )
    model = Mock(spec=BaseChatModel)
    summary_model = Mock(spec=BaseChatModel)
    outline_model = Mock(spec=BaseChatModel)
    model_outputs = {MaterialSummary: summary_model, MaterialOutlineDraft: outline_model}
    model.with_structured_output.side_effect = lambda schema, **kwargs: model_outputs[schema]
    issue = "资料未包含额外案例。" if has_outline else "资料缺少用户所需的核心结论。"
    outline_model.ainvoke.return_value = MaterialOutlineDraft.model_validate({
        "title": "两份资料的大纲" if has_outline else "",
        "sections": [{"title": "共有结论", "keys": ["k1"]}] if has_outline else [],
        "points": [],
        "issues": [{"type": "content_gap", "message": issue, "point_ids": ["p1"]}],
    })
    summary_agent = MaterialSummaryAgent(
        model=model,
        prompt=(PROJECT_ROOT / "prompts/materials/material_summary.md").read_text(encoding="utf-8"),
        retry_prompt=(PROJECT_ROOT / "prompts/materials/material_summary_retry.md").read_text(encoding="utf-8"),
    )
    workflow = MaterialCollectionWorkflow(request_agent=request_agent, web_workflow=web_workflow,
                                          file_agent=file_agent, summary_agent=summary_agent, target_count=2)

    state = await workflow.run(thread_id="mixed-outline", question=question,
                               file_name="材料.txt", file_content=fact.encode())
    response = build_chat_response(submission=ChatSubmission(message=question), task_id="mixed-outline",
                                   result=state, template=None)

    web_workflow.run.assert_awaited_once()
    file_agent.extract_file.assert_awaited_once()
    summary_model.ainvoke.assert_not_awaited()
    outline_model.ainvoke.assert_awaited_once()
    prompt = outline_model.ainvoke.await_args.args[0]
    assert json.loads(prompt.split("\n资料要点：", 1)[1]) == [
        {"key": "k1", "point_ids": ["p1", "p2"], "content": fact},
    ]
    assert response.outline_error is None
    assert response.report is not None
    assert response.report["target_source_count"] == 2
    assert response.report["issues"][0]["message"] == issue
    assert response.report["issues"][0]["point_ids"] == [f"web:{web_id}:1"]
    assert response.attachment_analyzed and response.sources[0].url == url
    assert response.summary is not None
    if has_outline:
        assert response.report["source_count"] == 2
        assert response.summary.references_for(response.summary.points[0], response.summary_inputs) == [
            MaterialReference(kind="web", source_id=web_id),
            MaterialReference(kind="file", source_id="uploaded_file", block_ids=["b000001"]),
        ]
        assert response.status == "completed"
        assert response.waiting_question is None
        assert response.outline is not None and response.outline.title == "两份资料的大纲"
        bullet = response.outline.slides[0].bullets[0]
        assert bullet.content == fact
        assert set(bullet.point_ids) == {f"web:{web_id}:1", "file:uploaded_file:1"}
    else:
        assert response.status == "awaiting_user"
        assert response.outline is None and response.waiting_question is not None
        assert issue in response.waiting_question.reason


@pytest.mark.asyncio
async def test_search_turns_publish_available_evidence_below_target() -> None:
    request_agent = Mock(spec=RequestAnalysisAgent)
    request_agent.analyze.return_value = RequestAnalysisResult(
        status="completed", plan=RequestAnalysis(source_mode="web", execution_order="single",
            needs_clarification=False, clarification=None, reason="联网补充资料。"),
        error_code=None, message="需求分析完成。",
    )
    web_workflow = Mock(spec=WebResearchWorkflow)
    rounds = []
    for source_id, content in [("wei", "曹魏的资料"), ("wu", "东吴的资料")]:
        url = f"https://example.org/{source_id}"
        rounds.append({
            "status": "collected", "stop_reason": "summary_deferred", "provided_urls_only": False,
            "unreviewed": [], "report": None,
            "pages": [{"candidate_id": source_id, "requested_url": url, "final_url": url,
                       "title": content, "truncated": False}],
            "page_extractions": [{"candidate_id": source_id, "points": [
                {"content": content, "candidate_ids": [source_id]},
            ]}],
        })
    web_workflow.run.side_effect = rounds
    model = Mock(spec=BaseChatModel)
    outline_model = Mock(spec=BaseChatModel)
    model.with_structured_output.return_value = outline_model
    outline_model.ainvoke.side_effect = [
        MaterialOutlineDraft(title="三国历史：曹魏", sections=[MaterialOutlineSection(title="曹魏", keys=["k1"])], issues=[]),
        MaterialOutlineDraft(title="三国历史", sections=[MaterialOutlineSection(title="曹魏", keys=["k1"]),
                                                       MaterialOutlineSection(title="东吴", keys=["k2"])], issues=[]),
    ]
    summary = MaterialSummaryAgent(model=model,
        prompt=(PROJECT_ROOT / "prompts/materials/material_summary.md").read_text(encoding="utf-8"),
        retry_prompt=(PROJECT_ROOT / "prompts/materials/material_summary_retry.md").read_text(encoding="utf-8"))
    workflow = MaterialCollectionWorkflow(request_agent=request_agent, web_workflow=web_workflow,
        file_agent=Mock(spec=FileExtractionAgent), summary_agent=summary, target_count=5)
    first = await workflow.run(thread_id="a" * 32, question="介绍三国历史")
    assert first["status"] == "completed" and first["outline"]
    assert first["report"] and first["report"]["source_count"] == 1
    followup = ChatSubmission(message="补充东吴", previous_task_id="a" * 32)
    second = await workflow.run(thread_id="b" * 32, question=followup.message,
                                previous_task_id=followup.previous_task_id)
    response = build_chat_response(submission=followup, task_id="b" * 32, result=second, template=None)
    assert response.previous_task_id == "a" * 32
    assert response.status == "completed" and response.outline is not None
    assert [source.candidate_id for source in response.sources] == ["wei", "wu"]
    assert [bullet.point_ids for slide in response.outline.slides for bullet in slide.bullets] == [
        ["web:wei:1"], ["web:wu:1"],
    ]
    assert "补充东吴" in web_workflow.run.await_args.kwargs["question"]


@pytest.mark.asyncio
async def test_empty_search_explains_webpage_timeout() -> None:
    request_agent = Mock(spec=RequestAnalysisAgent)
    request_agent.analyze.return_value = RequestAnalysisResult(
        status="completed", plan=RequestAnalysis(source_mode="web", execution_order="single",
            needs_clarification=False, clarification=None, reason="联网搜索。"),
        error_code=None, message="需求分析完成。",
    )
    web = Mock(spec=WebResearchWorkflow)
    web.run.return_value = {
        "status": "insufficient", "stop_reason": "page_limit", "provided_urls_only": False,
        "unreviewed": [], "pages": [], "page_extractions": [],
        "report": {"issues": [{"type": "webpage_read_failed", "message": "网页读取超时。"}]},
    }
    summary = Mock(spec=MaterialSummaryAgent)
    workflow = MaterialCollectionWorkflow(request_agent=request_agent, web_workflow=web,
        file_agent=Mock(spec=FileExtractionAgent), summary_agent=summary)
    state = await workflow.run(thread_id="unread-page", question="介绍三国历史")
    assert state["status"] == "awaiting_user" and state["outline"] is None
    assert state["waiting_question"] and "网页读取超时" in state["waiting_question"]["reason"]
    summary.summarize.assert_not_awaited()


@pytest.mark.asyncio
async def test_research_continues_after_first_page_fails_within_page_limit() -> None:
    first = "https://example.org/first"
    second = "https://example.org/second"
    fetch = Mock(spec=BaseTool)
    fetch.ainvoke.side_effect = [
        ToolException("网页读取超时。"),
        {"requested_url": second, "final_url": second, "title": "三国史",
         "text": "三国历史资料。", "returned_chars": 7, "extracted_chars": 7,
         "truncated": False, "fetched_at": "2026-11-27T00:00:00Z", "links": []},
    ]
    extraction = Mock(spec=WebpageExtractionAgent)

    async def extract(*, question: str, page: dict) -> WebPageExtraction:
        return WebPageExtraction(points=[WebSummaryPoint(content="三国历史资料。",
                                                        candidate_ids=[page["candidate_id"]])], follow_links=[])

    extraction.extract_page.side_effect = extract
    workflow = WebResearchWorkflow(query_agent=Mock(), review_agent=Mock(), fetch_tool=fetch,
        webpage_extraction_agent=extraction, material_summary_agent=Mock(spec=MaterialSummaryAgent),
        max_pages=2, target_count=1)
    result = await workflow.run(thread_id="page-retry", question=f"介绍 {first} 和 {second}",
                                defer_user_question=True)
    assert fetch.ainvoke.await_count == 2
    assert result["read_failures"][0]["url"] == first
    assert result["page_extractions"][0]["points"][0]["content"] == "三国历史资料。"
    assert result["report"] and result["report"]["has_usable_content"]
