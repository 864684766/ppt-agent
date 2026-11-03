"""解析后的一个正文块：登记模块创建，检索/读取业务使用。

与 MaterialSummary 不同，这里保存正文与原文定位。来源的名称、格式、
状态仍由资料目录提供，避免在两个地方维护同一份元数据。
"""

from dataclasses import dataclass

from validators.materials.material_fragment_validator import validate_material_fragment


@dataclass(frozen=True, slots=True)
class MaterialFragment:
    """不可变正文片段；版本与目录摘要一致，block_id 在同来源版本内唯一。

    page 是原文件从1开始的页码，网页/无可靠页码的文件使用None。
    block_id 由未来的解析模块产生并保持稳定，不是搜索结果序号。
    text 保存此块的完整解析文本；工具返回的截取片段不替代这里的原文。
    """

    # 正文所属项目编号，用于与当前任务范围隔离。
    project_id: str
    # 所属资料编号，对应目录中同项目的MaterialSummary.source_id。
    source_id: str
    # 正文来源版本，必须与资料目录版本一致。
    version: str
    # 解析模块分配的正文块编号；在同一来源版本内唯一，不是检索结果序号。
    block_id: str
    # 该块完整的解析正文；保留原文空白，不用搜索摘要覆盖。
    text: str
    # 原文件页码，从1开始；网页或无法可靠定位时为None。
    page: int | None = None

    def __post_init__(self) -> None:
        """普通类型标注不执行校验，因此在对象构造后检查字段。"""
        validate_material_fragment(
            project_id=self.project_id, source_id=self.source_id,
            version=self.version, block_id=self.block_id,
            text=self.text, page=self.page,
        )
