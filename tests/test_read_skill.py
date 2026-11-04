"""只检查工具JSON及实际技能正文，使用本地文件，不调用模型或执行脚本。

uv run --locked --no-sync python -m pytest tests/test_read_skill.py -s -q
"""

import json

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool

from config.logging_config import configure_logging
from config.settings import PROJECT_ROOT, Settings
from integrations.local_skill_reader import LocalSkillReader
from tools.skills.read_skill_tool import create_read_skill_tool


@pytest.mark.asyncio
async def test_tool_calling_json() -> None:
    """转换时不读取文件；确保模型能看到用途、必填参数及参数含义。"""
    tool = create_read_skill_tool(reader=LocalSkillReader(directory=PROJECT_ROOT / "skills"))
    json_text = json.dumps(convert_to_openai_tool(tool), ensure_ascii=False, indent=2)
    print("\n【1】read_skill的tool-calling JSON：")
    print(json_text)
    definition = json.loads(json_text)
    assert definition["type"] == "function"
    function = definition["function"]
    assert function["name"] == "read_skill"
    assert "完整Markdown" in function["description"]
    parameters = function["parameters"]
    assert set(parameters["properties"]) == {"skill_id"}
    assert parameters["required"] == ["skill_id"]
    assert "list_skills" in parameters["properties"]["skill_id"]["description"]


@pytest.mark.asyncio
async def test_tool_return_result() -> None:
    """实际读取已有技能；可修改skill_id，在ainvoke行断点查看content。"""
    settings = Settings()
    configure_logging(
        directory=PROJECT_ROOT / "log", level=settings.log_level, output=settings.log_output,
    )
    tool = create_read_skill_tool(reader=LocalSkillReader(directory=PROJECT_ROOT / "skills"))
    # 使用list_skills实际返回的编号，可改成flyai或legal-issue-research。
    arguments = {"skill_id": "flyai"}
    print("\n【2】工具调用参数：")
    print(json.dumps(arguments, ensure_ascii=False, indent=2))
    # 在这里打断点：单步可进入工具、读取适配器和共享头部校验。
    result = await tool.ainvoke(arguments)
    print("【2】实际技能完整返回结果：")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    expected_content = (
        PROJECT_ROOT / "skills" / arguments["skill_id"] / "SKILL.md"
    ).read_text(encoding="utf-8-sig")
    assert result == {
        "skill_id": arguments["skill_id"], "resource_path": "SKILL.md", "content": expected_content,
    }
