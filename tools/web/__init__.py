"""联网工具入口；导入时不会创建连接或发起请求。"""

from tools.web.search_web_tool import create_search_web_tool
from tools.web.fetch_webpage_tool import create_fetch_webpage_tool

__all__ = ["create_search_web_tool", "create_fetch_webpage_tool"]
