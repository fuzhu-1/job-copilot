import json
import re
from typing import Any, Type

from openai import OpenAI
from pydantic import BaseModel

from app.config import settings


class LLMService:
    """LLM 调用封装：普通补全 + 结构化 JSON 输出，带一次重试。"""

    def __init__(self, client: OpenAI | None = None, model: str | None = None):
        self.client = client or OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key or "EMPTY",
        )
        self.model = model or settings.llm_model

    def complete(self, messages: list[dict[str, str]], max_tokens: int = 2000) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    def complete_structured(
        self,
        messages: list[dict[str, str]],
        schema: Type[BaseModel],
        max_tokens: int = 2000,
    ) -> dict[str, Any]:
        """要求模型输出符合 schema 的 JSON；解析失败时带错误信息重试一次。"""
        instruction = (
            "You must respond with a single JSON object matching this schema exactly:\n"
            f"{schema.model_json_schema()}\n"
            "No markdown fences. No commentary."
        )
        attempt_messages = messages + [{"role": "system", "content": instruction}]
        for attempt in range(2):
            text = self.complete(attempt_messages, max_tokens=max_tokens)
            try:
                data = self._extract_json(text)
                return schema.model_validate(data).model_dump()
            except Exception as exc:
                if attempt == 0:
                    attempt_messages = attempt_messages + [
                        {"role": "assistant", "content": text},
                        {
                            "role": "user",
                            "content": f"Previous output was invalid: {exc}. Return valid JSON.",
                        },
                    ]
                    continue
                raise ValueError(f"LLM structured output failed: {exc}") from exc
        raise ValueError("LLM structured output failed")

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return json.loads(cleaned)
