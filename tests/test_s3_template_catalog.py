"""只验证存储适配模块，不建立HTTP接口测试，不访问真实RustFS或读取密钥。"""

from datetime import datetime, timezone
from contextlib import closing
import json
import boto3
from botocore.stub import Stubber
import pytest

from domain.templates.template_resource_catalog_contract import TemplateResourceError
from integrations.storage.s3_template_catalog import S3TemplateCatalog


def test_pptx_filter_preserves_object_key_and_storage_pagination() -> None:
    """验证普通文件被排除，同时保留下一页游标及同名模板的完整路径。"""
    # 显式假凭据和SDK Stubber隔离外网；验证的是本项目适配，不是S3内部实现。
    with closing(boto3.client("s3", region_name="us-east-1", aws_access_key_id="test-only", aws_secret_access_key="test-only")) as client:
        with Stubber(client) as stub:
            stub.add_response("list_objects_v2", {
                "Contents": [
                    {"Key": "business/简洁.PPTX", "Size": 100, "LastModified": datetime(2026, 11, 6, tzinfo=timezone.utc)},
                    {"Key": "readme.txt", "Size": 3},
                ], "IsTruncated": True, "NextContinuationToken": "opaque-next-page",
            }, {"Bucket": "ppts", "Prefix": "", "MaxKeys": 2})
            result = S3TemplateCatalog(client=client, bucket="ppts").list_resources(prefix="", max_keys=2, continuation_token=None)
            print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
            assert result.returned_count == 1 and result.scanned_count == 2
            assert result.items[0].object_key == "business/简洁.PPTX"
            assert result.is_truncated and result.next_continuation_token == "opaque-next-page"
            stub.assert_no_pending_responses()


def test_access_denied_returns_safe_error_without_server_original() -> None:
    """上游403映射为可理解错误，不回传原始服务端消息。"""
    with closing(boto3.client("s3", region_name="us-east-1", aws_access_key_id="test-only", aws_secret_access_key="test-only")) as client:
        with Stubber(client) as stub:
            stub.add_client_error("list_objects_v2", service_error_code="AccessDenied", service_message="private-server-original", http_status_code=403)
            with pytest.raises(TemplateResourceError) as captured:
                S3TemplateCatalog(client=client, bucket="ppts").list_resources(prefix="", max_keys=100, continuation_token=None)
            assert captured.value.code == "storage_access_denied"
            assert "private-server-original" not in str(captured.value)
