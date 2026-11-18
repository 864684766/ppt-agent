"""资料收集流程所需的子Agent接口；不绑定具体模型或SDK实现。"""

from typing import Protocol

from models.web.research_contract import SearchReview
from models.web.search_web_contract import WebSearchItem


class ResearchQueryAgentContract(Protocol):
    """查询Agent需要提供默认工具状态和异步搜索能力。"""

    @property
    def has_default_tool(self) -> bool:
        """是否配置了由服务器选择引擎的工具。"""
        ...

    async def search(self, *, question: str, feedback: str, engine: str | None) -> tuple[str, list[WebSearchItem]]:
        """返回本轮搜索词和候选；engine为None表示服务器默认策略。"""
        ...


class ResearchReviewAgentContract(Protocol):
    """检查Agent需要提供候选审核能力。"""

    async def review(self, *, question: str, candidates: list[WebSearchItem]) -> SearchReview:
        """按用户问题检查候选，返回正式候选、备用候选和反馈。"""
        ...
