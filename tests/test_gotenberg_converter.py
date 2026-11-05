"""真实Gotenberg转换测试：上传ppt-demo中的PPTX，不调用模型。

uv run --locked --no-sync python -m pytest tests/test_gotenberg_converter.py -s -q
在PyCharm中点击测试函数左侧图标选择Debug，无独立命令行主入口。
"""

import hashlib
from datetime import datetime
from uuid import uuid4

import httpx
import pytest

from config.settings import PROJECT_ROOT, Settings
from integrations.templates.gotenberg_converter import GotenbergPdfConverter


@pytest.mark.asyncio
async def test_convert_real_pptx_to_pdf() -> None:
    """读取真实配置，逐份转换样本，打印结果文件路径供人工打开核对。

    默认测试ppt-demo的全部一级PPTX，不递归扫描；忽略WPS/Office的~$锁文件。
    只想测试某份文件时，可将templates改为包含指定Path的列表。
    每次使用独立输出目录，不覆盖上次结果；测试不负责删除历史文件。
    """
    settings = Settings()
    templates = sorted(
        path for path in (PROJECT_ROOT / "ppt-demo").glob("*.pptx")
        if not path.name.startswith("~$") and path.is_file()
    )
    assert templates, "请先在ppt-demo目录放入需要测试的PPTX。"
    # 时间便于人工辨认；随机后缀避免同一秒重复调试时目录重名。
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:8]
    output_directory = PROJECT_ROOT / "data" / "gotenberg-test" / run_id
    async with httpx.AsyncClient() as http_client:
        converter = GotenbergPdfConverter(
            client=http_client, base_url=settings.gotenberg_base_url,
            timeout_seconds=settings.gotenberg_timeout_seconds,
        )
        for template in templates:
            pptx_bytes = template.read_bytes()
            original_hash = hashlib.sha256(pptx_bytes).hexdigest()
            print("\n【输入PPTX】", template.name, "字节数：", len(pptx_bytes), flush=True)
            print("【转换服务】", settings.gotenberg_base_url, flush=True)
            # 在下一行打断点：单步进入转换器观察请求、HTTP响应和PDF检查。
            pdf_bytes = await converter.convert(pptx_bytes=pptx_bytes, file_name=template.name)
            output_directory.mkdir(parents=True, exist_ok=True)
            output_path = output_directory / (template.stem + ".pdf")
            output_path.write_bytes(pdf_bytes)
            print("【PDF字节数】", len(pdf_bytes))
            print("【PDF保存位置】", output_path)
            print("请打开PDF对照原PPT检查页数、中文字体和布局；测试通过不等于视觉一致。")
            assert output_path.read_bytes() == pdf_bytes
            assert hashlib.sha256(template.read_bytes()).hexdigest() == original_hash
