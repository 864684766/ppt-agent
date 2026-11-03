"""独立调试真实搜索工具：uv run --locked python -m examples.search_web_demo。

会访问.env指定的真实服务；这是手工集成验证入口，不是单元测试或HTTP接口。
"""

import asyncio
import json

import httpx

from config.settings import Settings
from integrations.searxng_search_client import SearxngSearchClient
from tools.web import create_search_web_tool


async def main() -> None:
    """组装配置、连接和工具；执行结束或异常退出时自动关闭连接。"""
    settings = Settings()
    arguments = {"query": "中国居民膳食指南 健康饮食", "max_results": 5}
    async with httpx.AsyncClient() as http_client:
        search_client = SearxngSearchClient(
            client=http_client, base_url=settings.searxng_base_url,
            engines=settings.searxng_default_engines,
            timeout_seconds=settings.web_search_timeout_seconds,
        )
        tool = create_search_web_tool(client=search_client)
        # 在此处打断点，F8执行后查看result；修改arguments即可更换搜索词。
        result = await tool.ainvoke(arguments)
        print("【真实搜索参数】")
        print(json.dumps(arguments, ensure_ascii=False, indent=2))
        print("【真实搜索结果】")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
