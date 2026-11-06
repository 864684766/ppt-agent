"""RustFS/S3对象列表适配；使用注入的boto3客户端，不读.env或管理其连接。"""

import logging
from typing import Any
from botocore.exceptions import BotoCoreError, ClientError

from diagnostics.operation_logging import log_operation
from domain.templates.template_resource_catalog_contract import TemplateResourceError
from models.templates.template_resource_response import TemplateResourceItem, TemplateResourceListResponse

logger = logging.getLogger(__name__)


class S3TemplateCatalog:
    """只读目录：不下载、上传、删除对象，不构造公开URL或签名链接。"""

    def __init__(self, *, client: Any, bucket: str) -> None:
        self._client = client  # SDK客户端由外层创建并关闭；Any是第三方动态SDK边界。
        self._bucket = bucket  # 服务端配置固定桶，不允许HTTP调用方切换任意桶。

    @log_operation("storage.list_templates")
    def list_resources(self, *, prefix: str, max_keys: int, continuation_token: str | None) -> TemplateResourceListResponse:
        """调用ListObjectsV2一页；S3先分页，本地再过滤后缀，不自动遍历全桶。"""
        parameters = {"Bucket": self._bucket, "Prefix": prefix, "MaxKeys": max_keys}
        if continuation_token is not None:
            parameters["ContinuationToken"] = continuation_token
        try:
            page = self._client.list_objects_v2(**parameters)
        except ClientError as error:
            # 只根据固定服务端错误码选安全提示；不打印响应/原始错误字符串。
            code = error.response.get("Error", {}).get("Code", "")
            if code in {"AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch"}:
                raise TemplateResourceError("storage_access_denied", "无法列举模板桶，请检查RustFS访问凭据及s3:ListBucket权限。") from None
            if code == "NoSuchBucket":
                raise TemplateResourceError("storage_bucket_not_found", "模板桶不存在，请检查S3_TEMPLATE_BUCKET配置。") from None
            if code in {"InvalidArgument", "InvalidToken"}:
                raise TemplateResourceError("storage_invalid_cursor", "分页游标或存储查询参数无效，请从第一页重新查询。") from None
            raise TemplateResourceError("storage_unavailable", "对象存储服务返回错误，请检查服务状态及配置。") from None
        except BotoCoreError:
            raise TemplateResourceError("storage_unavailable", "无法连接对象存储，请检查网络、连接地址及超时配置。") from None
        objects = page.get("Contents", [])
        items = [TemplateResourceItem(
            object_key=item["Key"], file_name=item["Key"].rsplit("/", 1)[-1],
            size_bytes=item["Size"], last_modified=item.get("LastModified"),
        ) for item in objects if item["Key"].lower().endswith(".pptx")]
        more = bool(page.get("IsTruncated", False))
        token = page.get("NextContinuationToken") if more else None
        if more and not token:
            raise TemplateResourceError("storage_unavailable", "对象存储分页响应缺少下一页游标。")
        logger.info("event=templates_listed scanned_count=%s returned_count=%s is_truncated=%s", len(objects), len(items), more)
        return TemplateResourceListResponse(
            bucket=self._bucket, items=items, returned_count=len(items),
            scanned_count=len(objects), is_truncated=more, next_continuation_token=token,
        )
