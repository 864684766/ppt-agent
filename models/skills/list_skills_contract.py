"""list_skills的模型输入与公开结果；字段说明与工具Schema一起维护。"""

from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field


class ListSkillsInput(BaseModel):
    """模型只选择关键词，不选择本机技能目录。"""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    keyword: str = Field(default="", max_length=200, description=(
        "可选，按技能编号、名称或用途说明做不区分大小写的字面子串筛选，最多200字符。"
        "省略或空字符串列出全部可读取介绍的本地技能，例如法律或nutrition。"
        "不是语义搜索，不自动翻译或扩展同义词，不传文件路径。"
    ))


class SkillListItem(TypedDict):
    """工具只公开选择技能所需的信息，不返回SKILL.md正文或磁盘路径。"""

    # 本地技能一级目录名，供后续read_skill定位；与name可能不同。
    skill_id: str
    # 技能头部name，不保证是中文名称。
    name: str
    # SKILL.md中作者填写的用途说明，按原介绍返回，不分析技能内部实现。
    description: str
    # 声明的版本字符串；未提供时为None，JSON为null。
    version: str | None


class ListSkillsOutput(TypedDict):
    """TypedDict只描述字典形状，不自动执行校验。"""

    # 关键词过滤后的有效技能摘要，按skill_id排序；无匹配时为空列表。
    items: list[SkillListItem]
    # 本次过滤后的条数，等于items长度；本版无分页。
    returned_count: int
