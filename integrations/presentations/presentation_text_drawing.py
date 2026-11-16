"""为生成页面绘制单个可编辑文字框。"""

from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from models.presentations.presentation_page_element import TextElement


def draw_presentation_text(slide, plan: TextElement) -> None:
    shape = slide.shapes.add_textbox(Inches(plan.x), Inches(plan.y), Inches(plan.width), Inches(plan.height))
    paragraph = shape.text_frame.paragraphs[0]
    paragraph.text = plan.text
    paragraph.font.name = plan.font_name
    paragraph.font.size = Pt(plan.font_size)
    paragraph.font.color.rgb = RGBColor.from_string(plan.color[1:])
    shape.text_frame.word_wrap = True
