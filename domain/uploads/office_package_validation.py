"""有限量地校验DOCX、XLSX、PPTX的Open XML包；不落盘或提取正文。"""

from io import BytesIO
from pathlib import PurePosixPath
from xml.etree import ElementTree
from zipfile import BadZipFile, LargeZipFile, ZipFile
from zlib import error as ZlibError

from domain.uploads.file_upload_errors import FileUploadError


# 三种Office文件共享ZIP封装，但主XML、内容类型及XML根标签不同。
# 每个元组依次为：主XML路径、必须声明的内容类型、必须匹配的XML根标签。
_OFFICE_FORMATS = {
    "pptx": (
        "ppt/presentation.xml",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
        "{http://schemas.openxmlformats.org/presentationml/2006/main}presentation",
    ),
    "docx": (
        "word/document.xml",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document",
    ),
    "xlsx": (
        "xl/workbook.xml",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
        "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}workbook",
    ),
}


def validate_office_package(*, content: bytes, file_format: str, max_uncompressed_bytes: int) -> None:
    """检查条目、CRC、累计展开字节及关键结构；不保证Office可完整打开。

    同时检查ZIP目录声明与实际读取量；最多5000个条目，关键XML每份最多2 MiB。
    不接受加密、宏内容、绝对/上级目录路径或重复条目，不使用extractall。
    """
    if file_format not in _OFFICE_FORMATS:
        raise FileUploadError("unsupported_format", "当前仅支持DOCX、XLSX、PPTX的Office包检查。")
    main_part, main_content_type, main_root_tag = _OFFICE_FORMATS[file_format]
    try:
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            names = [item.filename for item in entries]
            if len(entries) > 5000 or sum(item.file_size for item in entries) > max_uncompressed_bytes:
                raise FileUploadError("archive_limit_exceeded", "Office文件条目数或累计解压大小超过限制。")
            if len(names) != len(set(names)) or any(
                "\\" in name or ":" in name or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
                for name in names
            ):
                raise FileUploadError("invalid_file", "Office文件包含重复或不支持的内部路径。")
            required = {"[Content_Types].xml", "_rels/.rels", main_part}
            if not required.issubset(names) or any(item.flag_bits & 1 for item in entries):
                raise FileUploadError("invalid_file", "文件不是可读取的Office文件包，或包含加密条目。")
            if any("vbaproject" in name.lower() for name in names):
                raise FileUploadError("unsupported_format", "当前不接受包含宏的文档。")
            # 读取完每个条目时zipfile会校验CRC；仅在内存中逐块读取并丢弃。
            total = 0
            for entry in entries:
                with archive.open(entry) as source:
                    while chunk := source.read(64 * 1024):
                        total += len(chunk)
                        if total > max_uncompressed_bytes:
                            raise FileUploadError("archive_limit_exceeded", "Office文件实际解压大小超过限制。")
            key_xml = {}
            for name in required:
                if archive.getinfo(name).file_size > 2 * 1024 * 1024:
                    raise FileUploadError("archive_limit_exceeded", "Office文件关键XML超过2 MiB限制。")
                key_xml[name] = ElementTree.fromstring(archive.read(name))
            types = key_xml["[Content_Types].xml"]
            if any("macroenabled" in item.get("ContentType", "").lower() or "vba" in item.get("ContentType", "").lower() for item in types):
                raise FileUploadError("unsupported_format", "当前不接受声明宏内容的文档。")
            if types.tag != "{http://schemas.openxmlformats.org/package/2006/content-types}Types" or not any(
                item.get("PartName") == "/" + main_part
                and item.get("ContentType") == main_content_type
                for item in types
            ):
                raise FileUploadError("invalid_file", "文件内部声明的Office类型与扩展名不匹配。")
            if key_xml[main_part].tag != main_root_tag:
                raise FileUploadError("invalid_file", "Office主XML结构与所选文件格式不匹配。")
            relationships = key_xml["_rels/.rels"]
            if relationships.tag != "{http://schemas.openxmlformats.org/package/2006/relationships}Relationships" or not any(
                item.get("Type") == "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
                and item.get("Target", "").lstrip("/") == main_part
                and item.get("TargetMode") != "External"
                for item in relationships
            ):
                raise FileUploadError("invalid_file", "Office根关系未指向预期的内部主文档。")
    except (BadZipFile, LargeZipFile, ElementTree.ParseError, LookupError, OSError, RuntimeError, NotImplementedError, EOFError, ValueError, ZlibError) as error:
        if isinstance(error, FileUploadError):
            raise
        raise FileUploadError("invalid_file", "Office文件包损坏、压缩方式不支持或关键XML不可读取。") from None
