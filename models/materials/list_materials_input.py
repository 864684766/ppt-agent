"""list_materials 工具的入参字段、声明式校验和模型填参说明。

Pydantic Field 同时参与运行时校验与 JSON Schema 生成；这些约束
必须留在入参声明处，模型才能看到类型、枚举、范围、默认值和描述。
这属于“调用请求是否合法”，不负责判断业务资料本身是否合法。
当前转换会省略 examples，所以必要例子也直接写入 description。
"""

from typing import Literal

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

