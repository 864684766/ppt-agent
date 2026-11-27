"""用真实 SDK 和模拟 HTTP 传输重现一次格式错误后读取超时。"""

import logging

import httpx
import pytest
from langchain_openai.chat_models.base import OpenAITimeoutError
from pydantic import SecretStr

from agents.web.research_review_agent import ResearchReviewAgent
from integrations.llm.langchain_model_factory import create_langchain_model
from integrations.llm.model_http_logging import log_model_headers, log_model_request


@pytest.mark.asyncio
async def test_review_retry_trace(caplog) -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise httpx.ReadTimeout("private-timeout-details", request=request)
        return httpx.Response(200, json={"id": "test", "created": 1, "model": "test",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": '{"feedback":"private-model-output"}'}}]})

    hooks = {"request": [log_model_request], "response": [log_model_headers]}
    with caplog.at_level(logging.INFO):
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond), event_hooks=hooks) as client:
            model = create_langchain_model(base_url="https://example.org", api_key=SecretStr("private-test-key"),
                model_name="test", timeout_seconds=240, max_tokens=256, http_client=client)
            agent = ResearchReviewAgent(model=model, prompt="private-prompt")
            with pytest.raises(OpenAITimeoutError):
                await agent.review(question="private-question", candidates=[{
                    "candidate_id": "web_1", "title": "test", "url": "https://example.org",
                    "snippet": "private-snippet", "engines": [], "search_strategies": []}])
    assert calls == 2
    assert caplog.text.count("event=model_http_headers status_code=200") == 1
    assert caplog.text.count("event=model_http_start read_timeout_seconds=240") == 2
    assert "format_attempt=2 connection_attempt=1" in caplog.text
    assert "field=relevant_ids kind=missing" in caplog.text
    assert "ReadTimeout[" in caplog.text
    assert "private-" not in caplog.text
