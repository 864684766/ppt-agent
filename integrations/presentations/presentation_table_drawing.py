"""把已校验的数据画成原生、可编辑的PPT表格。"""

from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from models.presentations.presentation_table_plan import PresentationTablePlan


def draw_presentation_table(slide, plan: PresentationTablePlan) -> int:
    """返回新增表格shape_id；逐行交替填充颜色，不做文字溢出判断。"""
    values = [plan.headers, *plan.rows]
    shape = slide.shapes.add_table(len(values), len(plan.headers), Inches(plan.x), Inches(plan.y),
                                   Inches(plan.width), Inches(plan.height))
    for row_index, row in enumerate(values):
        for column_index, value in enumerate(row):
            cell = shape.table.cell(row_index, column_index)
            cell.text = value
            # 第0行是表头；第一条数据从row_colors[0]开始，两种颜色循环。
            fill = plan.header_color if row_index == 0 else plan.row_colors[(row_index - 1) % 2]
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor.from_string(fill[1:])
            cell.text_frame.word_wrap = True
            for paragraph in cell.text_frame.paragraphs:
                paragraph.font.name = plan.font_name
                paragraph.font.size = Pt(plan.font_size)
                paragraph.font.color.rgb = RGBColor.from_string((plan.header_text_color if row_index == 0 else plan.text_color)[1:])
                paragraph.font.bold = row_index == 0
    return shape.shape_id
