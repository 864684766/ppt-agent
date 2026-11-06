"""RapidOCR本地CPU适配；不依赖PDF、聊天接口、Settings或大语言模型。"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rapidocr import RapidOCR
    from rapidocr.utils.output import RapidOCROutput

from diagnostics.operation_logging import log_operation
from domain.ocr.image_text_recognizer_contract import OcrError
from integrations.ocr.ocr_image_decoder import decode_ocr_image
from models.ocr.ocr_result import OcrResult, OcrTextRegion

logger = logging.getLogger(__name__)

# 对应锁定RapidOCR 3.10.0的默认模型组合，不将引擎默认值当作永远不变。
# Det寻找文字位置，Cls判断文字方向，Rec将图像中的文字转换为字符串。
MODEL_FILES = {
    "Det": "PP-OCRv6_det_small.onnx",
    "Cls": "ch_ppocr_mobile_v2.0_cls_mobile.onnx",
    "Rec": "PP-OCRv6_rec_small.onnx",
}


class RapidOcrTextRecognizer:
    """可重复使用的识别器；首次recognize才加载模型，导入时不创建会话。

    model_directory由宿主注入，必须预先放好三份模型；运行时不自动下载。
    默认文件上限20MiB、2500万像素、2个CPU计算线程，均为本模块参数，
    不是已接线的环境变量。当前组合用于常见中文/英文印刷文字，不承诺手写、
    公式或表格结构还原。同一实例通过锁串行识别，避免SDK修改共享推理状态。
    模型在实例存活期间复用，实例释放时由SDK回收会话，没有虚构close方法。
    """

    def __init__(
        self, *, model_directory: Path, max_image_bytes: int = 20 * 1024 * 1024,
        max_image_pixels: int = 25_000_000, cpu_threads: int = 2,
    ) -> None:
        for value in (max_image_bytes, max_image_pixels, cpu_threads):
            if type(value) is not int or value <= 0:
                raise ValueError("OCR字节、像素上限和CPU线程数必须为正整数。")
        self._model_directory = Path(model_directory)
        self._max_image_bytes = max_image_bytes
        self._max_image_pixels = max_image_pixels
        self._cpu_threads = cpu_threads
        self._engine: RapidOCR | None = None
        self._lock = Lock()

    @log_operation("ocr.recognize_image")
    def recognize(self, *, image_bytes: bytes) -> OcrResult:
        """识别一张图片；无文字正常返回空regions，失败记录安全位置并抛OcrError。"""
        with decode_ocr_image(
            image_bytes=image_bytes, max_bytes=self._max_image_bytes,
            max_pixels=self._max_image_pixels,
        ) as image:
            try:
                with self._lock:
                    if self._engine is None:
                        self._engine = self._create_engine()
                    output = self._engine(image)
                    # 空白页是合法结果；但“仅检测成功、识别失败”不能伪装为空白。
                    from rapidocr.utils.output import RapidOCROutput
                    if not isinstance(output, RapidOCROutput):
                        raise OcrError("OCR未完成文字识别，请检查引擎与模型。")
                    regions = self._read_regions(output)
                logger.info(
                    "event=ocr_result width_px=%d height_px=%d region_count=%d character_count=%d",
                    image.width, image.height, len(regions), sum(len(r.text) for r in regions),
                )
                if not regions:
                    logger.warning("event=ocr_no_text 未检出文字；不代表图片一定没有文字。")
                return OcrResult(width_px=image.width, height_px=image.height, regions=regions)
            except OcrError:
                raise
            except Exception:
                raise OcrError("本地OCR识别失败，请检查模型文件和运行环境。") from None

    @log_operation("ocr.load_engine")
    def _create_engine(self) -> RapidOCR:
        """显式使用本地模型，缺失即失败；不在用户识别请求中偷偷联网下载。"""
        model_paths = {task: self._model_directory / name for task, name in MODEL_FILES.items()}
        if not all(path.is_file() for path in model_paths.values()):
            raise OcrError("OCR模型文件缺失，请先按OCR调试说明准备本地模型。")
        from rapidocr import RapidOCR
        params = {
            "Global.log_level": "critical",
            "Global.text_score": 0.5,
            "EngineConfig.onnxruntime.use_cuda": False,
            "EngineConfig.onnxruntime.use_dml": False,
            "EngineConfig.onnxruntime.intra_op_num_threads": self._cpu_threads,
            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
        }
        for task, path in model_paths.items():
            params[f"{task}.model_path"] = str(path.resolve())
        # SDK会延迟创建ONNX会话，首次recognize的总耗时还包括实际加载。
        # SDK独立logger不归本项目接管，压制它的原文日志；本项目记录安全摘要。
        return RapidOCR(params=params)

    @staticmethod
    def _read_regions(output: RapidOCROutput) -> tuple[OcrTextRegion, ...]:
        """将SDK的NumPy数组转为标准库元组，调用方无需再依赖NumPy格式。"""
        if output.txts is None:
            if output.boxes is not None or output.scores is not None:
                raise OcrError("OCR返回了不完整的文字识别结果。")
            return ()
        if output.boxes is None or output.scores is None:
            raise OcrError("OCR文字结果缺少位置或置信分。")
        regions = []
        # strict=True要求三组数量相同，不能用普通zip静默丢弃多出的条目。
        for text, box, score in zip(output.txts, output.boxes, output.scores, strict=True):
            points = tuple((float(point[0]), float(point[1])) for point in box)
            confidence = float(score)
            if (len(points) != 4 or not math.isfinite(confidence) or not 0 <= confidence <= 1
                    or any(not math.isfinite(v) for point in points for v in point)):
                raise OcrError("OCR返回的位置或置信分不合法。")
            if text.strip():
                regions.append(OcrTextRegion(text=text, polygon_px=points, confidence=confidence))
        return tuple(regions)
