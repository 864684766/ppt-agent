"""list_materials 工具的公开结果字段，与内部业务实体区分。

结果只包含允许返回给模型的元数据，例如不公开内部 project_id。
TypedDict 用于类型检查和阅读，不会自动执行运行时校验；不要把它
当作 Pydantic BaseModel 使用。当前由工具显式选择字段并通过测试验证。
"""

from typing import Literal, TypedDict


class MaterialListItem(TypedDict):
    """明确选择可公开字段，不把内部对象全部转成字典交给模型。"""

    source_id: str
    name: str
    origin: Literal["uploaded", "web"]
    format: str
    status: Literal["pending", "ready", "failed"]
    version: str
    url: str | None
    page_count: int | None


class ListMaterialsOutput(TypedDict):
    """稳定的工具返回结构；空结果也保留同样的字段。"""

    items: list[MaterialListItem]
    total: int
    next_offset: int | None

