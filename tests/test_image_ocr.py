"""读取一张真实图片，调用本地OCR并打印文字，供PyCharm断点调试。"""

from pathlib import Path

from config.settings import PROJECT_ROOT
from integrations.ocr.rapidocr_text_recognizer import RapidOcrTextRecognizer


# 改成你的图片路径即可，例如Path("E:/我的资料/截图.png")。
IMAGE_PATH: Path = PROJECT_ROOT / "data" / "vision-demo" / "template-thumbnail.png"
MODEL_DIRECTORY = PROJECT_ROOT / "ocr-models"


def test_recognize_real_image() -> None:
    """只做一次真实识别；在recognize这一行打断点查看result。"""
    recognizer = RapidOcrTextRecognizer(model_directory=MODEL_DIRECTORY)
    result = recognizer.recognize(image_bytes=IMAGE_PATH.read_bytes())
    print("\n【图片】", IMAGE_PATH, flush=True)
    print("【识别文字】\n" + result.text, flush=True)
