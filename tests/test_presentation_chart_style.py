"""验证图表样式的可观察行为，独立于网络、模型和Office运行时。"""

import pytest
from typing import Any
from pydantic import TypeAdapter, ValidationError
from pptx import Presentation
from pptx.enum.chart import XL_LEGEND_POSITION, XL_TICK_LABEL_POSITION, XL_TICK_MARK
from pptx.util import Pt

from integrations.presentations.presentation_chart_drawing import draw_presentation_chart
from models.presentations.presentation_page_element import PresentationPageElement


def test_line_chart_axis_and_display_style() -> None:
    """折线图的轴范围、轴线、刻度、网格线及图例应按输入生效。"""
    adapter: TypeAdapter[PresentationPageElement] = TypeAdapter(PresentationPageElement)
    plan = adapter.validate_python({
        "type": "chart", "chart_type": "line", "x": 1, "y": 1, "width": 5, "height": 3,
        "categories": ["一月", "二月"], "series": [{"name": "次数", "values": [2, 4]}],
        "style": {"title": "趋势", "legend_visible": True, "legend_position": "bottom", "data_labels": True},
        "category_axis": {"label_position": "low", "major_tick": "outside", "label_color": "#123456"},
        "value_axis": {"title": "次数", "minimum": 0, "maximum": 10, "major_unit": 2, "minor_unit": 1,
                       "line_visible": True, "minor_tick": "inside",
                       "line_color": "#456789", "line_width": 1.5, "major_gridlines": True,
                       "gridline_color": "#AABBCC", "gridline_width": 0.5, "number_format": "0.0"},
    })
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    from models.presentations.presentation_page_element import ChartElement
    assert isinstance(plan, ChartElement)
    draw_presentation_chart(slide, plan)
    chart = slide.shapes[-1].chart
    assert chart.chart_title.text_frame.text == "趋势"
    assert chart.has_legend and chart.legend.position == XL_LEGEND_POSITION.BOTTOM
    assert chart.plots[0].has_data_labels
    assert chart.category_axis.tick_label_position == XL_TICK_LABEL_POSITION.LOW
    assert chart.category_axis.major_tick_mark == XL_TICK_MARK.OUTSIDE
    assert str(chart.category_axis.tick_labels.font.color.rgb) == "123456"
    axis = chart.value_axis
    assert (axis.minimum_scale, axis.maximum_scale, axis.major_unit) == (0, 10, 2)
    assert axis.minor_unit == 1 and axis.minor_tick_mark == XL_TICK_MARK.INSIDE
    assert axis.axis_title.text_frame.text == "次数" and axis.tick_labels.number_format == "0.0"
    assert str(axis.format.line.color.rgb) == "456789" and axis.format.line.width == Pt(1.5)
    assert str(axis.major_gridlines.format.line.color.rgb) == "AABBCC"


def test_invalid_axis_styles_rejected() -> None:
    """饼图没有坐标轴、范围颠倒和隐藏网格线却设置网格线颜色均应拒绝。"""
    adapter: TypeAdapter[PresentationPageElement] = TypeAdapter(PresentationPageElement)
    base: dict[str, Any] = {"type": "chart", "chart_type": "column", "x": 1, "y": 1, "width": 5, "height": 3,
            "categories": ["A"], "series": [{"name": "数量", "values": [1]}]}
    changes: list[dict[str, Any]] = [
        {"chart_type": "pie", "value_axis": {"minimum": 0}},
        {"value_axis": {"minimum": 10, "maximum": 1}},
        {"value_axis": {"major_gridlines": False, "gridline_color": "#AABBCC"}},
        {"category_axis": {"major_unit": 2}},
        {"value_axis": {"line_visible": False, "line_color": "#AABBCC"}},
    ]
    for change in changes:
        with pytest.raises(ValidationError):
            adapter.validate_python({**base, **change})
