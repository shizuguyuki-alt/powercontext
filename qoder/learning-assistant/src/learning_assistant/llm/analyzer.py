"""学习分析 LLM"""
from __future__ import annotations

from openai import AsyncOpenAI

from learning_assistant.llm.base import BaseLLM


class AnalyzerLLM(BaseLLM):
    """分析学习数据，生成进度报告和建议"""

    def __init__(self, client: AsyncOpenAI, model: str = "gpt-4o-mini"):
        super().__init__(client, model)

    async def analyze_progress(
        self,
        plan: object,
        weaknesses: object,
        masteries: object,
    ) -> dict:
        """分析学习进度，返回 JSON dict"""
        prompt = (
            f"分析以下学习数据并生成进度报告。\n\n"
            f"学习计划：{plan}\n"
            f"薄弱点：{weaknesses}\n"
            f"已掌握：{masteries}\n\n"
            f"输出 JSON：\n"
            f'{{"total": 总里程碑数, "completed": 已完成数, '
            f'"weak_areas": ["薄弱点1", ...], '
            f'"strong_areas": ["强项1", ...], '
            f'"recent": [], '
            f'"suggestions": ["建议1", ...]}}'
        )
        return await self._chat_json(
            prompt,
            system="你是学习数据分析师。只输出 JSON，不要其他文字。",
        )

    async def suggest_next_steps(self, context: str) -> list[str]:
        """建议下一步学习行动"""
        content = await self._chat(
            f"学习上下文：\n{context}\n\n请给出 3-5 条具体的下一步学习建议，每条一行，以 - 开头。",
            system="你是学习顾问，根据上下文给出具体可行的建议。",
        )
        return [
            line.strip("- ").strip()
            for line in content.split("\n")
            if line.strip().startswith("-") or line.strip().startswith("•")
        ]
