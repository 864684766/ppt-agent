"""只检查工具JSON与真实PPTX返回报告，便于PyCharm断点调试。

uv run --locked --no-sync python -m pytest tests/test_check_presentation.py -s -q
不调用模型、网络、Office或渲染；当前用已有模板作为产物样本验证检查工具。
"""

import json
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool

from config.settings import PROJECT_ROOT
from integrations.templates.local_presentation_checker import LocalPresentationChecker
from tools.presentations.check_presentation_tool import create_check_presentation_tool

# 可直接改成自己的PPTX路径；None默认读取ppt-demo中第一份PPTX。
PPTX_PATH: Path | None = None
# 宿主设置要求，不是模型可选参数。示例模板不符合8–12页时返回fail是正常结果。
MIN_SLIDES = 8
MAX_SLIDES = 12


def test_tool_calling_json() -> None:
    """转换为OpenAI兼容JSON，确认模型能看到用途、限制和唯一参数含义。"""
    tool = create_check_presentation_tool(checker=LocalPresentationChecker(artifacts={}))
    definition = json.loads(json.dumps(convert_to_openai_tool(tool), ensure_ascii=False))
    print("\n【1】工具JSON：", json.dumps(definition, ensure_ascii=False, indent=2), flush=True)
    function = definition["function"]
    assert definition["type"] == "function" and function["name"] == "check_presentation"
    assert function["parameters"]["required"] == ["artifact_id"]
    assert set(function["parameters"]["properties"]) == {"artifact_id"}
    assert "不是URL、文件路径" in function["parameters"]["properties"]["artifact_id"]["description"]
    assert all(word in function["description"] for word in ["not_checked", "passed", "slide_numbers", "不做OCR"])


@pytest.mark.asyncio
async def test_tool_return_result_from_real_pptx() -> None:
    """真实读取一份PPTX并打印全部报告；不是模型选择工具或Office打开验收。"""
    if PPTX_PATH is not None:
        path = PPTX_PATH
    else:
        candidates = sorted(p for p in (PROJECT_ROOT / "ppt-demo").glob("*.pptx") if not p.name.startswith("~$"))
        assert candidates, "请在ppt-demo放入PPTX，或填写PPTX_PATH。"
        path = candidates[0]
    checker = LocalPresentationChecker(
        artifacts={"demo-presentation": path}, min_slides=MIN_SLIDES, max_slides=MAX_SLIDES,
    )
    tool = create_check_presentation_tool(checker=checker)
    arguments = {"artifact_id": "demo-presentation"}
    print("\n【2】调用参数：", json.dumps(arguments, ensure_ascii=False, indent=2), flush=True)
    # 在下一行打断点；进入checker.check可看包校验、PPT解析和报告组装。
    result = await tool.ainvoke(arguments)
    print("【2】检查报告：", json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    # 从原始XML独立核对真实页数；不把检查器自己的输出再当成预期。
    with ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("ppt/presentation.xml"))
    expected_count = len(root.findall("p:sldIdLst/p:sldId", {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}))
    assert result["slide_count"] == expected_count
    rules = {item["rule_id"]: item for item in result["checks"]}
    assert rules["package_structure"]["status"] == "pass"
    assert rules["page_count"]["status"] == ("pass" if MIN_SLIDES <= expected_count <= MAX_SLIDES else "fail")
    assert result["passed"] == (MIN_SLIDES <= expected_count <= MAX_SLIDES)
    assert rules["office_open"]["status"] == rules["outline_coverage"]["status"] == "not_checked"
