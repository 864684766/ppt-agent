"""read_material 的模型输入与公开输出；不执行文件读取或正文查询。"""

from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field


class ReadMaterialInput(BaseModel):
    """定位一份资料中的一个正文块；项目范围由宿主绑定。"""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    source_id: str = Field(min_length=1, max_length=200, description=(
        "必填，当前项目已登记资料的来源ID，例如s01；来自list_materials或search_materials。"
        "不是文件路径、URL或资料名称；不能切换项目。"
    ))
    version: str = Field(min_length=1, max_length=200, description=(
        "必填，资料版本标识，例如v1；使用search_materials返回的version，"
        "必须与当前目录一致。版本过期会报错，不能把旧定位静默用于新资料。"
    ))
    block_id: str = Field(min_length=1, max_length=200, description=(
        "必填，正文块ID，例如block_31；使用search_materials返回的location.block_id。"
        "不是页码或结果序号，不要自行猜测；一次读取一个块，不自动包含相邻块。"
    ))
    offset: int = Field(default=0, ge=0, description=(
        "从完整正文块的第几个Python字符开始读取，从0开始，不是字节或token。"
        "首次省略或填0；续读填上次next_offset。next_offset为null时该块读取完毕。"
        "例如上次next_offset为2000，本次填2000；需保持来源、版本和块ID一致。"
    ))
    max_chars: int = Field(default=2000, ge=1, le=8000, description=(
        "本次最多返回的Python字符数，1至8000，默认2000；不是字节或token。"
        "例如填500最多读取500字符，长块通过next_offset续读，不会静默丢掉剩余正文。"
    ))


class MaterialReadLocation(TypedDict):
    """原文定位；page从1开始，未知为None，不编造页码。"""

    block_id: str
    page: int | None


class ReadMaterialOutput(TypedDict):
    """实际读取范围为[offset, end_offset)，均相对完整块；仅描述字典类型。"""

    source_id: str
    version: str
    location: MaterialReadLocation
    text: str
    offset: int
    end_offset: int
    total_chars: int
    next_offset: int | None
