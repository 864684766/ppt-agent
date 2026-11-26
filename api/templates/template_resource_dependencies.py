"""模板资源的配置与SDK组装边界；SDK连接随单次同步操作关闭。"""

from contextlib import contextmanager, closing
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlsplit

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from pydantic import ValidationError

from config.settings import Settings
from domain.templates.template_resource_catalog_contract import TemplateResourceCatalog, TemplateResourceError
from integrations.storage.s3_template_catalog import S3TemplateCatalog


@contextmanager
def open_template_storage_client(settings: Settings) -> Iterator[Any]:
    """在线程中创建/关闭S3客户端；不使用AWS默认凭据链或读取主机云身份。

    两个凭据均空表示匿名访问；仅填一个明确拒绝。传入显式配置避免请求意外
    使用宿主AWS凭据。匿名可用与否由桶策略决定，当前服务器匿名列举返回403。
    """
    try:
        endpoint = urlsplit(settings.s3_endpoint_url)
        # 不允许把控制台路径、预签名URL或URL内凭据误当作S3端点。
        if (
            endpoint.scheme not in {"http", "https"} or not endpoint.hostname
            or endpoint.username or endpoint.password or endpoint.query
            or endpoint.fragment or endpoint.path not in {"", "/"}
        ):
            raise ValueError("invalid endpoint")
        access = settings.s3_access_key_id.get_secret_value()
        secret = settings.s3_secret_access_key.get_secret_value()
        if bool(access) != bool(secret):
            raise ValueError("credentials must be paired")
    except (ValidationError, ValueError):
        raise TemplateResourceError("storage_configuration_invalid", "对象存储配置无效，请检查S3地址及成对的访问凭据。") from None
    # path模式请求endpoint/bucket，适用于RustFS的IP端点；不会拼成bucket.IP。
    config = Config(
        signature_version="s3v4" if access else UNSIGNED,
        s3={"addressing_style": "path"},
        connect_timeout=settings.s3_timeout_seconds,
        read_timeout=settings.s3_timeout_seconds,
        retries={"mode": "standard", "total_max_attempts": 1},
    )
    # boto3客户端有close但不支持with协议；closing负责正常/异常退出时关闭。
    with closing(boto3.session.Session().client(
        "s3", endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        aws_access_key_id=access or None, aws_secret_access_key=secret or None,
        config=config,
    )) as client:
        yield client


@contextmanager
def open_template_catalog() -> Iterator[TemplateResourceCatalog]:
    """保持目录接口的组装入口；Settings错误映射为安全存储配置错误。"""
    try:
        settings = Settings()
    except ValidationError:
        raise TemplateResourceError("storage_configuration_invalid", "对象存储配置无效，请检查本机环境变量。") from None
    with open_template_storage_client(settings) as client:
        yield S3TemplateCatalog(client=client, bucket=settings.s3_template_bucket)
