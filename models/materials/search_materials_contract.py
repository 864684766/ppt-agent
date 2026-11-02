"""search_materials 工具契约：在一处查看模型输入和公开输出。

Input 使用 Pydantic 声明参数、运行时校验及模型可见的 Field 描述；
必要例子写入 description，避免工具转换时 examples 被省略。
Output 及其条目使用 TypedDict 描述字典形状，不自动执行运行时校验，
也不会仅凭类型标注自动成为发送给模型的输出 Schema。
这里只定义数据约定，不执行查询；内部业务结果另见 material_query_results.py。
"""

from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SearchMaterialsInput(BaseModel):
    """拒绝未知字段；project_id及正文由宿主绑定，不向模型开放。"""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    queries: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(
        min_length=1, max_length=8,
        description=(
            "必填，1至8个关键词，每个1至200字符。忽略大小写，按字面子串查正文，"
            "不是正则或语义搜索；多个词按任意一个命中。"
            "例如[经济补偿,解除劳动合同]。同义词需明确列入，不会自动扩展。"
        ),
    )
    source_ids: list[Annotated[str, Field(min_length=1, max_length=200)]] | None = Field(
        default=None, min_length=1, max_length=100,
        description=(
            "可选，限定当前项目的来源ID，例如[s01,s02]；省略或null搜索项目内全部ready资料。"
            "不能传空列表；指定不存在或未ready的来源会报错，不伪装为无命中。"
        ),
    )
    origin: Literal["all", "uploaded", "web"] = Field(
        default="all",
        description=(
            "来源过滤：all=全部，uploaded=上传业务文件，web=已抓取并登记的网页正文。"
            "默认all；例如只看上传资料填uploaded。与source_ids共同过滤，不重新联网。"
        ),
    )
    max_results: int = Field(
        default=10, ge=1, le=50,
        description=(
            "最多返回几个命中正文块，1至50，默认10；例如填5最多返回5块。"
            "同一块命中多个词只返回一次。truncated为true时可缩小范围后重新搜索。"
        ),
    )
    max_chars_per_match: int = Field(
        default=300, ge=50, le=1000,
        description=(
            "每条命中文本最多返回多少个Python字符，50至1000，默认300，不是字节或token。"
            "例如填100返回最多100字符；长块围绕最早命中截取，text_truncated表示原块未完整返回。"
        ),
    )

    @field_validator("queries", "source_ids")
    @classmethod
    def remove_duplicates(cls, values: list[str] | None) -> list[str] | None:
        """精确重复项只保留第一次；空白/长度已由字段约束检查。"""
        return list(dict.fromkeys(values)) if values is not None else None


# 以下是工具返回给模型的公开字段；由工具适配器显式组装。
class MaterialMatchLocation(TypedDict):
    """原文定位；page从1开始，未知为None，block_id用于后续精确读取。"""

    block_id: str
    page: int | None


class MaterialSearchItem(TypedDict):
    """不返回内部project_id或本地路径；matched_queries对应完整原文块。"""

    source_id: str
    version: str
    location: MaterialMatchLocation
    matched_queries: list[str]
    text: str
    text_truncated: bool


class SearchMaterialsOutput(TypedDict):
    """零命中返回空matches；truncated表示条数上限，不是单条文本截取。"""

    matches: list[MaterialSearchItem]
    total_matches: int
    truncated: bool
