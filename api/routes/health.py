"""健康检查路由，用于验证 HTTP 服务能够正常响应。"""

from fastapi import APIRouter
from api.schemas.health import HealthResponse


# 同类接口集中到一个路由对象，由 api/router.py 汇总后挂载到应用。
router = APIRouter(tags=["健康检查"])


@router.get("/health", response_model=HealthResponse, summary="检查服务是否运行")
async def check_health() -> HealthResponse:
    """返回服务存活状态，不访问网络或读取项目资料。

    Returns:
        status 为 ok 的响应对象，由 FastAPI 序列化为 JSON。
    """
    return HealthResponse()
