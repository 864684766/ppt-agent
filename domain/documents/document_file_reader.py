"""校验文件并按格式选择注入的读取器，供不同入口复用。"""

from collections.abc import Mapping

from domain.documents.document_reader_contract import DocumentReader
from domain.uploads.file_upload_validation import validate_upload_metadata, validate_uploaded_content
from models.documents.document_content import DocumentContent, DocumentReadLimits


class DocumentFileReader:
    """读取调用方提供的文件字节；不管理磁盘路径、模型或HTTP。"""

    def __init__(self, *, readers: Mapping[str, DocumentReader], limits: DocumentReadLimits,
                 max_file_bytes: int, max_uncompressed_bytes: int) -> None:
        """读取器、正文限制和文件大小限制由宿主提供；调用方负责其资源。"""
        self._readers = readers
        self._limits = limits
        self._max_file_bytes = max_file_bytes
        self._max_uncompressed_bytes = max_uncompressed_bytes

    def read(self, *, file_name: str, content: bytes) -> tuple[str, DocumentContent]:
        """校验名称和真实字节，再根据格式解析；出错时保留原始错误分类。"""
        name, file_format = validate_upload_metadata(file_name=file_name, content_type=None)
        validate_uploaded_content(content=content, file_format=file_format, max_file_bytes=self._max_file_bytes,
                                  max_uncompressed_bytes=self._max_uncompressed_bytes)
        reader = self._readers.get(file_format)
        if reader is None:
            raise ValueError(f"未配置 {file_format} 格式的文件读取器。")
        return name, reader.read(content=content, limits=self._limits)
