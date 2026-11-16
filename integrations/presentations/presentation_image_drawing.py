"""从宿主登记的图片字节绘制图片，不读取模型指定路径。"""

from io import BytesIO

from PIL import Image
from pptx.util import Inches

from domain.presentations.presentation_builder_contract import PresentationBuildError
from models.presentations.presentation_page_element import ImageElement


def draw_presentation_image(slide, plan: ImageElement, images: dict[str, bytes]) -> None:
    content = images.get(plan.image_id)
    if content is None:
        raise PresentationBuildError("图片编号未登记，请选择宿主提供的图片。")
    if not content or len(content) > 10 * 1024 * 1024:
        raise PresentationBuildError("图片为空或超过10 MiB。")
    try:
        with Image.open(BytesIO(content)) as image:
            if image.format not in {"PNG", "JPEG"} or image.width * image.height > 25_000_000:
                raise PresentationBuildError("仅支持不超过2500万像素的PNG或JPEG。")
            image.verify()
    except PresentationBuildError:
        raise
    except Exception:
        raise PresentationBuildError("图片无法读取，请检查PNG或JPEG内容。") from None
    # 同时指定宽高意味着拉伸填充，非自动裁剪；方案制定者需要保持原始宽高比。
    slide.shapes.add_picture(BytesIO(content), Inches(plan.x), Inches(plan.y), Inches(plan.width), Inches(plan.height))
