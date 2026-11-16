"""设置原生图表的标题、图例、数据标签和默认字体。"""

from pptx.enum.chart import XL_LEGEND_POSITION
from pptx.util import Pt

from models.presentations.presentation_chart_style import ChartDisplayStyle


def apply_chart_display_style(chart, style: ChartDisplayStyle) -> None:
    """只设置明确给出的选项；操作原生图表对象并保留可编辑数据。"""
    if style.title is not None:
        chart.has_title = bool(style.title)
        if style.title:
            chart.chart_title.text_frame.text = style.title
    if style.legend_visible is not None:
        chart.has_legend = style.legend_visible
    if style.legend_position is not None:
        chart.legend.position = {"bottom": XL_LEGEND_POSITION.BOTTOM, "top": XL_LEGEND_POSITION.TOP,
                                 "left": XL_LEGEND_POSITION.LEFT, "right": XL_LEGEND_POSITION.RIGHT}[style.legend_position]
    if style.data_labels is not None:
        for plot in chart.plots:
            plot.has_data_labels = style.data_labels
            if style.data_labels:
                plot.data_labels.show_value = True
    if style.font_name is not None:
        chart.font.name = style.font_name
    if style.font_size is not None:
        chart.font.size = Pt(style.font_size)
