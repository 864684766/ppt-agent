"""search_web的LangChain适配：描述工具、调用业务、选择公开字段。"""


from langchain.tools import tool
from langchain_core.tools import BaseTool, ToolException

from diagnostics.operation_logging import log_operation
from domain.web.web_search import search_web_candidates
from domain.web.web_search_contract import WebSearchClient, WebSearchError
from models.web.search_web_contract import SearchWebInput, SearchWebOutput, WebSearchItem


def create_search_web_tool(*, client: WebSearchClient) -> BaseTool:
    """绑定外层注入的搜索客户端；不持有项目目录，不负责关闭连接。

    使用await tool.ainvoke(...)调用；模型只提供查询词和条数，不能更换密钥。
    创建工具不会发请求，只有实际调用时才执行一次外部搜索。
    """

    @tool("search_web", args_schema=SearchWebInput, description=(
        "需要发现外部主题资料或可引用网页时使用互联网搜索。"
        "返回query（实际搜索词）、items（候选网页列表）和returned_count（本次返回条数，非全网总数）。"
        "每个候选含candidate_id（URL生成的候选编号）、title（网页标题）、url（网页地址）、snippet（搜索摘要）。snippet不是完整原文或事实核实结果；"
        "candidate_id不能用于read_material，不会自动登记source_id。"
        "可用fetch_webpage读取候选url的正文；正文登记为项目资料尚未实现。"
        "查询已上传或已登记资料应使用search_materials；不搜索PPT设计模板。"
        "每次只搜索一次，不自动扩词、重试或循环；空items表示本次没有候选。"
    ))
    @log_operation("tool.search_web")
    async def search_web(query: str, max_results: int = 5) -> SearchWebOutput:
        """异步等待外部搜索，避免阻塞其他请求；业务错误转换成工具错误。"""
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
            })
        return {"query": query.strip(), "items": items, "returned_count": len(items)}

    return search_web
