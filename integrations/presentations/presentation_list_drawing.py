"""将结构化列表绘制为可编辑的PPT文字框。"""

from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from models.presentations.presentation_list_plan import PresentationListPlan


def draw_presentation_list(slide, plan: PresentationListPlan) -> list[int]:
    """每项独立文字框；标记为普通文本，不提供PowerPoint自动编号。"""
    shape_ids = []
    item_height = plan.height / len(plan.items)
    for index, item in enumerate(plan.items):
        indent = item.level * 0.3
        prefix = "• " if plan.marker == "bullet" else f"{index + 1}. " if plan.marker == "number" else ""
        shape = slide.shapes.add_textbox(Inches(plan.x + indent), Inches(plan.y + index * item_height),
                                         Inches(plan.width - indent), Inches(item_height))
        paragraph = shape.text_frame.paragraphs[0]
        paragraph.text = prefix + item.text
        paragraph.font.name = plan.font_name
        paragraph.font.size = Pt(plan.font_size)
        paragraph.font.color.rgb = RGBColor.from_string(plan.text_color[1:])
        shape.text_frame.word_wrap = True
        shape_ids.append(shape.shape_id)
    return shape_ids
