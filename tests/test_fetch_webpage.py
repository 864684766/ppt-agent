"""检查工具JSON，再真实搜索并读取候选网页；不使用模拟数据。

uv run --locked python -m pytest tests/test_fetch_webpage.py -s -q
结果项属于集成验证，依赖.env、SearXNG、外网和目标网站。
"""

import json

import pytest
from langchain_core.tools import ToolException
from langchain_core.utils.function_calling import convert_to_openai_tool

from config.settings import Settings
from integrations.web.http_webpage_reader import HttpWebpageReader
from integrations.web.webpage_http_client import create_webpage_http_client
from integrations.web.searxng_search_client import SearxngSearchClient
from tools.web import create_fetch_webpage_tool, create_search_web_tool


@pytest.mark.asyncio
async def test_tool_calling_json() -> None:
    """只转换定义，不发送请求；核对模型能看到参数说明。"""
    settings = Settings()
    async with create_webpage_http_client(verify_tls=settings.webpage_tls_verify) as http_client:
        reader = HttpWebpageReader(
            client=http_client, timeout_seconds=settings.webpage_timeout_seconds,
            max_download_bytes=settings.webpage_max_download_bytes,
        )
        tool = create_fetch_webpage_tool(reader=reader)
        json_text = json.dumps(convert_to_openai_tool(tool), ensure_ascii=False, indent=2)
    print("\n【1】fetch_webpage的tool-calling JSON：")
    print(json_text)
    definition = json.loads(json_text)
    assert definition["type"] == "function"
    function = definition["function"]
    assert function["name"] == "fetch_webpage"
    assert function["description"]
    fields = function["parameters"]["properties"]
    assert set(fields) == {"url", "max_chars"}
    assert all(field.get("description") for field in fields.values())


@pytest.mark.asyncio
async def test_tool_return_result_from_search() -> None:
    """真实搜索，依次尝试最多三个候选，取得一个网页正文后停止。

    换候选只属于这份集成验证，fetch_webpage本身仍只读取传入的一个URL。
    所有候选失败时测试失败，逐条打印错误，不用模拟正文冒充成功。
    """
    settings = Settings()
    search_arguments = {"query": "中国居民膳食指南 健康饮食", "max_results": 3}
    # 共用连接池，响应在各适配器的上下文中关闭；最多跟随5次HTTP重定向。
    async with create_webpage_http_client(verify_tls=settings.webpage_tls_verify) as http_client:
        search_client = SearxngSearchClient(
            client=http_client, base_url=settings.searxng_base_url,
            engines=settings.searxng_default_engines,
            timeout_seconds=settings.web_search_timeout_seconds,
        )
        search_tool = create_search_web_tool(client=search_client)
        reader = HttpWebpageReader(
            client=http_client, timeout_seconds=settings.webpage_timeout_seconds,
            max_download_bytes=settings.webpage_max_download_bytes,
        )
        fetch_tool = create_fetch_webpage_tool(reader=reader)
        search_result = await search_tool.ainvoke(search_arguments)
        print("\n【2】真实搜索参数：", json.dumps(search_arguments, ensure_ascii=False))
        print("【2】真实搜索结果：")
        print(json.dumps(search_result, ensure_ascii=False, indent=2))
        assert search_result["items"], "本次没有搜索候选，无法验证网页读取。"
        for candidate in search_result["items"]:
            arguments = {"url": candidate["url"], "max_chars": 3000}
            print("【3】网页读取参数：", json.dumps(arguments, ensure_ascii=False))
            try:
                # 在这里打断点；URL直接来自上面的真实搜索，不是预先写好的测试网址。
                result = await fetch_tool.ainvoke(arguments)
            except ToolException as error:
                print("【3】此候选读取失败：", str(error))
                continue
            print("【3】网页读取结果：")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            assert result["requested_url"] == candidate["url"]
            assert 0 < result["returned_chars"] == len(result["text"]) <= arguments["max_chars"]
            assert result["truncated"] == (result["extracted_chars"] > result["returned_chars"])
            return
        pytest.fail("搜索返回的候选均无法读取，请根据上方错误检查网络、页面类型或访问限制。")
