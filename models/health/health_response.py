"""健康检查接口的响应结构。"""

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """健康检查响应；不代表模型或 PPT 生成等外部能力已经可用。"""

    # 固定取值使接口契约和 OpenAPI 文档保持一致。
    status: Literal["ok"] = Field(default="ok", description="服务存活状态，固定为ok；不表示模型、网络或PPT生成能力已就绪。")
