"""健康检查接口的响应结构。"""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """健康检查响应；不代表模型或 PPT 生成等外部能力已经可用。"""

    # 固定取值使接口契约和 OpenAPI 文档保持一致。
    status: Literal["ok"] = "ok"
