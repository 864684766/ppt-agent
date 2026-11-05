"""工具JSON及ppt-demo真实PPTX结果验证，不调用模型、网络、Office或渲染。

uv run --locked --no-sync python -m pytest tests/test_inspect_template.py -s -q
"""

import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool

from config.logging_config import configure_logging
from config.settings import PROJECT_ROOT, Settings
from integrations.templates.local_template_inspector import LocalTemplateInspector
from models.templates.template_structure import TemplateShape
from tools.templates.inspect_template_tool import create_inspect_template_tool


def find_demo_templates() -> dict[str, Path]:
    """仅测试入口扫描样本目录，以文件名（含扩展名）作为本次登记编号。

    正式上传后应由宿主登记模块提供映射；工具本身不扫描ppt-demo。
    """
    return {
        path.name: path for path in sorted((PROJECT_ROOT / "ppt-demo").glob("*.pptx"))
        if not path.name.startswith("~$")
    }


@pytest.mark.asyncio
async def test_tool_calling_json() -> None:
    """不打开文件即可转换；确认模型看得到模板编号和返回信息的含义。"""
    tool = create_inspect_template_tool(inspector=LocalTemplateInspector(templates={}))
    json_text = json.dumps(convert_to_openai_tool(tool), ensure_ascii=False, indent=2)
    print("\n【1】inspect_template的tool-calling JSON：")
    print(json_text)
    definition = json.loads(json_text)
    assert definition["type"] == "function"
    function = definition["function"]
    assert function["name"] == "inspect_template"
    assert "EMU" in function["description"] and "children" in function["description"]
    parameters = function["parameters"]
    assert set(parameters["properties"]) == {"template_id"}
    assert parameters["required"] == ["template_id"]
    assert "不是文件路径" in parameters["properties"]["template_id"]["description"]


@pytest.mark.asyncio
async def test_tool_return_result_from_demo_files() -> None:
    """逐份真实样本输出全部结构；直接核对包内XML页数、页面尺寸及原文件hash。"""
    settings = Settings()
    configure_logging(
        directory=PROJECT_ROOT / "log", level=settings.log_level, output=settings.log_output,
    )
    templates = find_demo_templates()
    assert templates, "请先将.pptx样本放入项目ppt-demo目录。"
    tool = create_inspect_template_tool(inspector=LocalTemplateInspector(templates=templates))
    for template_id, path in templates.items():
        arguments = {"template_id": template_id}
        print("\n【2】调用参数：")
        print(json.dumps(arguments, ensure_ascii=False, indent=2))
        original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        # 在此打断点查看result；可单步进入页面、组合、占位符提取过程。
        result = await tool.ainvoke(arguments)
        print("【2】完整结构返回结果：")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("【2】概要：", path.name, "页数=", result["slide_count"],
              "母版=", len(result["masters"]), "版式=", len(result["layouts"]))
        # 独立读取原始Open XML核对，不把解析适配器自身的输出当成预期样本。
        with ZipFile(path) as archive:
            root = ElementTree.fromstring(archive.read("ppt/presentation.xml"))
        ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
        assert result["slide_count"] == len(root.findall("p:sldIdLst/p:sldId", ns))
        assert result["slide_count"] == len(result["slides"])
        size = root.find("p:sldSz", ns)
        assert size is not None
        assert result["slide_width_emu"] == int(size.attrib["cx"])
        assert result["slide_height_emu"] == int(size.attrib["cy"])
        assert result["template_id"] == template_id and result["file_name"] == path.name
        assert result["sha256"] == original_hash
        assert hashlib.sha256(path.read_bytes()).hexdigest() == original_hash
        layout_ids = {layout["layout_id"] for layout in result["layouts"]}
        master_ids = {master["master_id"] for master in result["masters"]}
        assert all(slide["layout_id"] in layout_ids for slide in result["slides"])
        assert all(layout["master_id"] in master_ids for layout in result["layouts"])
        # 样本含组合时，核对递归提取的对象数量，避免顶层数量正确却漏掉内部对象。
        def count_shapes(shapes: list[TemplateShape]) -> int:
            return sum(1 + count_shapes(shape["children"]) for shape in shapes)

        with ZipFile(path) as archive:
            for slide in result["slides"]:
                if not slide["shapes"]:
                    continue
                part = slide["shapes"][0]["object_id"].split("#", maxsplit=1)[0].lstrip("/")
                slide_xml = ElementTree.fromstring(archive.read(part))
                shape_tags = {"sp", "pic", "graphicFrame", "cxnSp", "grpSp", "contentPart"}
                expected_objects = sum(
                    1 for element in slide_xml.iter()
                    if element.tag in {f"{{{ns['p']}}}{tag}" for tag in shape_tags}
                )
                assert count_shapes(slide["shapes"]) == expected_objects
