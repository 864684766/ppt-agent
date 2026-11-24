"""在应用生命周期内组装网页研究流程；连接与检查点由宿主持有。"""

import asyncio
from contextlib import AsyncExitStack

import httpx

from agents.research_query_agent import ResearchQueryAgent
from agents.research_review_agent import ResearchReviewAgent
from agents.web_research_summary_agent import WebResearchSummaryAgent
from config.settings import PROJECT_ROOT, Settings
from integrations.llm.langchain_model_factory import create_langchain_model
from integrations.web.http_webpage_reader import HttpWebpageReader
from integrations.web.searxng_search_client import SearxngSearchClient
from integrations.web.webpage_http_client import create_webpage_http_client
from tools.web.fetch_webpage_tool import create_fetch_webpage_tool
from tools.web.search_web_tool import create_search_web_tool
from workflows.web_research_workflow import WebResearchWorkflow


class WebResearchRuntime:
    """首次请求时初始化并复用工作流；连接和内存检查点随应用关闭而释放。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = asyncio.Lock()
        self._resources: AsyncExitStack | None = None
        self._workflow: WebResearchWorkflow | None = None

    async def get_workflow(self) -> WebResearchWorkflow:
        """并发请求只创建一次工作流；初始化失败时关闭已创建的资源。"""
        async with self._lock:
            if self._workflow is None:
                async with AsyncExitStack() as resources:
                    model_http = await resources.enter_async_context(httpx.AsyncClient())
                    search_http = await resources.enter_async_context(httpx.AsyncClient(trust_env=False))
                    page_http = await resources.enter_async_context(
                        create_webpage_http_client(verify_tls=self._settings.webpage_tls_verify))
                    workflow = self._create_workflow(model_http, search_http, page_http)
                    self._resources = resources.pop_all()
                    self._workflow = workflow
            return self._workflow

    def _create_workflow(self, model_http: httpx.AsyncClient, search_http: httpx.AsyncClient,
                         page_http: httpx.AsyncClient) -> WebResearchWorkflow:
        """集中注入配置、模型和工具；不在此发起搜索或模型请求。"""
        settings = self._settings
        model = create_langchain_model(
            base_url=settings.llm_base_url, api_key=settings.llm_api_key,
            model_name=settings.get_model("outline"), timeout_seconds=settings.llm_timeout_seconds,
            max_tokens=max(settings.llm_max_tokens, 4096), http_client=model_http,
        )
        prompts = PROJECT_ROOT / "prompts"
        def prompt(name: str) -> str:
            return (prompts / name).read_text(encoding="utf-8")
        search = create_search_web_tool(client=SearxngSearchClient(
            client=search_http, base_url=settings.searxng_base_url, engines="",
            timeout_seconds=settings.web_search_timeout_seconds))
        reader = HttpWebpageReader(client=page_http, timeout_seconds=settings.webpage_timeout_seconds,
                                   max_download_bytes=settings.webpage_max_download_bytes)
        return WebResearchWorkflow(
            query_agent=ResearchQueryAgent(model=model, tool=search, prompt=prompt("research_query.md")),
            review_agent=ResearchReviewAgent(model=model, prompt=prompt("research_review.md")),
            fetch_tool=create_fetch_webpage_tool(reader=reader),
            summary_agent=WebResearchSummaryAgent(
                model=model, prompt=prompt("web_research_summary.md"), page_prompt=prompt("web_research_page.md"),
                summary_prompt=prompt("web_research_merge.md"), retry_prompt=prompt("web_research_page_retry.md")),
            target_count=settings.research_target_source_count, max_attempts=settings.research_max_search_rounds,
            max_pages=settings.research_max_web_pages,
        )

    async def close(self) -> None:
        """服务停止时关闭连接；进程内检查点也随工作流实例失效。"""
        if self._resources is not None:
            await self._resources.aclose()
        self._resources = None
        self._workflow = None
