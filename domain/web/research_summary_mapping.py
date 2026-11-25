"""将通用汇总结果映射为现有网页研究响应，不执行模型判断。"""

from models.materials.material_summary import MaterialInputPoint, MaterialSummary
from models.web.web_research_summary import WebContentIssue, WebResearchSummary, WebSummaryPoint


def to_web_research_summary(summary: MaterialSummary, points: list[MaterialInputPoint]) -> WebResearchSummary:
    """按输入要点编号还原网页候选编号，保持现有工作流与HTTP契约。"""
    sources = {point.point_id: [ref.source_id for ref in point.references if ref.kind == "web"] for point in points}

    def candidate_ids(point_ids: list[str]) -> list[str]:
        return list(dict.fromkeys(source for point_id in point_ids for source in sources[point_id]))

    return WebResearchSummary(
        points=[WebSummaryPoint(content=item.content, candidate_ids=candidate_ids(item.point_ids)) for item in summary.points],
        issues=[WebContentIssue(type=item.type, message=item.message, candidate_ids=candidate_ids(item.point_ids)) for item in summary.issues],
        gaps=[item.message for item in summary.issues if item.type == "content_gap"], follow_links=[],
    )
