"""将当前请求已提炼的要点交给草稿订阅方，供网页和资料收集工作流共用。"""

from collections.abc import Callable
from contextvars import ContextVar

from domain.materials.material_outline_draft import draft_from_material_points
from models.materials.material_summary import MaterialInputPoint
from models.outlines.presentation_outline import PresentationOutline


outline_preview: ContextVar[Callable[[PresentationOutline, list[MaterialInputPoint]], None] | None] = (
    ContextVar("outline_preview", default=None)
)


def publish_outline_preview(points: list[MaterialInputPoint]) -> None:
    """每份预览最多使用八条要点，订阅者在当前请求的 SSE 连接上发送。"""
    publish = outline_preview.get()
    if publish is not None and points:
        selected = points[:8]
        outline = draft_from_material_points(selected).outline
        if outline is not None:
            publish(outline, selected)
