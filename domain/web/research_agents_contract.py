"""资料收集流程所需的子Agent接口；不绑定具体模型或SDK实现。"""

from typing import Protocol

from models.web.research_contract import SearchReview
from models.web.search_web_contract import WebSearchItem


class ResearchQueryAgentContract(Protocol):
    """查询Agent根据需求与反馈执行搜索。"""

    async def search(self, *, question: str, feedback: str) -> tuple[str, list[WebSearchItem]]:
        """返回本轮搜索词和候选；搜索工具由宿主注入。"""
        ...


class ResearchReviewAgentContract(Protocol):
    """检查Agent需要提供候选审核能力。"""

    async def review(self, *, question: str, candidates: list[WebSearchItem]) -> SearchReview:
        """按用户问题检查候选，返回正式候选、备用候选和反馈。"""
        ...
