"""共享PPTX加载和安全另存；不决定页面设计或Agent工具行为。"""

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from pptx import Presentation

from domain.uploads.file_upload_errors import FileUploadError
from domain.uploads.office_package_validation import validate_office_package


class TemplateFileError(RuntimeError):
    """模板文件无法读取、校验或保存；文本可安全用于对外提示。"""


def load_template(path: Path):
    """有界读取并复用Office包校验；返回内存中的python-pptx文稿对象。"""
    if path.suffix.lower() != ".pptx":
        raise TemplateFileError("当前只支持PPTX模板。")
    try:
        with path.open("rb") as source:
            content = source.read(50 * 1024 * 1024 + 1)
        if not content or len(content) > 50 * 1024 * 1024:
            raise TemplateFileError("模板为空或超过50 MiB。")
        validate_office_package(content=content, file_format="pptx", max_uncompressed_bytes=100 * 1024 * 1024)
        return Presentation(BytesIO(content))
    except FileUploadError:
        raise TemplateFileError("模板未通过Office包检查，请确认文件有效且未加密。") from None
    except OSError:
        raise TemplateFileError("无法读取模板，请检查文件和访问权限。") from None


def save_new_template(presentation, output_directory: Path) -> tuple[str, str]:
    """另存独立文件并返回编号、文件名；不会覆盖原文件或已存在的文件。"""
    buffer = BytesIO()
    presentation.save(buffer)
    output_directory.mkdir(parents=True, exist_ok=True)
    output_id = f"template-{uuid4().hex}"
    path = output_directory / f"{output_id}.pptx"
    with path.open("xb") as target:
        try:
            target.write(buffer.getvalue())
            target.flush()
        except OSError:
            # 只清理本次独占创建的不完整文件，不触碰原模板和其他文件。
            target.close()
            path.unlink(missing_ok=True)
            raise
    return output_id, path.name
