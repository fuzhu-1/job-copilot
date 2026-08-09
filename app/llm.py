import json
import logging
import re
import time
from typing import Any, Type

from openai import OpenAI
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """LLM 调用封装：普通补全 + 结构化 JSON 输出，带退避重试与可选 json 模式。"""

    def __init__(
        self,
        client: OpenAI | None = None,
        model: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        json_mode: bool | None = None,
    ):
        self.timeout = timeout if timeout is not None else settings.llm_timeout
        self.max_retries = max_retries if max_retries is not None else settings.llm_max_retries
        self.json_mode = settings.llm_json_mode if json_mode is None else json_mode
        self.client = client or OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key or "EMPTY",
            timeout=self.timeout,
        )
        self.model = model or settings.llm_model

    def _log_usage(self, response) -> None:
        usage = getattr(response, "usage", None)
        logger.info(
            "llm_complete model=%s prompt_tokens=%s completion_tokens=%s",
            self.model,
            getattr(usage, "prompt_tokens", None),
            getattr(usage, "completion_tokens", None),
        )

    def complete(self, messages: list[dict[str, str]], max_tokens: int = 4000, **kwargs) -> str:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                self._log_usage(response)
                return response.choices[0].message.content or ""
            except Exception as exc:
                last_exc = exc
                status = getattr(exc, "status_code", None)
                retryable = status is None or status >= 500 or status == 429
                if attempt < self.max_retries and retryable:
                    time.sleep(0.5 * (2**attempt))
                    continue
                raise
        raise last_exc  # type: ignore[misc]

    def complete_structured(
        self,
        messages: list[dict[str, str]],
        schema: Type[BaseModel],
        max_tokens: int = 4000,
    ) -> dict[str, Any]:
        """要求模型输出符合 schema 的 JSON；解析失败带错误重试一次。"""
        instruction = (
            "You must respond with a single JSON object matching this schema exactly:\n"
            f"{schema.model_json_schema()}\n"
            "No markdown fences. No commentary."
        )
        last_exc: Exception | None = None
        for _ in range(3):
            try:
                kwargs = {"response_format": {"type": "json_object"}} if self.json_mode else {}
                text = self.complete(
                    messages + [{"role": "system", "content": instruction}],
                    max_tokens=max_tokens,
                    **kwargs,
                )
            except Exception:
                if self.json_mode:
                    self.json_mode = False
                    continue
                raise
            try:
                data = self._extract_json(text)
                return schema.model_validate(data).model_dump()
            except Exception as exc:
                last_exc = exc
                messages = messages + [
                    {"role": "assistant", "content": text},
                    {
                        "role": "user",
                        "content": f"Previous output was invalid: {exc}. Return valid JSON.",
                    },
                ]
        raise ValueError(f"LLM structured output failed: {last_exc}") from last_exc

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return json.loads(cleaned)
