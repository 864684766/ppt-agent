"""网页分段发生模型服务故障时，验证重试及已完成资料的交付。"""

from unittest.mock import Mock

import httpx2
import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain_openai.chat_models.base import OpenAIAPIError
from openai import InternalServerError

from agents.materials.file_extraction_agent import FileExtractionAgent
from agents.materials.material_summary_agent import MaterialSummaryAgent
from agents.materials.request_analysis_agent import RequestAnalysisAgent
from agents.web.webpage_extraction_agent import WebpageExtractionAgent
from models.materials.material_summary import MaterialMergedPoint, MaterialSummary
from models.materials.request_analysis import RequestAnalysis, RequestAnalysisResult
from models.outlines.presentation_outline import OutlineBullet, OutlineSlide, PresentationOutline
from models.web.web_research_summary import WebPageExtraction, WebSummaryPoint
from workflows.materials.material_collection_workflow import MaterialCollectionWorkflow
from workflows.web.web_research_workflow import WebResearchWorkflow


def server_error() -> OpenAIAPIError:
    """模拟 LangChain 对供应商 500 错误的包装。"""
    response = httpx2.Response(500, request=httpx2.Request("POST", "https://example.org"))
    cause = InternalServerError("server error", response=response, body=None)
    error = OpenAIAPIError(message="server error", response=response, body=None)
    error.__cause__ = cause
    return error


@pytest.mark.asyncio
async def test_page_extraction_retries_server_error_once() -> None:
    model = Mock(spec=BaseChatModel)
    runnable = Mock(spec=BaseChatModel)
    model.with_structured_output.return_value = runnable
    runnable.ainvoke.side_effect = [server_error(), WebPageExtraction(
        points=[WebSummaryPoint(content="第一段事实", candidate_ids=["page"])], follow_links=[])]
    agent = WebpageExtractionAgent(model=model, prompt="提炼", retry_prompt="精简")

    result = await agent.extract_page(question="介绍主题", page={"candidate_id": "page", "links": []})

    assert runnable.ainvoke.await_count == 2
    assert result.points[0].content == "第一段事实"


@pytest.mark.asyncio
async def test_server_error_preserves_completed_segments_for_outline() -> None:
    url = "https://example.org/article"
    fetch = Mock(spec=BaseTool)
    fetch.ainvoke.return_value = {"requested_url": url, "final_url": url, "title": "资料",
        "text": "甲" * 6001, "returned_chars": 6001, "extracted_chars": 6001,
        "truncated": False, "fetched_at": "2026-11-27T00:00:00Z", "links": []}
    extraction = Mock(spec=WebpageExtractionAgent)

    async def extract(*, question: str, page: dict) -> WebPageExtraction:
        if page["segment_index"] == 2:
            raise server_error()
        return WebPageExtraction(points=[WebSummaryPoint(content=f"第{page['segment_index']}段事实",
            candidate_ids=[page["candidate_id"]])], follow_links=[])

    extraction.extract_page.side_effect = extract
    web = WebResearchWorkflow(query_agent=Mock(), review_agent=Mock(), fetch_tool=fetch,
        webpage_extraction_agent=extraction, material_summary_agent=Mock(spec=MaterialSummaryAgent),
        max_pages=1, extraction_concurrency=3)
    request = Mock(spec=RequestAnalysisAgent)
    request.analyze.return_value = RequestAnalysisResult(status="completed", error_code=None, message="完成",
        plan=RequestAnalysis(source_mode="web", execution_order="single", needs_clarification=False,
                             clarification=None, reason="使用网页"))
    summary = Mock(spec=MaterialSummaryAgent)

    async def summarize(*, question: str, points: list, **kwargs: object) -> MaterialSummary:
        bullets = [OutlineBullet(content=p.content, point_ids=[p.point_id]) for p in points]
        return MaterialSummary(points=[MaterialMergedPoint(content=b.content, point_ids=b.point_ids) for b in bullets],
            issues=[], outline=PresentationOutline(title="部分资料", slides=[
                OutlineSlide(role="content", title="已完成的内容", bullets=bullets)]))

    summary.summarize.side_effect = summarize
    workflow = MaterialCollectionWorkflow(request_agent=request, web_workflow=web,
        file_agent=Mock(spec=FileExtractionAgent), summary_agent=summary)
    result = await workflow.run(thread_id="partial-server-error", question=f"介绍{url}")

    assert [point["content"] for point in result["summary_inputs"]] == ["第1段事实", "第3段事实"]
    assert result["outline"] is not None
    assert result["report"] is not None and result["report"]["web"] is not None
    assert result["report"]["web"]["source_count"] == 1
    assert "模型服务返回错误" in result["report"]["web"]["issues"][0]["message"]

