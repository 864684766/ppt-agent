"""联网搜索业务入口：校验查询，调用可替换的搜索能力，不登记网页正文。"""

from domain.web.web_search_contract import WebSearchClient
from models.web.web_search_candidate import WebSearchCandidate


async def search_web_candidates(
    *, client: WebSearchClient, query: str, max_results: int = 5,
) -> tuple[WebSearchCandidate, ...]:
    """独立于模型/HTTP运行时调用；参数错误抛ValueError，服务错误由适配器报告。

    每次只发起一次搜索，不决定Agent检索轮数，不修改任何项目资料目录。
    调用方拥有client及底层连接，函数不会关闭调用方的资源。
    """
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 1000:
        raise ValueError("query必须为1至1000字符的非空字符串。")
    if type(max_results) is not int or not 1 <= max_results <= 10:
        raise ValueError("max_results必须为1至10的整数。")
    return await client.search(query=query.strip(), max_results=max_results)
