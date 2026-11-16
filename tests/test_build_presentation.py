"""查看工具JSON与真实模板成品，供PyCharm断点和WPS人工核对。"""

import json
import hashlib
from pathlib import Path

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from config.settings import PROJECT_ROOT
from integrations.templates.local_presentation_builder import LocalPresentationBuilder
from tools.presentations.build_presentation_tool import create_build_presentation_tool

# 本示例针对ppt-demo/公司模板.pptx；换模板需通过inspect_template重新确认页码和shape_id。
TEMPLATE_PATH: Path = PROJECT_ROOT / "ppt-demo" / "公司模板.pptx"
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "built-presentations"
# 公开示例来自MDN；测试仅读取本地文件，不在模型调用时联网。
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
    """手工页面计划生成8页成品，验证顺序、文字以及原模板不变。"""
    original = TEMPLATE_PATH.read_bytes()
    # 测试模拟宿主读取文件后按编号提供字节；运行时工具不访问互联网或任意路径。
    picture = (MEDIA_DIRECTORY / "reference-photo.png").read_bytes()
    video = (MEDIA_DIRECTORY / "reference-video.mp4").read_bytes()
    audio = (MEDIA_DIRECTORY / "reference-audio.mp3").read_bytes()
    builder = LocalPresentationBuilder(templates={"demo": TEMPLATE_PATH}, output_directory=OUTPUT_DIRECTORY,
                                       images={"sample-image": picture}, videos={"sample-video": video},
                                       audios={"sample-audio": audio})
    tool = create_build_presentation_tool(builder=builder)
    # shape_id来自该模板的inspect_template；第2页25、第3页20位于组合对象内部。
    pages = [{"role": "封面", "source_slide_number": 1,
              "replacements": [{"shape_id": 18, "text": "健康饮食指南"}]}]
    pages.append({"role": "目录", "source_slide_number": 2,
                  "replacements": [{"shape_id": 25, "text": "健康饮食要点"}]})
    for number in range(1, 6):
        pages.append({"role": "内容页", "source_slide_number": 3,
                      "replacements": [{"shape_id": 20, "text": f"健康饮食要点 {number}"}]})
    # 同一页混合五类内容；元素依列表顺序绘制，真实布局仍需用户打开核对。
    # 原第3页有大面积装饰，改用第5页作为参考并清空其示例文字。
    pages[2]["source_slide_number"] = 5
    pages[2]["replacements"] = [{"shape_id": 23, "text": ""}]
    pages[2]["elements"] = [
        {"type": "text", "x": 0.6, "y": 1.1, "width": 3.3, "height": 0.5, "text": "饮食计划示例", "color": "#263238"},
        {"type": "image", "x": 0.7, "y": 0.25, "width": 1.5, "height": 0.8, "image_id": "sample-image"},
        {"type": "chart", "x": 6.8, "y": 2.0, "width": 4.4, "height": 3.0, "chart_type": "column",
         "categories": ["谷类", "蔬菜", "蛋白质"], "series": [{"name": "示例", "values": [3, 4, 2]}]},
        {"type": "table", "x": 0.6, "y": 2.0, "width": 5.0, "height": 1.6, "headers": ["餐次", "示例"],
         "rows": [["早餐", "牛奶"], ["午餐", "蔬菜"]]},
        {"type": "list", "x": 0.6, "y": 4.1, "width": 5.0, "height": 1.5,
         "items": [{"text": "食物多样", "level": 0}, {"text": "规律进餐", "level": 1}]},
    ]
    # 第4页演示视频和音频。视频可传用户提供的图片作封面，音频使用默认媒体图标。
    pages[3]["source_slide_number"] = 5
    pages[3]["replacements"] = [{"shape_id": 23, "text": ""}]
    pages[3]["elements"] = [
        {"type": "text", "x": 0.7, "y": 0.4, "width": 5.0, "height": 0.5, "text": "用户媒体示例"},
        {"type": "video", "x": 0.7, "y": 1.1, "width": 6.4, "height": 3.6,
         "video_id": "sample-video", "poster_image_id": "sample-image"},
        {"type": "audio", "x": 8.2, "y": 1.5, "width": 1.0, "height": 1.0, "audio_id": "sample-audio"},
    ]
    pages.append({"role": "来源页", "source_slide_number": 5,
                  "replacements": [{"shape_id": 23, "text": "来源：示例资料"}]})
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
    assert "健康饮食指南" in _slide_text(presentation.slides[0].shapes)
    assert "健康饮食要点" in _slide_text(presentation.slides[1].shapes)
    mixed = presentation.slides[2]
    assert "饮食计划示例" in _slide_text(mixed.shapes)
    chart = next(shape.chart for shape in mixed.shapes if shape.has_chart)
    assert list(chart.series[0].values) == [3, 4, 2]
    assert any(shape.has_table and shape.table.cell(1, 0).text == "早餐" for shape in mixed.shapes)
    assert any(shape.shape_type == MSO_SHAPE_TYPE.PICTURE and
               hashlib.sha256(shape.image.blob).digest() == hashlib.sha256(picture).digest()
               for shape in mixed.shapes)
    assert "• 食物多样" in _slide_text(mixed.shapes)
    assert result["pages"][2]["element_count"] == 5
    # 文件包内实际有视频、音频字节，表示已嵌入；这并不证明WPS能够播放。
    from zipfile import ZipFile
    with ZipFile(output) as archive:
        media = [archive.read(name) for name in archive.namelist() if name.startswith("ppt/media/")]
    assert video in media and audio in media
    assert "来源：示例资料" in _slide_text(presentation.slides[-1].shapes)
