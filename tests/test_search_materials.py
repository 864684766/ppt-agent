"""只测试两件事：模型工具JSON定义和检索结果；-s可查看完整输出。

uv run --locked python -m pytest tests/test_search_materials.py -s -q
正文是手写演示句子，不是法律依据，不会访问实际文件或网页。
"""

import json

import pytest
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool

from models.materials.material_fragment import MaterialFragment
from models.materials.material_source import MaterialSummary
from tools.materials import create_search_materials_tool


@pytest.fixture
def material_search_tool() -> BaseTool:
    """提供两份ready资料、三个正文块，其中两个块包含目标词。"""
    materials = [
        MaterialSummary(
            project_id="demo", source_id="s01", name="员工培训资料.pdf",
            origin="uploaded", format="pdf", status="ready", version="v1", page_count=12,
        ),
        MaterialSummary(
            project_id="demo", source_id="s02", name="政策解读演示网页",
            origin="web", format="html", status="ready", version="v1",
            url="https://example.org/policy",
        ),
    ]
    fragments = [
        MaterialFragment(
            project_id="demo", source_id="s01", version="v1", block_id="block_01",
            text="本次培训介绍公司日常考勤制度。", page=1,
        ),
        MaterialFragment(
            project_id="demo", source_id="s01", version="v1", block_id="block_31",
            text="演示资料：讨论解除劳动合同与经济补偿的处理流程。", page=12,
        ),
        MaterialFragment(
            project_id="demo", source_id="s02", version="v1", block_id="paragraph_02",
            text="演示网页：经济补偿的适用条件需要核对原文。",
        ),
    ]
    return create_search_materials_tool(
        project_id="demo", materials=materials, fragments=fragments,
    )


def test_tool_calling_json(material_search_tool: BaseTool) -> None:
    """转换并打印模型实际可见的function-tool定义，不调用真实模型。"""
    definition = convert_to_openai_tool(material_search_tool)
    json_text = json.dumps(definition, ensure_ascii=False, indent=2)
    print("\n【1】search_materials 的 tool-calling JSON：")
    print(json_text)

    parsed = json.loads(json_text)
    assert parsed["type"] == "function"
    function = parsed["function"]
    assert function["name"] == "search_materials"
    assert function["description"]
    parameters = function["parameters"]
    assert parameters["type"] == "object"
    assert set(parameters["properties"]) == {
        "queries", "source_ids", "origin", "max_results", "max_chars_per_match",
    }
    assert "queries" in parameters["required"]
    assert all(field.get("description") for field in parameters["properties"].values())


def test_tool_return_result(material_search_tool: BaseTool) -> None:
    """打印参数及实际结果；同块命中两个词，仍只返回一条结果。"""
    arguments = {
        "queries": ["经济补偿", "解除劳动合同"],
        "max_results": 10,
    }
    result = material_search_tool.invoke(arguments)
    print("\n【2】本次调用参数：")
    print(json.dumps(arguments, ensure_ascii=False, indent=2))
    print("【2】检索返回结果：")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 两个来源各命中一个块；页码未知的网页使用None，不编造页码。
    assert result == {
        "matches": [
            {
                "source_id": "s01",
                "version": "v1",
                "location": {"block_id": "block_31", "page": 12},
                "matched_queries": ["经济补偿", "解除劳动合同"],
                "text": "演示资料：讨论解除劳动合同与经济补偿的处理流程。",
                "text_truncated": False,
            },
            {
                "source_id": "s02",
                "version": "v1",
                "location": {"block_id": "paragraph_02", "page": None},
                "matched_queries": ["经济补偿"],
                "text": "演示网页：经济补偿的适用条件需要核对原文。",
                "text_truncated": False,
            },
        ],
        "total_matches": 2,
        "truncated": False,
    }
