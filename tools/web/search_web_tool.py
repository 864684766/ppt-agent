"""search_web的LangChain适配：描述工具、调用业务、选择公开字段。"""


from langchain.tools import tool
from langchain_core.tools import BaseTool, ToolException

from diagnostics.operation_logging import log_operation
from domain.web.web_search import search_web_candidates
from domain.web.web_search_contract import WebSearchClient, WebSearchError
from models.web.search_web_contract import SearchWebInput, SearchWebOutput, WebSearchItem


def create_search_web_tool(*, client: WebSearchClient) -> BaseTool:
    """绑定外层注入的搜索客户端；不持有项目目录，不负责关闭连接。

    Args:
        client: 实现WebSearchClient协议的客户端，已由外层绑定搜索服务及引擎；
            本函数借用它，不负责创建或关闭底层连接。

    Returns:
        LangChain BaseTool。通过await tool.ainvoke({"query": "..."})调用；
        模型可见名称、用途及参数说明，不能在入参中更换引擎或密钥。
    创建工具不会发请求；一次工具调用只执行一次搜索，不自动筛选或重试。
    """

    @tool("search_web", args_schema=SearchWebInput, description=(
        "联网搜索主题资料，返回query（搜索词）、items（网页候选）和returned_count（返回条数）。"
        "每项包含candidate_id（候选编号）、title（标题）、url（地址）、snippet（搜索摘要）和engines（来源引擎列表）。"
        "摘要不是正文或事实核验结果；读取网页请将url传给fetch_webpage。"
        "candidate_id不是已登记资料的source_id，不能用于read_material；本地资料检索使用search_materials。"
        "每次调用搜索一次，空items表示没有候选。"
    ))
    @log_operation("tool.search_web")
    async def search_web(query: str, max_results: int = 5) -> SearchWebOutput:
        """执行一次搜索并返回公开字段；正常零结果返回空items。

        query是搜索词，max_results是返回候选上限；Pydantic输入模型先校验。
        搜索或业务校验失败转为ToolException，供LangChain运行时或工作流处理。
        """
        try:
            candidates = await search_web_candidates(client=client, query=query, max_results=max_results)
        except (ValueError, WebSearchError) as error:
            raise ToolException(str(error)) from None
        # 显式逐条组装，便于打断点观察，也避免公开供应商的其他内部字段。
        items: list[WebSearchItem] = []
        for item in candidates:
            items.append({
                "candidate_id": item.candidate_id, "title": item.title,
                "url": item.url, "snippet": item.snippet,
                "engines": list(item.engines),
            })
        return {"query": query.strip(), "items": items, "returned_count": len(items)}

    return search_web
