"""真实图片输入验证，不属于离线单元测试，不自动接入正式Agent。

uv run --locked --no-sync python -m examples.vision_model_demo
可传--image本地PNG/JPEG，默认读取data/vision-demo下唯一的图片。
"""

import argparse
import asyncio
import base64
import json
import time
from pathlib import Path

import httpx
from langchain.messages import HumanMessage
from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APIStatusError, APITimeoutError

from config.settings import PROJECT_ROOT, Settings


def prepare_image(image: Path | None) -> tuple[Path, str]:
    """定位用户提供的图片及MIME类型，不提取、生成或覆盖输入图片。

    未传image时只检查固定目录的一级PNG/JPEG，不把JSON结果当图片。
    多图时明确报错，请用户用--image选择，避免误测其他图片。
    """
    if image is None:
        directory = PROJECT_ROOT / "data" / "vision-demo"
        images = sorted(
            path for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}
        ) if directory.is_dir() else []
        if not images:
            raise ValueError("data/vision-demo没有图片，请放入一张PNG/JPEG或使用--image指定。")
        if len(images) != 1:
            raise ValueError("data/vision-demo有多张图片，请只保留一张，或用--image明确指定。")
        image = images[0]
    image = image.resolve()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(image.suffix.lower())
    if mime is None or not image.is_file():
        raise ValueError("请提供存在的PNG或JPEG图片文件。")
    return image, mime


async def run_demo(*, image: Path | None, max_tokens: int, timeout: float) -> None:
    """沿用项目连接配置发送一张图片；结果保存原始可见回答供人工核对。

    不打印Settings、密钥或图片base64；禁用自动重试，避免失败后重复计费。
    response.usage_metadata仅打印计量字段，不打印SDK内部请求及响应对象。
    """
    settings = Settings()
    if not settings.llm_base_url or not settings.llm_api_key.get_secret_value():
        raise ValueError("请先在.env填写LLM_BASE_URL和LLM_API_KEY。")
    image_path, mime = prepare_image(image)
    prompt = (PROJECT_ROOT / "prompts" / "vision_template_analysis.md").read_text(encoding="utf-8")
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    print("模型：", settings.llm_vision_model)
    print("图片：", image_path)
    print("将进行一次真实图片请求，未发送PPT结构或预期答案。", flush=True)
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout) as http_client:
        model = ChatOpenAI(
            base_url=settings.llm_base_url, api_key=settings.llm_api_key,
            model=settings.llm_vision_model, timeout=timeout, max_tokens=max_tokens,
            max_retries=0, http_async_client=http_client, use_responses_api=False,
            # 保留httpx的系统代理行为，不由SDK另建带自定义socket选项的transport。
            http_socket_options=(),
        )
        # OpenAI兼容的多模态格式：同一条消息里同时放text和image_url块。
        # data URL内嵌图片字节，无需让代理访问用户本机路径。
        message = HumanMessage(content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
        ])
        # PyCharm在此打断点，单步观察消息构造；不要将包含图片的message输出到日志。
        response = await model.ainvoke([message])
    elapsed = round(time.perf_counter() - started, 2)
    text = response.text.strip()
    if not text:
        raise ValueError("模型未返回可见回答，请检查输出额度或代理的图片支持。")
    print("\n【模型视觉回答】\n", text)
    print("\n耗时（秒）：", elapsed)
    print("Token用量：", json.dumps(response.usage_metadata, ensure_ascii=False))
    output = PROJECT_ROOT / "data" / "vision-demo"
    output.mkdir(parents=True, exist_ok=True)
    # 仅保存可见回答及计量，不保存密钥、连接地址、base64或隐藏推理。
    result_path = output / "vision-result.json"
    result_path.write_text(json.dumps({
        "model": settings.llm_vision_model, "image_name": image_path.name,
        "elapsed_seconds": elapsed, "usage": response.usage_metadata, "answer": text,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("结果文件：", result_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="独立视觉模型真实图片验证")
    parser.add_argument("--image", type=Path, help="可选，本地PNG/JPEG；省略读取data/vision-demo中唯一图片。")
    parser.add_argument("--max-tokens", type=int, default=4096, help="输出token预算，默认4096，含推理预算的解释由供应商决定。")
    parser.add_argument("--timeout", type=float, default=120, help="HTTP等待超时秒数，默认120。")
    args = parser.parse_args()
    if args.max_tokens <= 0 or args.timeout <= 0:
        parser.error("max-tokens和timeout必须大于0。")
    try:
        asyncio.run(run_demo(image=args.image, max_tokens=args.max_tokens, timeout=args.timeout))
    except APITimeoutError:
        raise SystemExit("视觉请求超时，未自动重试。") from None
    except APIConnectionError:
        raise SystemExit("无法连接模型代理，请检查网络和LLM_BASE_URL。") from None
    except APIStatusError as error:
        raise SystemExit(f"代理返回HTTP {error.status_code}，未自动重试；检查模型图片支持、权限和请求格式。") from None
    except (ValueError, OSError) as error:
        raise SystemExit(str(error)) from None
