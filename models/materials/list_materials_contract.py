"""list_materials 工具契约：在一处查看模型输入和公开输出。

Input 使用 Pydantic 声明参数、运行时校验及模型可见的 Field 描述；
必要例子写入 description，避免工具转换时 examples 被省略。
Output 及其条目使用 TypedDict 描述字典形状，不自动执行运行时校验，
也不会仅凭类型标注自动成为发送给模型的输出 Schema。
这里只定义数据约定，不执行查询；内部业务结果另见 material_query_results.py。
"""

from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field


class ListMaterialsInput(BaseModel):
    """模型可传入的参数；拒绝未知字段、字符串数字及布尔数字等误用。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    origin: Literal["all", "uploaded", "web"] = Field(
        default="all", description=(
            "筛选来源类型：all=当前项目全部已登记业务资料；"
            "uploaded=用户上传的业务参考文件；web=已抓取并登记的网页正文。"
            "省略时为all。这里不会联网搜索，也不包含PPT设计模板或技能资源。"
            "例如只看上传文件时填uploaded。"
        ),
        examples=["all", "uploaded", "web"],
    )
    name_contains: str = Field(
        default="", max_length=200,
        description=(
            "仅按资料显示名称做字面子串过滤，不搜索正文，不是正则表达式。"
            "例如填劳动可匹配劳动合同法.pdf。忽略首尾空白和大小写，"
            "最多200字符；省略或填空字符串表示不按名称过滤。"
        ),
        examples=["", "劳动", "员工手册"],
    )
    offset: int = Field(
        default=0, ge=0,
        description=(
            "在过滤并排序后的结果中跳过多少条，从0开始，必须为非负整数。"
            "首次查询省略或填0；继续翻页时填上次返回的next_offset，"
            "并保持同样的来源/名称过滤条件。next_offset为null时停止翻页。"
            "例如上次next_offset为20，本次填20。"
        ),
        examples=[0, 20],
    )
    limit: int = Field(
        default=20, ge=1, le=100,
        description=(
            "本次最多返回多少条资料摘要，必须为1至100的整数，默认20。"
            "这是目录条数，不是正文长度、页码或检索轮数；"
            "当total大于当前已返回范围时，通过next_offset继续翻页。"
            "例如只需查看最多10条摘要时填10。"
        ),
        examples=[10, 20],
    )


# 以下是工具返回给模型的公开字段；由工具适配器显式组装。
class MaterialListItem(TypedDict):
    """明确选择可公开字段，不把内部对象全部转成字典交给模型。"""

    # 项目内资料编号，可用于后续检索和引用。
    source_id: str
    # 资料显示名称，不是本机文件路径。
    name: str
    # 来源类型：uploaded上传文件，web已登记网页。
    origin: Literal["uploaded", "web"]
    # 资料格式名，例如pdf、docx、html。
    format: str
    # 解析状态：pending待解析、ready可读、failed解析失败。
    status: Literal["pending", "ready", "failed"]
    # 资料版本标识，读取时必须与正文版本一致。
    version: str
    # 网页原始地址；上传资料为None（JSON中为null）。
    url: str | None
    # 原文件总页数；未知为None（JSON中为null）。
    page_count: int | None


class ListMaterialsOutput(TypedDict):
    """稳定的工具返回结构；空结果也保留同样的字段。"""

    # 本次返回的资料摘要列表；没有符合条件的资料时为空列表。
    items: list[MaterialListItem]
    # 筛选后全部资料的总条数，可大于本次items长度。
    total: int
    # 下次目录调用的offset；None表示分页结束，单位是资料条数。
    next_offset: int | None
