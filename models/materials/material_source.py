"""单份业务资料摘要：描述资料所属项目、来源和解析状态。

这里的资料只指内容参考来源；模板和技能由各自模块管理。
本模块定义数据；详细校验委托 validators/materials/material_metadata_validator.py。
不定义工具参数、不上传、不解析文件，也不访问数据库或创建全局资料仓库。
"""

from dataclasses import dataclass
from typing import Literal

from validators.materials.material_metadata_validator import validate_material_metadata


MaterialOrigin = Literal["uploaded", "web"]
MaterialStatus = Literal["pending", "ready", "failed"]


@dataclass(frozen=True, slots=True)
class MaterialSummary:
    """由外层登记模块提供的一条不可变业务资料摘要。

    project_id：这份资料属于哪个 PPT 制作项目。
    查询时，后端只允许工具查看当前项目的资料；
    当前项目由后端绑定，模型不能通过工具参数切换项目。

    source_id：资料在所属项目中的编号，方便后续读取和引用。
    同一个项目里的不同资料不能使用相同编号；
    不同项目可以使用相同编号。

    version 指资料版本，不是列表页码。页数未知时为 None，不能假报为 0。

    format 为 pdf/docx/pptx/html 等格式名称；url 仅用于网页原始地址。

    status 为 pending（待解析）、ready（可读取）、failed（解析失败）。

    本对象不是完整的文件记录，不携带本机路径、正文或异常原文。
    """

    # 以下字段由宿主登记：模型只能看公开摘要，不能修改项目绑定。
    # 所属PPT项目编号；内部隔离范围，由宿主绑定，不向模型公开。
    project_id: str
    # 所属项目内唯一的资料编号；供检索、读取和引用使用，不是本地路径。
    source_id: str
    # 资料显示名称，例如员工手册.pdf。
    name: str
    # 资料来源：uploaded为上传业务文件，web为已登记网页。
    origin: MaterialOrigin
    # 文件或正文格式，例如pdf、docx、html，不含点号。
    format: str
    # 解析状态：pending待解析、ready解析成功、failed解析失败；上传成功不等于ready。
    status: MaterialStatus
    # 资料版本标识，例如v1；必须与对应正文块版本一致。
    version: str
    # 可选字段用 None 表示未知/不适用；不要将未知页数写成 0。
    # 原网页地址；上传资料为None，不公开本机文件路径。
    url: str | None = None
    # 原文件总页数；未知为None，不用0代替未知。
    page_count: int | None = None

    def __post_init__(self) -> None:
        """dataclass 完成构造后自动执行，尽早拒绝无效登记数据。

        类型标注本身不会拦截错误值，因此在数据进入业务模块时校验。
        frozen=True 禁止后续修改字段，slots=True 限制随意增加属性。

        数据校验
        """
        # 数据校验交给专门规则模块；创建对象的任何入口都不能跳过它。
        validate_material_metadata(
            project_id=self.project_id,
            source_id=self.source_id,
            name=self.name,
            origin=self.origin,
            format=self.format,
            status=self.status,
            version=self.version,
            url=self.url,
            page_count=self.page_count,
        )
