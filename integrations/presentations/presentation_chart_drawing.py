"""使用python-pptx绘制可编辑原生图表。"""

from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches

from integrations.presentations.presentation_chart_axis_style import apply_chart_axis_style
from integrations.presentations.presentation_chart_display_style import apply_chart_display_style
from models.presentations.presentation_page_element import ChartElement


def draw_presentation_chart(slide, plan: ChartElement) -> None:
    data = CategoryChartData()
    data.categories = plan.categories
    for series in plan.series:
        data.add_series(series.name, series.values)
    chart_type = {"column": XL_CHART_TYPE.COLUMN_CLUSTERED, "line": XL_CHART_TYPE.LINE,
                  "pie": XL_CHART_TYPE.PIE}[plan.chart_type]
    shape = slide.shapes.add_chart(chart_type, Inches(plan.x), Inches(plan.y), Inches(plan.width), Inches(plan.height), data)
    if plan.style is not None:
        apply_chart_display_style(shape.chart, plan.style)
    if plan.category_axis is not None:
        apply_chart_axis_style(shape.chart.category_axis, plan.category_axis, is_value_axis=False)
    if plan.value_axis is not None:
        apply_chart_axis_style(shape.chart.value_axis, plan.value_axis, is_value_axis=True)
    # 不提供颜色时保留Office主题默认值；显式设置时才覆盖对应系列或饼图扇区。
    for series, series_plan in zip(shape.chart.series, plan.series):
        if series_plan.color is not None and plan.chart_type == "column":
            series.format.fill.solid()
            series.format.fill.fore_color.rgb = RGBColor.from_string(series_plan.color[1:])
        elif series_plan.color is not None and plan.chart_type == "line":
            series.format.line.color.rgb = RGBColor.from_string(series_plan.color[1:])
    if plan.chart_type == "pie" and plan.point_colors is not None:
        for point, color in zip(shape.chart.series[0].points, plan.point_colors):
            point.format.fill.solid()
            point.format.fill.fore_color.rgb = RGBColor.from_string(color[1:])
