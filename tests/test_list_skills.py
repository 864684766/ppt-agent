"""打印工具JSON和真实本地技能列表，不联网、不运行技能脚本。

uv run --locked --no-sync python -m pytest tests/test_list_skills.py -s -q
结果项读取项目根目录skills/，属于真实文件系统接入验证，不使用模拟目录。
"""

import json

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool

from config.settings import PROJECT_ROOT, Settings
from config.logging_config import configure_logging
from integrations.local_skill_catalog import LocalSkillCatalog
from tools.skills.list_skills_tool import create_list_skills_tool


@pytest.mark.asyncio
async def test_tool_calling_json() -> None:
    """创建工具不会扫描文件，转换定义时即可看到参数说明。"""
    tool = create_list_skills_tool(catalog=LocalSkillCatalog(directory=PROJECT_ROOT / "skills"))
    json_text = json.dumps(convert_to_openai_tool(tool), ensure_ascii=False, indent=2)
    print("\n【1】list_skills的tool-calling JSON：")
    print(json_text)
    definition = json.loads(json_text)
    assert definition["type"] == "function"
    function = definition["function"]
    assert function["name"] == "list_skills"
    assert function["description"]
    properties = function["parameters"]["properties"]
    assert set(properties) == {"keyword"}
    assert properties["keyword"]["description"]


@pytest.mark.asyncio
async def test_tool_return_result() -> None:
    """从用户实际技能目录读取元数据；新增技能后无需改固定样本。"""
    # 单独运行测试不会启动FastAPI，由测试入口读取配置，组装全系统共用的日志。
    settings = Settings()
    log_path = configure_logging(
        directory=PROJECT_ROOT / "log", level=settings.log_level, output=settings.log_output,
    )
    # 相对源码位置确定项目根目录；不依赖启动目录，也不读取环境变量。
    catalog = LocalSkillCatalog(directory=PROJECT_ROOT / "skills")
    tool = create_list_skills_tool(catalog=catalog)
    # 空字符串列出全部。可改成法律或nutrition，再断点观察筛选结果。
    arguments = {"keyword": ""}
    # 在此打断点，F8后查看result；可单步进入扫描、YAML解析及筛选。
    result = await tool.ainvoke(arguments)
    print("\n【2】技能目录：", PROJECT_ROOT / "skills")
    print("【2】日志级别/目标：", settings.log_level, settings.log_output)
    print("【2】日志文件：", log_path if log_path else "未启用文件输出")
    print("【2】工具调用参数：")
    print(json.dumps(arguments, ensure_ascii=False, indent=2))
    print("【2】真实本地技能返回结果：")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # 实际目录可增删，不把固定三个技能写成永久测试条件。
    assert result["returned_count"] == len(result["items"])
    assert result["items"] == sorted(result["items"], key=lambda item: item["skill_id"])
    for item in result["items"]:
        assert item["name"] and item["description"]
        assert (PROJECT_ROOT / "skills" / item["skill_id"] / "SKILL.md").is_file()
