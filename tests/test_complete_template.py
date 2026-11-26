"""两个测试：工具JSON和真实PPTX补全结果；供PyCharm断点与人工打开核对。"""

import json
from pathlib import Path

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool
from pptx import Presentation

from config.settings import PROJECT_ROOT
from integrations.templates.local_template_completer import LocalTemplateCompleter
from tools.templates.complete_template_tool import create_complete_template_tool


# 指定测试模板；None时选择ppt-demo里按名称排序的第一份PPTX。
TEMPLATE_PATH: Path | None = None
# 选择原模板中的实际参考页，复制该页已有的图形和图片。
SOURCE_SLIDE_NUMBER = 4
# 最终总页数（包括原有页面），允许8至12页。
TARGET_SLIDE_COUNT = 10
# 新文件保存到这里；每次运行使用新文件名，不覆盖原模板。
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "completed-templates"


def test_tool_calling_json() -> None:
    tool = create_complete_template_tool(completer=LocalTemplateCompleter(templates={}, output_directory=OUTPUT_DIRECTORY))
    definition = json.loads(json.dumps(convert_to_openai_tool(tool), ensure_ascii=False))
    print("\n【1】工具JSON：", json.dumps(definition, ensure_ascii=False, indent=2), flush=True)
    assert definition["function"]["name"] == "complete_template"
    assert set(definition["function"]["parameters"]["properties"]) == {"template_id", "pages", "target_slide_count"}
    assert "参考页" in definition["function"]["description"]


@pytest.mark.asyncio
async def test_tool_result_with_real_template() -> None:
    """读取真实模板，复制参考页至指定总页数，输出供人工查看的新文件。"""
    candidates = sorted(p for p in (PROJECT_ROOT / "ppt-demo").glob("*.pptx") if not p.name.startswith("~$"))
    path = TEMPLATE_PATH if TEMPLATE_PATH is not None else (candidates[0] if candidates else None)
    assert path is not None, "请填写TEMPLATE_PATH或在ppt-demo中放入PPTX。"
    original_bytes = path.read_bytes()
    tool = create_complete_template_tool(completer=LocalTemplateCompleter(
        templates={"demo-template": path}, output_directory=OUTPUT_DIRECTORY,
    ))
    original_count = len(Presentation(str(path)).slides)
    arguments = {"template_id": "demo-template", "target_slide_count": TARGET_SLIDE_COUNT,
                 "pages": [{"role": "内容页示例", "source_slide_number": SOURCE_SLIDE_NUMBER}
                           for _ in range(TARGET_SLIDE_COUNT - original_count)]}
    print("\n【2】调用参数：", json.dumps(arguments, ensure_ascii=False, indent=2), flush=True)
    # 在这里打断点；单步进入补全器查看版式选择与新页面的创建。
    result = await tool.ainvoke(arguments)
    output_path = OUTPUT_DIRECTORY / result["file_name"]
    print("【2】补全结果：", json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    print("【3】请打开新文件核对：", output_path, flush=True)
    completed = Presentation(output_path)
    assert path.read_bytes() == original_bytes
    assert len(completed.slides) == TARGET_SLIDE_COUNT == result["slide_count"]
    assert len(completed.slides[-1].shapes) == len(completed.slides[SOURCE_SLIDE_NUMBER - 1].shapes)
