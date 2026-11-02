"""只检查工具JSON定义与实际返回结果；使用内存样本，无模型或真实文件。

uv run --locked python -m pytest tests/test_read_material.py -s -q
PyCharm调试pytest时，在附加参数中填-s以显示print输出。
"""

import json

import pytest
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool

from models.materials.material_fragment import MaterialFragment
from models.materials.material_source import MaterialSummary
from tools.materials import create_read_material_tool


@pytest.fixture
def material_read_tool() -> BaseTool:
    """假设解析模块已提供资料和正文；样本不是实际上传文件或法律依据。"""
    source = MaterialSummary(
        project_id="demo", source_id="s01", name="培训演示.pdf",
        origin="uploaded", format="pdf", status="ready", version="v1", page_count=12,
    )
    block = MaterialFragment(
        project_id="demo", source_id="s01", version="v1", block_id="block_31",
        text="演示正文：请核对完整条件。", page=12,
    )
    return create_read_material_tool(project_id="demo", materials=[source], fragments=[block])


def test_tool_calling_json(material_read_tool: BaseTool) -> None:
    """查看真正转换后的定义，确认必填定位和每个参数说明能被模型看到。"""
    definition = convert_to_openai_tool(material_read_tool)
    json_text = json.dumps(definition, ensure_ascii=False, indent=2)
    print("\n【1】read_material的tool-calling JSON：")
    print(json_text)
    parsed = json.loads(json_text)
    assert parsed["type"] == "function"
    function = parsed["function"]
    assert function["name"] == "read_material"
    assert function["description"]
    parameters = function["parameters"]
    assert parameters["type"] == "object"
    assert set(parameters["properties"]) == {"source_id", "version", "block_id", "offset", "max_chars"}
    assert set(parameters["required"]) == {"source_id", "version", "block_id"}
    assert all(field.get("description") for field in parameters["properties"].values())


def test_tool_return_result(material_read_tool: BaseTool) -> None:
    """同一个结果场景分两次读完原块，打印两次参数和结果，便于断点学习。"""
    arguments = {"source_id": "s01", "version": "v1", "block_id": "block_31", "max_chars": 5}
    result = material_read_tool.invoke(arguments)
    print("\n【2】首次调用参数：")
    print(json.dumps(arguments, ensure_ascii=False, indent=2))
    print("【2】首次读取结果：")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    assert result == {
        "source_id": "s01", "version": "v1",
        "location": {"block_id": "block_31", "page": 12},
        "text": "演示正文：", "offset": 0, "end_offset": 5,
        "total_chars": 13, "next_offset": 5,
    }

    # 续读必须复用相同定位；next_offset是原块字符偏移，不是第几次调用。
    arguments = {"source_id": "s01", "version": "v1", "block_id": "block_31", "offset": result["next_offset"]}
    result = material_read_tool.invoke(arguments)
    print("【2】续读调用参数：")
    print(json.dumps(arguments, ensure_ascii=False, indent=2))
    print("【2】续读返回结果：")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    assert result == {
        "source_id": "s01", "version": "v1",
        "location": {"block_id": "block_31", "page": 12},
        "text": "请核对完整条件。", "offset": 5, "end_offset": 13,
        "total_chars": 13, "next_offset": None,
    }
