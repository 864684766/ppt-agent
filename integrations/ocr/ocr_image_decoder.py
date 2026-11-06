"""只处理OCR图片输入的解码与限额，不负责模型加载、识别或来源管理。"""

from io import BytesIO
import warnings

from PIL import Image, ImageOps

from domain.ocr.image_text_recognizer_contract import OcrError


def decode_ocr_image(*, image_bytes: bytes, max_bytes: int, max_pixels: int) -> Image.Image:
    """返回独立的RGB图片，由调用方用with关闭；失败不泄漏Pillow异常原文。

    限额防止压缩文件很小、解码却占用大量内存。先看尺寸再解码像素，
    不通过修改Pillow的全局MAX_IMAGE_PIXELS去影响其他图片模块。
    EXIF是照片里可携带的方向信息；校正后再OCR，尺寸与文字坐标才一致。
    """
    if not isinstance(image_bytes, bytes) or not image_bytes:
        raise OcrError("请传入非空图片文件字节。")
    if len(image_bytes) > max_bytes:
        raise OcrError("图片文件超过OCR字节上限。")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(image_bytes)) as image:
                if image.format not in {"PNG", "JPEG", "WEBP", "BMP", "TIFF"}:
                    raise OcrError("OCR仅支持PNG、JPEG、WEBP、BMP和单页TIFF图片。")
                if getattr(image, "n_frames", 1) != 1:
                    raise OcrError("请先将多帧或多页图片拆为单张图片，再调用OCR。")
                if image.width * image.height > max_pixels:
                    raise OcrError("图片超过OCR像素上限，请先缩小或分块。")
                with ImageOps.exif_transpose(image) as oriented:
                    # 透明部分合成白色，避免直接丢弃alpha后透明底变黑、影响识别。
                    with oriented.convert("RGBA") as rgba:
                        with Image.new("RGBA", rgba.size, "white") as background:
                            with Image.alpha_composite(background, rgba) as combined:
                                return combined.convert("RGB")
    except OcrError:
        raise
    except Exception:
        raise OcrError("无法解码图片，请检查格式、内容及像素大小。") from None
