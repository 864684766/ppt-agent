"""将宿主提供的媒体字节嵌入PPTX，不下载网络资源。"""

from io import BytesIO

from pptx.util import Inches

from domain.presentations.presentation_builder_contract import PresentationBuildError
from models.presentations.presentation_page_element import AudioElement, VideoElement


def draw_presentation_media(slide, plan: VideoElement | AudioElement, *, videos: dict[str, bytes],
                            audios: dict[str, bytes], images: dict[str, bytes]) -> None:
    """使用python-pptx实验性媒体接口；只验证文件基本标识，不验证编解码或实际播放。"""
    is_video = isinstance(plan, VideoElement)
    content = videos.get(plan.video_id) if is_video else audios.get(plan.audio_id)
    if content is None:
        raise PresentationBuildError("视频或音频编号未登记。")
    if not content or len(content) > 50 * 1024 * 1024:
        raise PresentationBuildError("媒体为空或超过50 MiB。")
    # 简单识别格式，不等价于验证完整文件及编解码器是否受Office支持。
    if is_video and (len(content) < 12 or content[4:8] != b"ftyp"):
        raise PresentationBuildError("视频不是可识别的MP4容器。")
    if not is_video and not (content.startswith(b"ID3") or len(content) >= 2 and content[0] == 0xff and content[1] & 0xe0 == 0xe0):
        raise PresentationBuildError("音频不是可识别的MP3。")
    poster = None
    if is_video and plan.poster_image_id is not None:
        poster = images.get(plan.poster_image_id)
        if poster is None or not poster or len(poster) > 10 * 1024 * 1024:
            raise PresentationBuildError("视频封面图片未登记、为空或超过10 MiB。")
    # add_movie为实验性API：MP3通过同一个媒体接口嵌入，音频对象的实际播放尚未验证。
    slide.shapes.add_movie(BytesIO(content), Inches(plan.x), Inches(plan.y), Inches(plan.width), Inches(plan.height),
                           poster_frame_image=BytesIO(poster) if poster else None,
                           mime_type="video/mp4" if is_video else "audio/mpeg")
