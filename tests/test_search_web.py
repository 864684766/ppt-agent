"""查看工具JSON和真实搜索结果；从Settings读取.env及系统环境配置。

结果测试会访问真实SearXNG，属于集成验证，需要网络与可用服务。

uv run --locked python -m pytest tests/test_search_web.py -s -q
"""

import json

import httpx
import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool

from config.settings import Settings
from integrations.web.searxng_search_client import SearxngSearchClient
from tools.web import create_search_web_tool


@pytest.mark.asyncio
async def test_tool_calling_json() -> None:
    """转换并打印模型可见定义，不调用搜索客户端。"""
    settings = Settings()
    async with httpx.AsyncClient() as http_client:
        client = SearxngSearchClient(
            client=http_client, base_url=settings.searxng_base_url,
            engines=settings.searxng_default_engines,
            timeout_seconds=settings.web_search_timeout_seconds,
        )
        tool = create_search_web_tool(client=client)
        definition = convert_to_openai_tool(tool)
    json_text = json.dumps(definition, ensure_ascii=False, indent=2)
    print("\n【1】search_web的tool-calling JSON：")
    print(json_text)
    definition = json.loads(json_text)
    assert definition["type"] == "function"
    function = definition["function"]
    assert function["name"] == "search_web"
    assert function["description"]
    parameters = function["parameters"]
    assert parameters["type"] == "object"
    assert set(parameters["properties"]) == {"query", "max_results"}
    assert parameters["required"] == ["query"]
    assert all(field.get("description") for field in parameters["properties"].values())


@pytest.mark.asyncio
async def test_tool_return_result() -> None:
    """真实查询健康食谱资料；依赖.env配置、网络和SearXNG，不生成食谱。"""
    # 用户想要一份不忌口的健康食谱；这里直接填写用于寻找依据的搜索词。
    # 模型生成搜索词、读取网页和制作食谱的流程尚未接入此工具测试。
    arguments = {"query": "健康饮食 均衡膳食 每日食谱", "max_results": 3}
    settings = Settings()
    async with httpx.AsyncClient() as http_client:
        client = SearxngSearchClient(
            client=http_client, base_url=settings.searxng_base_url,
            engines=settings.searxng_default_engines,
            timeout_seconds=settings.web_search_timeout_seconds,
        )
        tool = create_search_web_tool(client=client)
        # 在这一行打断点；可以单步进入适配器，查看请求、真实响应和最终结果。
        result = await tool.ainvoke(arguments)
    print("\n【2】联网搜索调用参数：")
    print(json.dumps(arguments, ensure_ascii=False, indent=2))
    print("【2】搜索结果（真实SearXNG服务）：")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # 真实搜索结果随时间变化，不固定断言某个标题或网址。
    # 正常零命中也是合法结果；断点或打印用于观察实际内容是否符合你的需要。
    assert result["query"] == arguments["query"].strip()
    assert result["returned_count"] == len(result["items"])
    assert 0 <= result["returned_count"] <= arguments["max_results"]
