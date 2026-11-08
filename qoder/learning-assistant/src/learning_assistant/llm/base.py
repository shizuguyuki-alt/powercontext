"""LLM 基类"""
from __future__ import annotations

from openai import AsyncOpenAI


class BaseLLM:
    """LLM 基类，封装 OpenAI 客户端"""

    def __init__(
        self,
        client: AsyncOpenAI,
        model: str = "gpt-4o-mini",
        system_prompt: str = "",
    ):
        self._client = client
        self._model = model
        self._system_prompt = system_prompt

    async def _chat(self, user_message: str, *, system: str | None = None) -> str:
        messages = []
        if system or self._system_prompt:
            messages.append({"role": "system", "content": system or self._system_prompt})
        messages.append({"role": "user", "content": user_message})

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
        )
        return response.choices[0].message.content or ""

    async def _chat_json(self, user_message: str, *, system: str | None = None) -> dict:
        import json
        content = await self._chat(user_message, system=system)
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            content = "\n".join(lines)
        return json.loads(content)
