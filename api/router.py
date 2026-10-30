"""API 路由组装入口，集中声明应用启用的接口模块。"""

from fastapi import APIRouter

from api.health import router as health_router


# 每个元素是一组接口，后续添加大纲、模板等路由时在此显式登记。
# 显式列表便于检查启用范围，也便于定位模块导入与路由冲突问题。
ROUTERS: tuple[APIRouter, ...] = (health_router,)

api_router = APIRouter()
for module_router in ROUTERS:
    api_router.include_router(module_router)
