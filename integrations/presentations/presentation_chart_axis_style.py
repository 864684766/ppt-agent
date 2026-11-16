"""设置原生图表坐标轴、刻度与网格线；不负责图表数据或模型决策。"""

from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_TICK_LABEL_POSITION, XL_TICK_MARK
from pptx.util import Pt

from models.presentations.presentation_chart_style import ChartAxisStyle


def apply_chart_axis_style(axis, style: ChartAxisStyle, *, is_value_axis: bool) -> None:
    """只覆盖显式传入的配置；分类轴与数值轴的输入约束由契约提前验证。"""
    if style.visible is not None:
        axis.visible = style.visible
    if style.title is not None:
        axis.has_title = bool(style.title)
        if style.title:
            axis.axis_title.text_frame.text = style.title
    # 图表轴线与刻度标签是不同对象，需要分别设置。
    if style.line_visible is False:
        axis.format.line.fill.background()
    elif style.line_visible is True:
        axis.format.line.fill.solid()
    if style.line_color is not None:
        axis.format.line.color.rgb = RGBColor.from_string(style.line_color[1:])
    if style.line_width is not None:
        axis.format.line.width = Pt(style.line_width)
    if style.major_tick is not None:
        axis.major_tick_mark = {"none": XL_TICK_MARK.NONE, "inside": XL_TICK_MARK.INSIDE,
                                "outside": XL_TICK_MARK.OUTSIDE, "cross": XL_TICK_MARK.CROSS}[style.major_tick]
    if style.minor_tick is not None:
        axis.minor_tick_mark = {"none": XL_TICK_MARK.NONE, "inside": XL_TICK_MARK.INSIDE,
                                "outside": XL_TICK_MARK.OUTSIDE, "cross": XL_TICK_MARK.CROSS}[style.minor_tick]
    if style.label_position is not None:
        axis.tick_label_position = {"none": XL_TICK_LABEL_POSITION.NONE, "next_to_axis": XL_TICK_LABEL_POSITION.NEXT_TO_AXIS,
                                    "low": XL_TICK_LABEL_POSITION.LOW, "high": XL_TICK_LABEL_POSITION.HIGH}[style.label_position]
    font = axis.tick_labels.font
    if style.label_font_name is not None:
        font.name = style.label_font_name
    if style.label_font_size is not None:
        font.size = Pt(style.label_font_size)
    if style.label_color is not None:
        font.color.rgb = RGBColor.from_string(style.label_color[1:])
    if is_value_axis:
        if style.minimum is not None:
            axis.minimum_scale = style.minimum
        if style.maximum is not None:
            axis.maximum_scale = style.maximum
        if style.major_unit is not None:
            axis.major_unit = style.major_unit
        if style.minor_unit is not None:
            axis.minor_unit = style.minor_unit
        if style.number_format is not None:
            axis.tick_labels.number_format = style.number_format
    if style.major_gridlines is not None:
        axis.has_major_gridlines = style.major_gridlines
    if style.major_gridlines:
        if style.gridline_color is not None:
            axis.major_gridlines.format.line.color.rgb = RGBColor.from_string(style.gridline_color[1:])
        if style.gridline_width is not None:
            axis.major_gridlines.format.line.width = Pt(style.gridline_width)
