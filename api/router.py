"""API 路由组装入口，集中声明应用启用的接口模块。"""

from fastapi import APIRouter

from api.routes.health import router as health_router
from api.routes.chat import router as chat_router


# 每个元素是一组接口，后续添加大纲、模板等路由时在此显式登记。
# 显式列表便于检查启用范围，也便于定位模块导入与路由冲突问题。
# 业务路由只声明自身路径，例如 /chat。公共前缀在此统一设置，
# 后续新增项目、模板等接口时，将对应路由加入此清单即可。
BUSINESS_ROUTERS: tuple[APIRouter, ...] = (chat_router,)

business_router = APIRouter(prefix="/ppt-agent/v1")
for module_router in BUSINESS_ROUTERS:
    business_router.include_router(module_router)

# 健康检查独立于业务版本，继续提供 GET /health。
# 应用入口只挂载 api_router，不需要感知这里的分组细节。
api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(business_router)
