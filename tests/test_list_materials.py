"""第一个工具只演示并验证两件事：tool-calling JSON 和工具返回结果。

运行时加 -s 显示 print 输出：
uv run --locked python -m pytest tests/test_list_materials.py -s -q
下面的资料完全是测试样本，不会上传文件，也不会调用真实模型或网络。
"""

import json

import pytest
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool

from models.materials.material_summary import MaterialSummary
from tools.materials import create_list_materials_tool


@pytest.fixture
def material_tool() -> BaseTool:
    """准备两条样本，并创建一个绑定 demo 项目的工具供两个测试使用。"""
    materials = [
        MaterialSummary(
            project_id="demo",
            source_id="s01",
            name="员工手册.docx",
            origin="uploaded",
            format="docx",
            status="ready",
            version="v1",
        ),
        MaterialSummary(
            project_id="demo",
            source_id="s02",
            name="政策公告",
            origin="web",
            format="html",
            status="ready",
            version="v1",
            url="https://example.org/policy",
        ),
    ]
    return create_list_materials_tool(project_id="demo", materials=materials)


def test_tool_calling_json(material_tool: BaseTool) -> None:
    """第一件事：转换为模型可用的 function-tool JSON，并打印完整定义。"""
    definition = convert_to_openai_tool(material_tool)
    # 转换函数返回字典；json.dumps 才把字典变成可传输、可阅读的 JSON 文本。
    # ensure_ascii=False 保留中文，indent=2 用缩进方便观察参数结构。
    json_text = json.dumps(definition, ensure_ascii=False, indent=2)
    print("\n【1】提供给模型的 tool-calling JSON 定义：")
    print(json_text)

    # 读回 JSON，确认可解析，并检查工具名、参数及其说明确实存在。
    parsed = json.loads(json_text)
    assert parsed["type"] == "function"
    function = parsed["function"]
    assert function["name"] == "list_materials"
    assert function["description"]
    parameters = function["parameters"]
    assert parameters["type"] == "object"
    assert set(parameters["properties"]) == {"origin", "name_contains", "offset", "limit"}
    assert all(field.get("description") for field in parameters["properties"].values())


def test_tool_return_result(material_tool: BaseTool) -> None:
    """第二件事：直接调用工具，打印参数和返回结果，并核对样本答案。"""
    # 可直接修改这里的参数，再运行此测试观察不同查询结果。
    arguments = {"origin": "uploaded", "limit": 10}
    result = material_tool.invoke(arguments)

    print("\n【2】本次调用参数：")
    print(json.dumps(arguments, ensure_ascii=False, indent=2))
    print("【2】工具返回结果（以 JSON 展示）：")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 样本中只有一条上传资料，所以期望仅返回员工手册。
    # 修改样本或查询参数时，也应同步修改下方的预期结果。
    assert result == {
        "items": [
            {
                "source_id": "s01",
                "name": "员工手册.docx",
                "origin": "uploaded",
                "format": "docx",
                "status": "ready",
                "version": "v1",
                "url": None,
                "page_count": None,
            }
        ],
        "total": 1,
        "next_offset": None,
    }

