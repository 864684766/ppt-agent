"""查看工具JSON与真实模板成品，供PyCharm断点和WPS人工核对。"""

import json
import hashlib
from io import BytesIO
from pathlib import Path

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool
from pptx import Presentation
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.shapes import MSO_SHAPE_TYPE
from PIL import Image

from config.settings import PROJECT_ROOT
from integrations.templates.local_presentation_builder import LocalPresentationBuilder
from tools.presentations.build_presentation_tool import create_build_presentation_tool

# 使用当前绿色几何模板；更换模板时须重新确认实际页码、对象编号和位置。
TEMPLATE_PATH: Path = PROJECT_ROOT / "ppt-demo" / "绿色几何创意演示PPT模板.pptx"
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "built-presentations"
# 测试仅读取本地样例，不在工具调用时联网；素材来源见调试说明和成品来源页。
MEDIA_DIRECTORY = PROJECT_ROOT / "data" / "media-samples"


def test_tool_calling_json() -> None:
    builder = LocalPresentationBuilder(templates={}, output_directory=OUTPUT_DIRECTORY)
    definition = json.loads(json.dumps(convert_to_openai_tool(create_build_presentation_tool(builder=builder)), ensure_ascii=False))
    print("\n【1】工具JSON：", json.dumps(definition, ensure_ascii=False, indent=2), flush=True)
    assert definition["function"]["name"] == "build_presentation"
    assert set(definition["function"]["parameters"]["properties"]) == {"template_id", "pages"}
    assert "未列出" in definition["function"]["description"]
    schema = json.dumps(definition, ensure_ascii=False)
    assert all(f'"{kind}"' in schema for kind in ["text", "image", "video", "audio", "chart", "table", "list"])
    assert "point_colors" in schema and "header_color" in schema and "系列填充色" in schema


def _slide_text(shapes) -> list[str]:
    """测试用递归读取，确保组合内部的替换内容也能核对。"""
    result = []
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            result.extend(_slide_text(shape.shapes))
        elif shape.has_text_frame:
            result.append(shape.text)
    return result


@pytest.mark.asyncio
async def test_tool_result_with_real_template() -> None:
    """根据公开运动指南手工准备8页示例；图表数值是计划示例，不是研究数据。"""
    original = TEMPLATE_PATH.read_bytes()
    # 测试模拟宿主读取文件后按编号提供字节；运行时工具不访问互联网或任意路径。
    picture = (MEDIA_DIRECTORY / "fitness-treadmill.jpg").read_bytes()
    video = (MEDIA_DIRECTORY / "fitness-squat.mp4").read_bytes()
    video_poster = (MEDIA_DIRECTORY / "fitness-squat-poster.jpg").read_bytes()
    # 原模板的内容区为绿色；白色底板让沿用主题色的图表保持足够对比度。
    chart_background = BytesIO()
    Image.new("RGB", (16, 16), "#FFFFFF").save(chart_background, format="PNG")
    builder = LocalPresentationBuilder(templates={"demo": TEMPLATE_PATH}, output_directory=OUTPUT_DIRECTORY,
                                       images={"fitness-photo": picture, "video-poster": video_poster,
                                               "chart-background": chart_background.getvalue()},
                                       videos={"squat-video": video})
    tool = create_build_presentation_tool(builder=builder)
    # 以下辅助函数只组织测试数据。坐标和尺寸为英寸；引用原始实际页码。
    def text(value: str, x: float, y: float, width: float, height: float,
             size: int = 20, color: str = "#263747") -> dict:
        return {"type": "text", "x": x, "y": y, "width": width, "height": height,
                "text": value, "font_size": size, "color": color}

    def content_page(role: str, title: str, elements: list[dict], body: str = "") -> dict:
        # 第4页已有标题、绿色正文区和装饰；替换其文字，保留原页面图形。
        return {"role": role, "source_slide_number": 4,
                "replacements": [{"shape_id": 3, "text": title}, {"shape_id": 20, "text": body}],
                "elements": elements}

    pages = [
        {"role": "封面", "source_slide_number": 1, "replacements": [
            {"shape_id": 2, "text": "一周健身计划"}, {"shape_id": 3, "text": "成人入门示例"},
            {"shape_id": 4, "text": "有氧 · 力量 · 恢复"}], "elements": []},
        {"role": "目录", "source_slide_number": 2, "replacements": [
            {"shape_id": 9, "text": "运动目标与强度"}, {"shape_id": 7, "text": "一周安排示例"},
            {"shape_id": 11, "text": "每周有氧时间"}, {"shape_id": 13, "text": "活动类型分配"},
            {"shape_id": 15, "text": "动作演示与安全提示"}, {"shape_id": 17, "text": "参考资料与素材"}], "elements": []},
        content_page("要点", "运动目标：先建立习惯", [
            text("成年人每周至少150分钟中等强度有氧活动，\n并在至少2天开展力量训练。\n从适合自己的活动量开始，逐步增加。", 1.0, 2.0, 6.6, 1.8, 17, "#FFFFFF"),
            {"type": "image", "x": 8.2, "y": 1.77, "width": 3.7, "height": 2.3, "image_id": "fitness-photo"},
        ]),
        content_page("一周安排", "一周安排示例", [
            {"type": "table", "x": 0.9, "y": 1.72, "width": 11.5, "height": 2.4,
             "headers": ["日期", "有氧活动", "力量 / 恢复"], "font_size": 13,
             "header_color": "#14734E", "header_text_color": "#FFFFFF",
             "row_colors": ["#FFFFFF", "#E7F5EE"], "text_color": "#243B32",
             "rows": [["周一", "快走 30 分钟", "全身力量"], ["周二", "快走 30 分钟", "放松"],
                      ["周三", "骑车 30 分钟", "休息"], ["周四", "快走 30 分钟", "全身力量"],
                      ["周五", "骑车 30 分钟", "放松"], ["周末", "自由活动", "休息或轻活动"]]},
        ]),
        content_page("柱状图", "每周有氧时间分布（示例，分钟）", [
            {"type": "image", "x": 0.9, "y": 1.68, "width": 11.5, "height": 2.45, "image_id": "chart-background"},
            {"type": "chart", "x": 0.9, "y": 1.68, "width": 11.5, "height": 2.45, "chart_type": "column",
             "categories": ["周一", "周二", "周三", "周四", "周五", "周末"],
             "style": {"title": "每日有氧时间（分钟）", "legend_visible": False, "data_labels": True},
             "category_axis": {"label_font_size": 10, "label_color": "#244A39", "line_color": "#719B86", "major_tick": "none"},
             "value_axis": {"minimum": 0, "maximum": 40, "major_unit": 10, "number_format": "0",
                            "label_font_size": 10, "label_color": "#244A39", "line_color": "#719B86",
                            "major_gridlines": True, "gridline_color": "#DFEAE2", "gridline_width": 0.5},
             "series": [{"name": "每周示例分钟数", "values": [30, 30, 30, 30, 30, 0], "color": "#12865B"}]},
        ]),
        content_page("饼图", "有氧活动如何分配（示例）", [
            text("快走 90 分钟\n骑车 60 分钟\n\n可根据喜好调整，不是固定比例。", 1.0, 2.0, 4.7, 1.9, 18, "#FFFFFF"),
            {"type": "image", "x": 6.7, "y": 1.72, "width": 5.3, "height": 2.4, "image_id": "chart-background"},
            {"type": "chart", "x": 6.7, "y": 1.72, "width": 5.3, "height": 2.4, "chart_type": "pie",
             "categories": ["快走 90 分钟", "骑车 60 分钟"],
             "series": [{"name": "示例活动时间", "values": [90, 60]}],
             "point_colors": ["#12865B", "#2BAA9A"]},
        ]),
        content_page("视频", "动作演示与安全提示", [
            {"type": "video", "x": 0.9, "y": 1.72, "width": 4.1, "height": 2.35,
             "video_id": "squat-video", "poster_image_id": "video-poster"},
            text("负重深蹲演示，并非个性化训练指导。初学者宜从适合的难度开始；如有疼痛或特殊健康情况，先咨询专业人士。", 5.4, 2.0, 6.4, 1.8, 16, "#FFFFFF"),
        ]),
        content_page("来源", "参考资料与素材", [],
                     "WHO：who.int/news-room/fact-sheets/detail/physical-activity\nCDC：cdc.gov/physical-activity-basics/guidelines/adults.html\n图片：Larry D. Moore，CC BY 4.0；视频：FitnessScape，CC BY 3.0（转码、提取封面）\n素材页面见配套调试文档。"),
    ]
    arguments = {"template_id": "demo", "pages": pages}
    print("\n【2】调用参数：", json.dumps(arguments, ensure_ascii=False, indent=2), flush=True)
    # 在此处断点，可进入builder观察页面复制、组合对象查找与文字替换。
    result = await tool.ainvoke(arguments)
    output = OUTPUT_DIRECTORY / result["file_name"]
    print("【3】工具结果：", json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    print("【4】请打开成品：", output, flush=True)
    presentation = Presentation(output)
    assert TEMPLATE_PATH.read_bytes() == original
    assert len(presentation.slides) == result["slide_count"] == 8
    assert "一周健身计划" in _slide_text(presentation.slides[0].shapes)
    assert "运动目标与强度" in _slide_text(presentation.slides[1].shapes)
    assert any(shape.has_table and shape.table.cell(1, 0).text == "周一" for shape in presentation.slides[3].shapes)
    table = next(shape.table for shape in presentation.slides[3].shapes if shape.has_table)
    assert str(table.cell(0, 0).fill.fore_color.rgb) == "14734E"
    assert str(table.cell(2, 0).fill.fore_color.rgb) == "E7F5EE"
    chart = next(shape.chart for shape in presentation.slides[4].shapes if shape.has_chart)
    assert chart.chart_type == XL_CHART_TYPE.COLUMN_CLUSTERED
    assert list(chart.series[0].values) == [30, 30, 30, 30, 30, 0]
    assert str(chart.series[0].format.fill.fore_color.rgb) == "12865B"
    assert chart.value_axis.minimum_scale == 0 and chart.value_axis.maximum_scale == 40
    assert chart.value_axis.major_unit == 10 and chart.value_axis.tick_labels.number_format == "0"
    assert str(chart.value_axis.format.line.color.rgb) == "719B86"
    pie = next(shape.chart for shape in presentation.slides[5].shapes if shape.has_chart)
    assert pie.chart_type == XL_CHART_TYPE.PIE and list(pie.series[0].values) == [90, 60]
    assert [str(point.format.fill.fore_color.rgb) for point in pie.series[0].points] == ["12865B", "2BAA9A"]
    assert any(shape.shape_type == MSO_SHAPE_TYPE.PICTURE and
               hashlib.sha256(shape.image.blob).digest() == hashlib.sha256(picture).digest()
               for shape in presentation.slides[2].shapes)
    # 文件包内有视频字节，表示已嵌入；这并不证明WPS能够播放。
    from zipfile import ZipFile
    with ZipFile(output) as archive:
        media = [archive.read(name) for name in archive.namelist() if name.startswith("ppt/media/")]
    assert video in media
    assert "参考资料与素材" in _slide_text(presentation.slides[-1].shapes)
    # 明确验证生成计划使用了真实模板页，而不是测试中临时创建的空白页。
    assert [item["source_slide_number"] for item in result["pages"]] == [1, 2, 4, 4, 4, 4, 4, 4]
