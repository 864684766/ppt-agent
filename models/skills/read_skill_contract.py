"""read_skill的模型输入与公开输出；不包含脚本执行参数或本机绝对路径。"""

from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field


class ReadSkillInput(BaseModel):
    """模型使用发现结果中的编号，不能指定任意文件或附属资源。"""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    skill_id: str = Field(min_length=1, pattern=r"^[^/\\:.\s][^/\\:]*$", description=(
        "必填，从list_skills结果原样选择skill_id，例如fitness-nutrition；"
        "它是技能目录编号，可能与name不同。不能传绝对路径、斜杠、反斜杠、冒号或以点开头的路径。"
        "只读取该技能的SKILL.md，不传references或scripts路径。"
    ))


class ReadSkillOutput(TypedDict):
    """正文原样交给模型理解；TypedDict只定义结果形状，不自动校验。"""

    # 本次读取的目录编号，对应输入及list_skills返回的skill_id。
    skill_id: str
    # 技能内相对文件标识，本版恒为SKILL.md；不是本机绝对路径。
    resource_path: str
    # UTF-8读取的完整Markdown，包含YAML头部，不截断；移除BOM并规范换行。
    content: str
