"""视觉模块真实图片测试：读取.env，会联网并消耗模型额度。

在PyCharm中以pytest调试test_real_image_recognition。
文件只保留真实识别，不包含模型替身、离线测试或独立命令行主入口。
pytest调试：uv run --locked --no-sync python -m pytest tests/test_template_vision.py -s -q
测试会调用真实模型，不使用模拟回答。
"""

from pathlib import Path

import httpx
import pytest

from integrations.llm.langchain_model_factory import create_langchain_model
from integrations.templates.langchain_template_vision import LangChainTemplateVisionAnalyzer


async def run_real_image_test(image: Path | None = None) -> None:
    """真实集成验证：发送用户截图，供PyCharm断点和人工核对。

    由pytest测试函数调用；image可由测试代码显式传入，默认使用目录唯一图片。
    此函数负责配置、图片和HTTP生命周期；正式视觉模块不依赖这些路径。
    """
    from config.settings import PROJECT_ROOT, Settings

    settings = Settings()
    if image is None:
        directory = PROJECT_ROOT / "data" / "vision-demo"
        images = sorted(
            p for p in directory.glob("*")
            if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg"}
        )
        if len(images) != 1:
            raise ValueError("data/vision-demo需有唯一PNG/JPEG，或在测试代码中通过image参数指定图片。")
        image = images[0]
    if image.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        raise ValueError("测试图片必须为PNG/JPEG。")
    prompt = (PROJECT_ROOT / "prompts" / "template_visual_analysis.md").read_text(encoding="utf-8")
    # async with确保正常结束或异常时都会释放网络连接；工厂只借用此客户端。
    async with httpx.AsyncClient(timeout=120) as http_client:
        model = create_langchain_model(
            base_url=settings.llm_base_url, api_key=settings.llm_api_key,
            model_name=settings.llm_vision_model, timeout_seconds=120,
            max_tokens=4096, http_client=http_client,
        )
        analyzer = LangChainTemplateVisionAnalyzer(model=model, prompt=prompt)
        print("真实模型：", settings.llm_vision_model, "；图片：", image.name, flush=True)
        # 在此打断点查看真实结果；不会打印密钥或含base64的完整消息。
        result = await analyzer.analyze(
            image_bytes=image.read_bytes(),
            mime_type="image/png" if image.suffix.lower() == ".png" else "image/jpeg",
        )
    print("【真实视觉结果，请与图片人工对照】")
    print(result.model_dump_json(indent=2))


@pytest.mark.asyncio
async def test_real_image_recognition() -> None:
    """PyCharm/pytest可收集的真实图片测试，使用默认目录中的唯一截图。

    pytest通过test_前缀发现测试；asyncio标记让pytest-asyncio等待异步调用。
    在run_real_image_test中的analyze调用处打断点，即可查看实际模型结果。
    此测试成功表示调用与格式校验完成；识别准确性仍需人工对照截图。
    """
    await run_real_image_test()