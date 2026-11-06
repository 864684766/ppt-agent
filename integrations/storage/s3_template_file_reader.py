"""读取RustFS/S3模板原始字节，不解析PPTX，不保存磁盘文件。"""

from contextlib import closing
import logging
from typing import Any
from botocore.exceptions import BotoCoreError, ClientError

from diagnostics.operation_logging import log_operation
from domain.templates.template_resource_catalog_contract import TemplateResourceError

logger = logging.getLogger(__name__)


class S3TemplateFileReader:
    """SDK客户端由宿主创建/关闭；本类负责get_object返回的Body流关闭。"""

    def __init__(self, *, client: Any, bucket: str) -> None:
        self._client = client
        self._bucket = bucket  # 固定由配置注入，不接受前端指定其他桶或服务器。

    @log_operation("storage.read_template")
    def read_file(self, *, object_key: str, max_bytes: int) -> bytes:
        """按原样Key读取；不是URL，不unquote、不拼接本地路径。

        ContentLength先检查一次，流中再按实际收到的字节累计，防止声明不准确。
        成功/失败/超限都关闭Body；返回bytes由本次请求持有，无跨请求缓存。
        """
        if not object_key.lower().endswith(".pptx"):
            raise TemplateResourceError("template_format_invalid", "template_key必须选择模板列表中的PPTX对象标识，不是下载地址。")
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=object_key)
            # StreamingBody不应交给外层长期保管，确保SDK连接关闭前先释放下载流。
            with closing(response["Body"]) as body:
                if response.get("ContentLength", 0) > max_bytes:
                    raise TemplateResourceError("template_too_large", "OSS模板超过S3_TEMPLATE_MAX_FILE_BYTES字节上限。")
                content = bytearray()
                while True:
                    # 达到上限后最多再读1字节即可判定超限，避免多分配一个完整块。
                    chunk = body.read(min(64 * 1024, max_bytes - len(content) + 1))
                    if not chunk:
                        break
                    content.extend(chunk)
                    if len(content) > max_bytes:
                        raise TemplateResourceError("template_too_large", "OSS模板实际下载量超过S3_TEMPLATE_MAX_FILE_BYTES字节上限。")
            if not content:
                raise TemplateResourceError("template_empty", "OSS模板为空文件，请选择其他模板。")
            logger.info("event=template_downloaded size_bytes=%s", len(content))
            return bytes(content)
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code", "")
            if code in {"NoSuchKey", "NotFound", "404"}:
                raise TemplateResourceError("template_not_found", "选中的OSS模板不存在，请刷新列表并原样传入object_key。") from None
            if code in {"AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch"}:
                raise TemplateResourceError("storage_access_denied", "无法下载OSS模板，请检查访问凭据及ppts桶对象的s3:GetObject权限。") from None
            raise TemplateResourceError("storage_unavailable", "对象存储读取失败，请检查桶配置和服务状态。") from None
        except BotoCoreError:
            raise TemplateResourceError("storage_unavailable", "模板下载失败或中断，请检查网络、超时及对象存储状态。") from None
