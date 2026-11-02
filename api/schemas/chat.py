"""普通对话接口的请求结构，不承担大纲等业务规则。"""

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """只接受一条非空消息；限制长度以避免调试时误传大段文件。"""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    message: str = Field(min_length=1, max_length=10000, description="用户消息，最多 10000 字符")
