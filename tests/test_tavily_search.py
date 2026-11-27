"""真实Tavily工具验证：uv run --locked python -m pytest tests/test_tavily_search.py -s。"""

import json

import httpx
import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool

from config.settings import Settings
from integrations.web.tavily.tavily_search_client import TavilySearchClient
from tools.web.search_web_tool import create_search_web_tool


@pytest.mark.asyncio
async def test_real_tavily_search() -> None:
    """打印模型工具定义及真实搜索结果；结果质量需要人工判断。"""
    settings = Settings()
    query, max_results = "中国居民膳食指南2022 平衡膳食 八准则", 5
    arguments = {"query": query, "max_results": max_results}
    async with httpx.AsyncClient() as client:
        tool = create_search_web_tool(client=TavilySearchClient(
            client=client, api_key=settings.tavily_api_key, timeout_seconds=settings.web_search_timeout_seconds))
        definition = convert_to_openai_tool(tool)
        print("【工具JSON】", json.dumps(definition, ensure_ascii=False, indent=2))
        parameters = definition["function"]["parameters"]
        assert set(parameters["properties"]) == {"query", "max_results"}
        assert all(value.get("description") for value in parameters["properties"].values())
        print("【调用参数】", json.dumps(arguments, ensure_ascii=False))
        result = await tool.ainvoke(arguments)
    print("【真实搜索结果】", json.dumps(result, ensure_ascii=False, indent=2))
    assert result["query"] == arguments["query"]
    assert 0 < result["returned_count"] == len(result["items"]) <= max_results
    assert all(item["candidate_id"].startswith("web_") and item["url"].startswith(("http://", "https://"))
               for item in result["items"])
