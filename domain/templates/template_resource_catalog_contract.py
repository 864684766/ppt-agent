"""模板目录能力协议；不依赖FastAPI、环境配置或S3 SDK。"""

from typing import Protocol
from models.templates.template_resource_response import TemplateResourceListResponse


class TemplateResourceError(RuntimeError):
    """存储操作安全错误；HTTP状态映射留给API，不暴露SDK原文。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code  # 固定错误分类，不是S3凭据或请求标识。


class TemplateResourceCatalog(Protocol):
    """同步列举模板；宿主负责连接生命周期及异步线程桥接。"""

    def list_resources(self, *, prefix: str, max_keys: int, continuation_token: str | None) -> TemplateResourceListResponse:
        """扫描一页对象并筛选PPTX；prefix是对象名前缀，不是本机目录。"""
        ...
