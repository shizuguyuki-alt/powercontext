"""学习计划 LLM 生成器"""
from __future__ import annotations

from openai import AsyncOpenAI

from learning_assistant.llm.base import BaseLLM


PLAN_SYSTEM_PROMPT = """\
你是一个专业的学习计划规划师。根据用户的学习目标和背景，生成结构化的学习计划。

你必须输出合法的 JSON，格式如下：
{
  "course_name": "课程名称",
  "milestones": [
    {
      "week": 1,
      "topic": "本周主题",
      "objectives": ["目标1", "目标2"],
      "estimated_hours": 5.0,
      "completed": false
    }
  ]
}

要求：
1. 循序渐进，由浅入深
2. 每周安排合理的学习量（建议 3-8 小时）
3. 包含实践项目或练习
4. 最后一个里程碑应包含综合复习"""


class PlanLLM(BaseLLM):
    """使用 LLM 生成学习计划"""

    def __init__(self, client: AsyncOpenAI, model: str = "gpt-4o-mini"):
        super().__init__(client, model, system_prompt=PLAN_SYSTEM_PROMPT)

    async def generate_plan(
        self,
        course_name: str,
        goal: str,
        total_weeks: int,
        background: str = "",
    ) -> dict:
        """生成学习计划，返回 JSON dict"""
        user_prompt = (
            f"请为以下学习需求生成计划：\n"
            f"- 课程：{course_name}\n"
            f"- 目标：{goal}\n"
            f"- 周期：{total_weeks}周\n"
            f"- 学生背景：{background or '初学者'}"
        )
        return await self._chat_json(user_prompt)
