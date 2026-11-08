"""教学交互 LLM"""
from __future__ import annotations

from openai import AsyncOpenAI

from learning_assistant.llm.base import BaseLLM


TUTOR_SYSTEM_PROMPT = """\
你是一位耐心且善于引导的学习助手。

教学原则：
1. 不直接给出答案，而是通过提问引导学生思考
2. 根据学生水平调整解释深度
3. 使用具体例子说明抽象概念
4. 及时给予正面反馈和鼓励
5. 回答简洁，每次不超过 300 字

当前学习上下文：
{context}

上次学习进度：
{resume_info}

当前主题：{topic}"""


class TutorLLM(BaseLLM):
    """苏格拉底式教学 AI"""

    def __init__(self, client: AsyncOpenAI, model: str = "gpt-4o-mini"):
        super().__init__(client, model, system_prompt="")

    async def respond(
        self,
        message: str,
        context: str = "",
        resume_info: str = "",
        topic: str = "",
    ) -> str:
        """回复学生问题"""
        system = TUTOR_SYSTEM_PROMPT.format(
            context=context or "暂无额外上下文",
            resume_info=resume_info or "首次学习",
            topic=topic,
        )
        return await self._chat(message, system=system)
