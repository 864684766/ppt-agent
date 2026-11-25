"""在应用生命周期内组装网页研究流程；连接与检查点由宿主持有。"""

import asyncio
from contextlib import AsyncExitStack

import httpx

from agents.web.research_query_agent import ResearchQueryAgent
from agents.web.research_review_agent import ResearchReviewAgent
from agents.web.webpage_extraction_agent import WebpageExtractionAgent
from agents.materials.material_summary_agent import MaterialSummaryAgent
from agents.materials.file_extraction_agent import FileExtractionAgent
from agents.materials.request_analysis_agent import RequestAnalysisAgent
from config.settings import PROJECT_ROOT, Settings
from domain.documents.document_file_reader import DocumentFileReader
from integrations.documents.document_reader_registry import create_document_readers
from integrations.ocr.rapidocr_text_recognizer import RapidOcrTextRecognizer
from integrations.templates.pdfium_page_renderer import PdfiumPageRenderer
from models.documents.document_content import DocumentReadLimits
from workflows.materials.material_collection_workflow import MaterialCollectionWorkflow
from integrations.llm.langchain_model_factory import create_langchain_model
from integrations.web.http_webpage_reader import HttpWebpageReader
from integrations.web.searxng_search_client import SearxngSearchClient
from integrations.web.webpage_http_client import create_webpage_http_client
from tools.web.fetch_webpage_tool import create_fetch_webpage_tool
from tools.web.search_web_tool import create_search_web_tool
from workflows.web.web_research_workflow import WebResearchWorkflow


class WebResearchRuntime:
    """首次请求时初始化并复用工作流；连接和内存检查点随应用关闭而释放。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = asyncio.Lock()
        self._resources: AsyncExitStack | None = None
        self._workflow: WebResearchWorkflow | None = None
        self._material_workflow: MaterialCollectionWorkflow | None = None

    @property
    def show_thinking(self) -> bool:
        """是否允许当前运行时向SSE请求暴露标准推理块。"""
        return self._settings.llm_show_thinking

    async def get_workflow(self) -> WebResearchWorkflow:
        """并发请求只创建一次工作流；初始化失败时关闭已创建的资源。"""
        async with self._lock:
            if self._workflow is None:
                async with AsyncExitStack() as resources:
                    model_http = await resources.enter_async_context(httpx.AsyncClient())
                    search_http = await resources.enter_async_context(httpx.AsyncClient(trust_env=False))
                    page_http = await resources.enter_async_context(
                        create_webpage_http_client(verify_tls=self._settings.webpage_tls_verify))
                    workflow, material_workflow = self._create_workflow(model_http, search_http, page_http)
                    self._resources = resources.pop_all()
                    self._workflow = workflow
                    self._material_workflow = material_workflow
            return self._workflow

    async def get_material_workflow(self) -> MaterialCollectionWorkflow:
        """复用应用生命周期内的资料图及其内存检查点。"""
        await self.get_workflow()
        assert self._material_workflow is not None
        return self._material_workflow

    def _create_workflow(self, model_http: httpx.AsyncClient, search_http: httpx.AsyncClient,
                         page_http: httpx.AsyncClient) -> tuple[WebResearchWorkflow, MaterialCollectionWorkflow]:
        """集中注入配置、模型和工具；不在此发起搜索或模型请求。"""
        settings = self._settings
        model = create_langchain_model(
            base_url=settings.llm_base_url, api_key=settings.llm_api_key,
            model_name=settings.get_model("outline"), timeout_seconds=settings.llm_timeout_seconds,
            max_tokens=settings.llm_max_tokens, http_client=model_http,
            streaming=settings.llm_show_thinking,
        )
        prompts = PROJECT_ROOT / "prompts"
        def prompt(name: str) -> str:
            return (prompts / name).read_text(encoding="utf-8")
        search = create_search_web_tool(client=SearxngSearchClient(
            client=search_http, base_url=settings.searxng_base_url, engines="",
            timeout_seconds=settings.web_search_timeout_seconds))
        reader = HttpWebpageReader(client=page_http, timeout_seconds=settings.webpage_timeout_seconds,
                                   max_download_bytes=settings.webpage_max_download_bytes)
        summary = MaterialSummaryAgent(model=model, prompt=prompt("materials/material_summary.md"),
                                       output_tokens=settings.llm_max_tokens)
        web = WebResearchWorkflow(
            query_agent=ResearchQueryAgent(model=model, tool=search, prompt=prompt("web/research_query.md")),
            review_agent=ResearchReviewAgent(model=model, prompt=prompt("web/research_review.md")),
            fetch_tool=create_fetch_webpage_tool(reader=reader),
            webpage_extraction_agent=WebpageExtractionAgent(
                model=model, prompt=prompt("web/web_research_page.md"),
                retry_prompt=prompt("web/web_research_page_retry.md")),
            material_summary_agent=summary,
            target_count=settings.research_target_source_count, max_attempts=settings.research_max_search_rounds,
            max_pages=settings.research_max_web_pages,
        )
        readers = create_document_readers(
            recognizer=RapidOcrTextRecognizer(model_directory=PROJECT_ROOT / "ocr-models"),
            renderer=PdfiumPageRenderer(), gotenberg_base_url=settings.gotenberg_base_url,
            gotenberg_timeout_seconds=settings.gotenberg_timeout_seconds)
        file_reader = DocumentFileReader(readers=readers,
            limits=DocumentReadLimits(max_characters=settings.document_max_characters,
                                      max_blocks=settings.document_max_blocks, max_cells=settings.document_max_cells),
            max_file_bytes=settings.upload_max_file_bytes, max_uncompressed_bytes=settings.upload_max_uncompressed_bytes)
        material = MaterialCollectionWorkflow(
            request_agent=RequestAnalysisAgent(model=model, prompt=prompt("materials/request_analysis.md")),
            web_workflow=web, file_agent=FileExtractionAgent(model=model, file_reader=file_reader,
                prompt=prompt("materials/file_extraction.md")), summary_agent=summary,
            target_count=settings.research_target_source_count)
        return web, material

    async def close(self) -> None:
        """服务停止时关闭连接；进程内检查点也随工作流实例失效。"""
        if self._resources is not None:
            await self._resources.aclose()
        self._resources = None
        self._workflow = None
        self._material_workflow = None
