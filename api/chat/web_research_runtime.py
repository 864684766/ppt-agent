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
from domain.web.web_search_contract import WebSearchClient
from integrations.documents.document_reader_registry import create_document_readers
from integrations.ocr.rapidocr_text_recognizer import RapidOcrTextRecognizer
from integrations.templates.pdfium_page_renderer import PdfiumPageRenderer
from models.documents.document_content import DocumentReadLimits
from workflows.materials.material_collection_workflow import MaterialCollectionWorkflow
from integrations.llm.langchain_model_factory import create_langchain_model
from integrations.web.http_webpage_reader import HttpWebpageReader
from integrations.web.browser_webpage_reader import BrowserWebpageReader
from integrations.web.fallback_webpage_reader import FallbackWebpageReader
from integrations.web.searxng.searxng_search_client import SearxngSearchClient
from integrations.web.tavily.tavily_search_client import TavilySearchClient
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
            # 已初始化时直接返回确定非空的对象；否则创建后返回局部变量。
            if self._workflow is not None:
                return self._workflow
            async with AsyncExitStack() as resources:
                model_http = await resources.enter_async_context(httpx.AsyncClient())
                # 本机SearXNG直连；Tavily允许使用系统代理以访问外部服务。
                search_http = await resources.enter_async_context(httpx.AsyncClient(
                    trust_env=self._settings.web_search_provider == "tavily"))
                page_http = await resources.enter_async_context(
                    create_webpage_http_client(verify_tls=self._settings.webpage_tls_verify))
                workflow, material_workflow = self._create_workflow(model_http, search_http, page_http)
                self._resources = resources.pop_all()
                self._workflow = workflow
                self._material_workflow = material_workflow
                return workflow

    async def get_material_workflow(self) -> MaterialCollectionWorkflow:
        """复用应用生命周期内的资料图及其内存检查点。"""
        await self.get_workflow()
        assert self._material_workflow is not None
        return self._material_workflow

    def _create_workflow(self, model_http: httpx.AsyncClient, search_http: httpx.AsyncClient,
                         page_http: httpx.AsyncClient) -> tuple[WebResearchWorkflow, MaterialCollectionWorkflow]:
        """组装并返回（网页研究工作流，资料收集工作流）。

        三个 HTTP 客户端分别用于模型、搜索服务和网页访问，由调用方负责关闭。
        此方法创建组件并编译工作流，但不执行搜索、读取文件或请求模型。
        配置无效、提示词读取失败等初始化错误会向调用方传播。
        """
        settings = self._settings
        # 返回一个 LangChain 聊天模型对象，供下方多个 Agent 共用；此时还没有调用模型。
        # get_model("outline") 选择配置中的任务模型；max_tokens 是单次输出预算。
        # streaming 控制模型是否流式产生内容，不保证供应商提供思考内容。
        model = create_langchain_model(
            base_url=settings.llm_base_url, api_key=settings.llm_api_key,
            model_name=settings.get_model("outline"), timeout_seconds=settings.llm_timeout_seconds,
            max_tokens=settings.llm_max_tokens, http_client=model_http,
            streaming=settings.llm_show_thinking,
        )
        # prompt 是本方法内部的小函数：接收相对 prompts 目录的文件名，返回 UTF-8 文本。
        prompts = PROJECT_ROOT / "prompts"
        def prompt(name: str) -> str:
            return (prompts / name).read_text(encoding="utf-8")

        # 宿主按配置选择供应商，工具接口不变；SearXNG使用其服务端默认引擎。
        search_client: WebSearchClient
        if settings.web_search_provider == "tavily":
            search_client = TavilySearchClient(client=search_http, api_key=settings.tavily_api_key,
                                               timeout_seconds=settings.web_search_timeout_seconds)
        else:
            search_client = SearxngSearchClient(client=search_http, base_url=settings.searxng_base_url,
                                                timeout_seconds=settings.web_search_timeout_seconds)
        search = create_search_web_tool(client=search_client)

        # HttpWebpageReader 返回网页读取器对象；调用时访问地址并提取内容。
        # 下载字节数和等待时间均受配置限制。
        # search_http、page_http 由上层管理和关闭，此处只借用连接。
        reader = HttpWebpageReader(client=page_http, timeout_seconds=settings.webpage_timeout_seconds,
                                   max_download_bytes=settings.webpage_max_download_bytes)
        # HTTP被拒绝或没有正文时，可用本机Edge执行脚本后读取；不使用用户浏览器的登录会话。
        webpage_reader = (FallbackWebpageReader(primary=reader, browser=BrowserWebpageReader(
            timeout_seconds=settings.webpage_timeout_seconds, max_download_bytes=settings.webpage_max_download_bytes))
            if settings.webpage_browser_fallback else reader)

        # MaterialSummaryAgent 返回汇总 Agent 对象，调用时接收已提炼要点并按需生成大纲。
        # 普通提示词用于汇总；最终输出超长时使用单独的重试提示词。
        # output_tokens 用于估算每批输入规模。timeout_seconds 是模型调用的超时配置。
        # 展示思考内容时逐批处理，减少不同批次内容交错；否则最多同时处理 3 批。
        # 并发数只影响中间批次，不保证供应商一定返回思考内容。
        summary = MaterialSummaryAgent(model=model, prompt=prompt("materials/material_summary.md"),
                                       retry_prompt=prompt("materials/material_summary_retry.md"),
                                       output_tokens=settings.llm_max_tokens, timeout_seconds=settings.llm_timeout_seconds,
                                       batch_concurrency=1 if settings.llm_show_thinking else 3)
        # WebResearchWorkflow 返回已组装的网页研究工作流；创建时不会运行各节点。
        web = WebResearchWorkflow(
            # 查询 Agent 生成搜索词并调用搜索工具；检查 Agent 判断搜索候选是否相关。
            query_agent=ResearchQueryAgent(model=model, tool=search, prompt=prompt("web/research_query.md")),
            review_agent=ResearchReviewAgent(model=model, prompt=prompt("web/research_review.md")),
            # 把前面创建的读取器包装为网页读取工具，供网页工作流调用。
            fetch_tool=create_fetch_webpage_tool(reader=webpage_reader),
            # 单页提炼 Agent 根据已读取的正文提取相关要点；超长输出使用重试提示词。
            webpage_extraction_agent=WebpageExtractionAgent(
                model=model, prompt=prompt("web/web_research_page.md"),
                retry_prompt=prompt("web/web_research_page_retry.md")),
            # 注入共用汇总 Agent；目标来源数、搜索轮数和读取页数均来自配置。
            material_summary_agent=summary,
            target_count=settings.research_target_source_count, max_attempts=settings.research_max_search_rounds,
            max_pages=settings.research_max_web_pages,
            extraction_concurrency=1 if settings.llm_show_thinking else 3,
        )
        # 返回“文件格式 -> 读取器”的字典，供文件读取入口按扩展名选择解析方式。
        # PDF 页面需要时由 Pdfium 渲染、RapidOCR 识别；旧版 doc 可使用 Gotenberg 转换。
        # 创建这些对象不代表已经加载 OCR 模型或解析文件。
        readers = create_document_readers(
            recognizer=RapidOcrTextRecognizer(model_directory=PROJECT_ROOT / "ocr-models"),
            renderer=PdfiumPageRenderer(), gotenberg_base_url=settings.gotenberg_base_url,
            gotenberg_timeout_seconds=settings.gotenberg_timeout_seconds)
        # 返回统一文件读取器：校验文件大小和格式，再选择上面的具体解析器。
        # DocumentReadLimits 限制提取字符数、内容块数和表格单元格数；大小上限单位是字节。
        file_reader = DocumentFileReader(readers=readers,
            limits=DocumentReadLimits(max_characters=settings.document_max_characters,
                                      max_blocks=settings.document_max_blocks, max_cells=settings.document_max_cells),
            max_file_bytes=settings.upload_max_file_bytes, max_uncompressed_bytes=settings.upload_max_uncompressed_bytes)
        # 返回上层资料收集工作流，负责按需求编排网页、文件、汇总及必要的用户询问。
        material = MaterialCollectionWorkflow(
            # 需求分析 Agent 判断资料来源和执行计划；web_workflow 复用上面的网页工作流。
            request_agent=RequestAnalysisAgent(model=model, prompt=prompt("materials/request_analysis.md")),
            # 文件提炼 Agent 先通过 file_reader 解析，再用模型提取相关要点。
            web_workflow=web, file_agent=FileExtractionAgent(model=model, file_reader=file_reader,
                prompt=prompt("materials/file_extraction.md")), summary_agent=summary,
            # 开放搜索使用配置中的来源目标，指定资料按用户给出的来源检查。
            target_count=settings.research_target_source_count)
        # 返回两个工作流对象的元组；调用方分别保存，之后才通过工作流方法启动任务。
        return web, material

    async def close(self) -> None:
        """服务停止时关闭连接；进程内检查点也随工作流实例失效。"""
        if self._resources is not None:
            await self._resources.aclose()
        self._resources = None
        self._workflow = None
        self._material_workflow = None
