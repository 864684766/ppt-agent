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

# 测试时修改这里：None读取.env；""使用服务器general默认引擎；
# "bing"或"baidu kaifa"只请求对应引擎。多个名称用英文逗号分隔。
TEST_ENGINES: str | None = None
# 例如"zh-CN"指定中文；空字符串不传language，由服务器自行决定。
TEST_LANGUAGE = "zh-CN"


@pytest.mark.asyncio
async def test_searxng_raw_response() -> None:
    """查看服务器原始JSON，使用与示例链接相同的q和format两个参数。

    这是接口对照测试，不经过search_web工具，不限制条数或转换字段。
    SearXNG可能返回图片、视频等分类；实际结果随服务设置和时间变化。
    可以在response.json()处打断点，查看服务返回的完整内容。
    """
    settings = Settings()
    params = {"q": "健康饮食 均衡膳食 每日食谱", "format": "json"}
    # 不添加engines、categories和language，与用户示例链接保持相同。
    async with httpx.AsyncClient(timeout=settings.web_search_timeout_seconds) as http_client:
        response = await http_client.get(settings.searxng_base_url.rstrip("/") + "/search", params=params)
        response.raise_for_status()
        payload = response.json()
    print("\n【服务器原始JSON，未截取】")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    assert isinstance(payload.get("results"), list)


@pytest.mark.asyncio
async def test_tool_calling_json() -> None:
    """转换并打印模型可见定义，不调用搜索客户端。"""
    settings = Settings()
    async with httpx.AsyncClient() as http_client:
        # 此处选择测试用引擎，不是传给模型的工具入参。
        selected_engines = settings.searxng_default_engines if TEST_ENGINES is None else TEST_ENGINES
        client = SearxngSearchClient(
            client=http_client, base_url=settings.searxng_base_url,
            engines=selected_engines, language=TEST_LANGUAGE,
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
    arguments = {"query": "健康饮食 均衡膳食 每日食谱", "max_results": 10}
    settings = Settings()
    async with httpx.AsyncClient() as http_client:
        selected_engines = settings.searxng_default_engines if TEST_ENGINES is None else TEST_ENGINES
        client = SearxngSearchClient(
            client=http_client, base_url=settings.searxng_base_url,
            engines=selected_engines, language=TEST_LANGUAGE,
            timeout_seconds=settings.web_search_timeout_seconds,
        )
        tool = create_search_web_tool(client=client)
        # 在这一行打断点；可以单步进入适配器，查看请求、真实响应和最终结果。
        result = await tool.ainvoke(arguments)
    print("\n【2】联网搜索调用参数：")
    print("【测试选择】引擎：", selected_engines or "服务器general默认", "；语言：", TEST_LANGUAGE or "服务器默认")
    print(json.dumps(arguments, ensure_ascii=False, indent=2))
    print("【2】搜索结果（真实SearXNG服务）：")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # 真实搜索结果随时间变化，不固定断言某个标题或网址。
    # 正常零命中也是合法结果；断点或打印用于观察实际内容是否符合你的需要。
    assert result["query"] == arguments["query"].strip()
    assert result["returned_count"] == len(result["items"])
    assert 0 <= result["returned_count"] <= arguments["max_results"]
