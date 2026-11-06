"""存储字节读取模块测试，不建立HTTP测试文件，不访问真实OSS。"""

from contextlib import closing
from io import BytesIO
import boto3
from botocore.response import StreamingBody
from botocore.stub import Stubber
import pytest

from domain.templates.template_resource_catalog_contract import TemplateResourceError
from integrations.storage.s3_template_file_reader import S3TemplateFileReader


def test_download_returns_bytes_and_closes_body() -> None:
    """对象Key保持原样；只验证下载字节和资源归属，不冒充PPTX解析验证。"""
    source = BytesIO(b"sample-object-bytes")
    with closing(boto3.client("s3", region_name="us-east-1", aws_access_key_id="test-only", aws_secret_access_key="test-only")) as client:
        with Stubber(client) as stub:
            stub.add_response("get_object", {"Body": StreamingBody(source, 19), "ContentLength": 19}, {"Bucket": "ppts", "Key": "business/公司模板.pptx"})
            data = S3TemplateFileReader(client=client, bucket="ppts").read_file(object_key="business/公司模板.pptx", max_bytes=100)
            print("下载字节数：", len(data))
            assert data == b"sample-object-bytes"
            assert source.closed


def test_stream_limit_closes_body_when_declared_length_is_absent() -> None:
    """即使没有声明大小，也检查实际字节；超限关闭Body，不返回截断模板。"""
    source = BytesIO(b"oversized")
    with closing(boto3.client("s3", region_name="us-east-1", aws_access_key_id="test-only", aws_secret_access_key="test-only")) as client:
        with Stubber(client) as stub:
            stub.add_response("get_object", {"Body": StreamingBody(source, 9)})
            with pytest.raises(TemplateResourceError) as captured:
                S3TemplateFileReader(client=client, bucket="ppts").read_file(object_key="模板.pptx", max_bytes=3)
            assert captured.value.code == "template_too_large"
            assert source.closed


def test_missing_object_has_safe_error() -> None:
    """对象可能在前端选中后被删除；明确返回不存在，不回传服务端错误原文。"""
    with closing(boto3.client("s3", region_name="us-east-1", aws_access_key_id="test-only", aws_secret_access_key="test-only")) as client:
        with Stubber(client) as stub:
            stub.add_client_error("get_object", service_error_code="NoSuchKey", service_message="private-original", http_status_code=404)
            with pytest.raises(TemplateResourceError) as captured:
                S3TemplateFileReader(client=client, bucket="ppts").read_file(object_key="模板.pptx", max_bytes=100)
            assert captured.value.code == "template_not_found"
            assert "private-original" not in str(captured.value)
