"""使用python-pptx绘制可编辑原生图表。"""

from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches

from models.presentations.presentation_page_element import ChartElement


def draw_presentation_chart(slide, plan: ChartElement) -> None:
    data = CategoryChartData()
    data.categories = plan.categories
    for series in plan.series:
        data.add_series(series.name, series.values)
    chart_type = {"column": XL_CHART_TYPE.COLUMN_CLUSTERED, "line": XL_CHART_TYPE.LINE,
                  "pie": XL_CHART_TYPE.PIE}[plan.chart_type]
    slide.shapes.add_chart(chart_type, Inches(plan.x), Inches(plan.y), Inches(plan.width), Inches(plan.height), data)
