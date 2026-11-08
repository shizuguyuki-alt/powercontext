"""学习计划生成与管理服务"""
from __future__ import annotations

from typing import TYPE_CHECKING

from learning_assistant.services.models import LearningPlan, Milestone

if TYPE_CHECKING:
    from learning_assistant.context.client import LearningAssistantClient
    from learning_assistant.llm.planner import PlanLLM


class PlanService:
    """学习计划服务

    职责：
    - 调用 LLM 生成学习计划
    - 将计划存入 PowerContext Memory
    - 管理里程碑状态更新
    """

    def __init__(self, client: LearningAssistantClient, planner: PlanLLM):
        self._client = client
        self._planner = planner

    async def create_plan(
        self,
        course_name: str,
        goal: str,
        total_weeks: int,
        student_background: str = "",
    ) -> LearningPlan:
        """生成学习计划并持久化到 PowerContext"""
        plan_data = await self._planner.generate_plan(
            course_name=course_name,
            goal=goal,
            total_weeks=total_weeks,
            background=student_background,
        )

        course_scope_id = await self._client.create_course_scope(
            course_name=course_name,
            goal=goal,
        )

        plan_text = self._format_plan_for_memory(plan_data)
        await self._client.remember(
            scope_id=course_scope_id,
            kind="plan",
            text=plan_text,
            reason=f"初始学习计划: {course_name}",
        )

        await self._client.remember(
            scope_id=course_scope_id,
            kind="learning_goal",
            text=f"目标: {goal}，周期: {total_weeks}周",
            reason="课程学习目标",
        )

        milestones = []
        for m in plan_data.get("milestones", []):
            milestones.append(Milestone(
                week=m.get("week", 0),
                topic=m.get("topic", ""),
                objectives=m.get("objectives", []),
                estimated_hours=m.get("estimated_hours", 5.0),
                completed=m.get("completed", False),
            ))

        return LearningPlan(
            course_name=course_name,
            goal=goal,
            total_weeks=total_weeks,
            milestones=milestones,
        )

    async def get_plan(self, course_scope_id: str) -> dict:
        """从 Memory 中获取当前学习计划"""
        result = await self._client.search_knowledge(
            scope_id=course_scope_id,
            query="学习计划 plan",
            mode="fts",
            limit=1,
        )
        if result.hits:
            return {"raw": result.hits[0].memory.text}
        return {"raw": "暂无学习计划"}

    async def update_milestone(
        self,
        course_scope_id: str,
        milestone_week: int,
        completed: bool = True,
        notes: str = "",
    ):
        """更新里程碑状态"""
        status = "已完成" if completed else "未完成"
        await self._client.remember(
            scope_id=course_scope_id,
            kind="milestone_status",
            text=f"第{milestone_week}周里程碑: {status}. {notes}",
            reason="进度更新",
        )

    def _format_plan_for_memory(self, plan_data: dict) -> str:
        lines = [f"课程: {plan_data.get('course_name', '')}"]
        for m in plan_data.get("milestones", []):
            lines.append(f"第{m.get('week', '?')}周: {m.get('topic', '')}")
            for obj in m.get("objectives", []):
                lines.append(f"  - {obj}")
            lines.append(f"  预计学时: {m.get('estimated_hours', '?')}h")
        return "\n".join(lines)
