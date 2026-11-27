"""根据已提炼的要点构造可溯源的草稿。"""

from models.materials.material_summary import MaterialInputPoint, MaterialMergedPoint, MaterialSummary
from models.outlines.presentation_outline import OutlineBullet, OutlineSlide, PresentationOutline


def draft_from_material_points(points: list[MaterialInputPoint]) -> MaterialSummary:
    """按资料原有顺序排列、合并完全相同的要点，并保留可查的来源编号。"""
    grouped: dict[str, list[str]] = {}
    for point in points:
        content = point.content.strip()
        if content:
            grouped.setdefault(content, []).append(point.point_id)
    if not grouped:
        return MaterialSummary(points=[], issues=[])

    # 草稿优先每页四条。资料较多时合并到最多十二页，保留全部依据。
    page_size = max(4, (len(grouped) + 11) // 12)
    bullets = [OutlineBullet(content=content, point_ids=ids) for content, ids in grouped.items()]
    slides = [OutlineSlide(role="content", title=f"资料要点 {index // page_size + 1}",
                           bullets=bullets[index:index + page_size])
              for index in range(0, len(bullets), page_size)]
    return MaterialSummary(
        points=[MaterialMergedPoint(content=bullet.content, point_ids=bullet.point_ids) for bullet in bullets],
        issues=[], outline=PresentationOutline(title="资料整理草稿", slides=slides),
    )
