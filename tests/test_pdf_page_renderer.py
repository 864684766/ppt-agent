"""真实PDF逐页图片测试，无网络、模型、模拟回答或独立脚本主入口。

uv run --locked --no-sync python -m pytest tests/test_pdf_page_renderer.py -s -q
在PyCharm中点击test_render_selected_pdf_pages左侧图标，选择Debug。
"""

import hashlib
from datetime import datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image

from config.settings import PROJECT_ROOT
from integrations.templates.pdfium_page_renderer import PdfiumPageRenderer


# 只需修改这三项就能改变真实测试，不必修改正式模块或增加环境变量。
# None表示选data/gotenberg-test中最近修改的PDF；也可填Path("E:/某份文件.pdf")。
PDF_PATH: Path | None = None
# 页码从1开始，保留填写顺序。例如[3, 1]先返回第3页，再返回第1页。
# 改成None表示全部页；如果样本不足3页，请改成[1]。
PAGE_NUMBERS: list[int] | None = [1, 3]
# 144 DPI表示每英寸144像素。模型输入并非越大越好，先检查图片清晰度。
RENDER_DPI = 144


def find_test_pdf() -> Path:
    """只在测试入口选择文件，不让正式渲染器扫描业务目录。"""
    if PDF_PATH is not None:
        return PDF_PATH
    candidates = list((PROJECT_ROOT / "data" / "gotenberg-test").rglob("*.pdf"))
    assert candidates, "请先运行Gotenberg转换测试生成PDF，或填写PDF_PATH。"
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, str(path)))


def test_render_selected_pdf_pages() -> None:
    """实际渲染所选页，重新打开PNG检查尺寸，输出完整元信息供断点查看。"""
    pdf_path = find_test_pdf()
    pdf_bytes = pdf_path.read_bytes()
    print("\n【输入PDF】", pdf_path, flush=True)
    print("【请求页码】", PAGE_NUMBERS, "【DPI】", RENDER_DPI, flush=True)
    renderer = PdfiumPageRenderer()
    # 在下一行打断点，Step Into可查看1基页码如何变为0基索引及图片编码过程。
    result = renderer.render(pdf_bytes=pdf_bytes, pages=PAGE_NUMBERS, dpi=RENDER_DPI)
    print("【PDF总页数】", result.total_pages, "【本次图片数】", len(result.images))
    print("【PDF指纹】", result.pdf_sha256)
    assert result.pdf_sha256 == hashlib.sha256(pdf_bytes).hexdigest()
    expected_pages = PAGE_NUMBERS if PAGE_NUMBERS is not None else list(range(1, result.total_pages + 1))
    assert [item.page_number for item in result.images] == expected_pages

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:8]
    output_directory = PROJECT_ROOT / "data" / "pdf-page-test" / run_id
    output_directory.mkdir(parents=True, exist_ok=True)
    for item in result.images:
        output_path = output_directory / f"page-{item.page_number:03d}.png"
        output_path.write_bytes(item.png_bytes)
        # 用图片解码器重新打开输出，验证不是仅给任意字节起了.png扩展名。
        with Image.open(BytesIO(item.png_bytes)) as image:
            image.load()
            assert image.format == "PNG"
            assert image.size == (item.width_px, item.height_px)
        print(f"【页面{item.page_number}】{item.width_px}×{item.height_px}px，{len(item.png_bytes)}字节")
        print("【图片位置】", output_path)
    assert hashlib.sha256(pdf_path.read_bytes()).hexdigest() == result.pdf_sha256
    print("请打开图片对照PDF对应页；PDF页码尚未自动关联PPT页码。")
