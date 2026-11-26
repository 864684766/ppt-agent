"""输出工具JSON并使用真实模板创建可编辑页面，便于PyCharm断点查看。"""

import json
from pathlib import Path

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool
from pptx import Presentation

from config.settings import PROJECT_ROOT
from integrations.templates.local_template_page_creator import LocalTemplatePageCreator
from tools.templates.create_template_page_tool import create_template_page_tool

# None使用ppt-demo第一份真实PPTX；换模板后应先检查其实际版式编号和页面尺寸。
TEMPLATE_PATH: Path | None = None
LAYOUT_ID = "/ppt/slideLayouts/slideLayout7.xml"
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "created-template-pages"


def test_tool_calling_json() -> None:
    creator = LocalTemplatePageCreator(templates={}, output_directory=OUTPUT_DIRECTORY)
    definition = json.loads(json.dumps(convert_to_openai_tool(create_template_page_tool(creator=creator)), ensure_ascii=False))
    print("\n【1】工具JSON：", json.dumps(definition, ensure_ascii=False, indent=2), flush=True)
    assert definition["function"]["name"] == "create_template_page"
    assert set(definition["function"]["parameters"]["properties"]) == {"template_id", "layout_id", "background_color", "elements"}


@pytest.mark.asyncio
async def test_tool_result_with_real_template() -> None:
    """将方案画到真实模板，输出新文件，检查页数和可编辑对象。"""
    candidates = sorted(p for p in (PROJECT_ROOT / "ppt-demo").glob("*.pptx") if not p.name.startswith("~$"))
    path = TEMPLATE_PATH if TEMPLATE_PATH is not None else (candidates[0] if candidates else None)
    assert path is not None, "请在ppt-demo放入PPTX，或设置TEMPLATE_PATH。"
    original = path.read_bytes()
    original_count = len(Presentation(str(path)).slides)
    creator = LocalTemplatePageCreator(templates={"demo": path}, output_directory=OUTPUT_DIRECTORY)
    tool = create_template_page_tool(creator=creator)
    # 根据参考截图手工填写方案：坐标单位英寸，字号单位pt。
    # 元素按顺序绘制，先画色块、后放文字；这不是模型自动识图设计。
    arguments = {"template_id": "demo", "layout_id": LAYOUT_ID, "background_color": "#FFFFFF", "elements": [
        {"kind": "rectangle", "x": 0, "y": 0.55, "width": 0.32, "height": 0.46, "color": "#334C78"},
        {"kind": "rectangle", "x": 0.42, "y": 0.55, "width": 0.15, "height": 0.46, "color": "#334C78"},
        {"kind": "text", "x": 0.72, "y": 0.48, "width": 4.2, "height": 0.65, "color": "#303239", "text": "智研- 微代码", "font_size": 27, "font_name": "Microsoft YaHei"},
        {"kind": "text", "x": 8.95, "y": 0.5, "width": 4.0, "height": 0.5, "color": "#777777", "text": "应用生成智能化，人人都是程序员", "font_size": 15, "font_name": "Microsoft YaHei"},
        {"kind": "rectangle", "x": 0.32, "y": 1.86, "width": 5.9, "height": 4.2, "color": "#F3F4F6"},
        {"kind": "rectangle", "x": 0.9, "y": 1.64, "width": 3.8, "height": 0.55, "color": "#3451F4"},
        {"kind": "text", "x": 1.95, "y": 1.68, "width": 2.5, "height": 0.48, "color": "#FFFFFF", "text": "智能 · 流程", "font_size": 19, "font_name": "Microsoft YaHei"},
        {"kind": "text", "x": 0.42, "y": 2.36, "width": 5.68, "height": 3.55, "color": "#24416E", "text": "流程编排与自动化：通过流程引擎，可以将表单与业务流程相关联，实现流程的自动化处理。提交表单时，流程引擎根据预先定义的流程规则和步骤，自动推进表单的处理流程。\n\n精准控制流程流转，将对应的审批、处理送至对应负责人、负责组织手中。\n\n自动化流程校验，根据用户权限对数据进行隔离，上级部门可以查看下级部门的流程处理进度。", "font_size": 13, "font_name": "Microsoft YaHei"},
        {"kind": "rectangle", "x": 6.3, "y": 1.86, "width": 6.8, "height": 4.2, "color": "#F4F5F7"},
        {"kind": "rectangle", "x": 6.3, "y": 1.86, "width": 6.8, "height": 0.23, "color": "#2036DA"},
        {"kind": "text", "x": 6.35, "y": 1.84, "width": 1.5, "height": 0.22, "color": "#FFFFFF", "text": "流程发起", "font_size": 7, "font_name": "Microsoft YaHei"},
        {"kind": "rectangle", "x": 6.4, "y": 2.1, "width": 6.6, "height": 3.72, "color": "#FFFFFF"},
        {"kind": "text", "x": 6.65, "y": 2.2, "width": 2.8, "height": 0.35, "color": "#555555", "text": "设备类型：  请选择设备", "font_size": 10, "font_name": "Microsoft YaHei"},
        {"kind": "text", "x": 6.65, "y": 2.68, "width": 2.8, "height": 0.35, "color": "#555555", "text": "TextArea：", "font_size": 10, "font_name": "Microsoft YaHei"},
        {"kind": "rectangle", "x": 7.65, "y": 2.67, "width": 1.65, "height": 0.35, "color": "#EDF3FF"},
        {"kind": "text", "x": 6.65, "y": 3.18, "width": 2.8, "height": 0.35, "color": "#555555", "text": "供应商：  请输入供应商", "font_size": 10, "font_name": "Microsoft YaHei"},
        {"kind": "text", "x": 6.65, "y": 3.65, "width": 2.8, "height": 0.35, "color": "#555555", "text": "价格：       请输入价格", "font_size": 10, "font_name": "Microsoft YaHei"},
        {"kind": "rectangle", "x": 9.72, "y": 2.2, "width": 0.02, "height": 3.1, "color": "#E5E7EB"},
        {"kind": "rectangle", "x": 10.05, "y": 2.42, "width": 0.35, "height": 0.35, "color": "#2842E8"},
        {"kind": "text", "x": 10.55, "y": 2.4, "width": 1.9, "height": 0.4, "color": "#555555", "text": "发起人", "font_size": 10, "font_name": "Microsoft YaHei"},
        {"kind": "rectangle", "x": 10.05, "y": 3.03, "width": 0.35, "height": 0.35, "color": "#2842E8"},
        {"kind": "text", "x": 10.55, "y": 3.02, "width": 1.9, "height": 0.4, "color": "#555555", "text": "审批人", "font_size": 10, "font_name": "Microsoft YaHei"},
        {"kind": "rectangle", "x": 10.05, "y": 3.64, "width": 0.35, "height": 0.35, "color": "#2842E8"},
        {"kind": "text", "x": 10.55, "y": 3.63, "width": 1.9, "height": 0.4, "color": "#555555", "text": "负责人", "font_size": 10, "font_name": "Microsoft YaHei"},
        {"kind": "rectangle", "x": 10.05, "y": 4.25, "width": 0.35, "height": 0.35, "color": "#2842E8"},
        {"kind": "text", "x": 10.55, "y": 4.24, "width": 1.9, "height": 0.4, "color": "#555555", "text": "抄送人", "font_size": 10, "font_name": "Microsoft YaHei"},
    ]}
    print("\n【2】调用参数：", json.dumps(arguments, ensure_ascii=False, indent=2), flush=True)
    # 在这里打断点：单步查看版式选择、坐标校验和每个PPT对象的绘制。
    result = await tool.ainvoke(arguments)
    output = OUTPUT_DIRECTORY / result["file_name"]
    print("【3】工具结果：", json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    print("【4】请打开文件查看最后一页：", output, flush=True)
    created = Presentation(output)
    assert path.read_bytes() == original
    assert len(created.slides) == original_count + 1 == result["slide_number"]
    assert any(shape.has_text_frame and shape.text == "智研- 微代码" for shape in created.slides[-1].shapes)
    assert result["element_count"] == len(arguments["elements"])
