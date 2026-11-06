"""前端模板选择列表HTTP接口；不是Agent工具，不接收任意存储地址。"""

import asyncio
from typing import Annotated
from fastapi import APIRouter, HTTPException, Query

from api.template_resource_dependencies import open_template_catalog
from diagnostics.operation_logging import log_operation
from domain.templates.template_resource_catalog_contract import TemplateResourceError
from models.templates.template_resource_response import TemplateResourceListResponse, TemplateResourceErrorResponse

router = APIRouter(tags=["模板资源"])


@router.get("/templates", response_model=TemplateResourceListResponse,
            responses={code: {"model": TemplateResourceErrorResponse} for code in (400, 502, 503)},
            summary="读取对象存储中的PPTX模板候选列表")
@log_operation("templates.list_resources")
async def list_template_resources(
    prefix: Annotated[str, Query(max_length=1024, description="桶内对象名称前缀，默认空表示整个桶；如business/。不是文件名关键词或本机路径。")] = "",
    max_keys: Annotated[int, Query(ge=1, le=1000, description="一页最多扫描的S3对象数，默认100，范围1–1000；过滤PPTX后返回数量可能更少。")] = 100,
    continuation_token: Annotated[str | None, Query(min_length=1, max_length=8192, description="上次响应next_continuation_token原样传入；第一页省略，不自行生成。")] = None,
) -> TemplateResourceListResponse:
    """一页扫描后过滤PPTX，返回前端候选；不读取模板正文或调用模型。

    同步SDK操作在线程内执行，客户端创建和关闭也留在该线程。取消HTTP等待
    不保证中止底层SDK请求；其超时生效后退出并关闭资源。
    """
    def read_page() -> TemplateResourceListResponse:
        with open_template_catalog() as catalog:
            return catalog.list_resources(prefix=prefix, max_keys=max_keys, continuation_token=continuation_token)
    try:
        return await asyncio.to_thread(read_page)
    except TemplateResourceError as error:
        status = 503 if error.code == "storage_configuration_invalid" else 400 if error.code == "storage_invalid_cursor" else 502
        # 上游403映射502：这是后端访问存储失败，不是前端用户登录权限判定。
        raise HTTPException(status, detail={"code": error.code, "message": str(error)}) from None
