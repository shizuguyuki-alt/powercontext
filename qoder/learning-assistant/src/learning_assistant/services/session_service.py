"""学习会话管理服务

基于 PowerContext Atomic Memory 实现跨会话连续性。
每次会话结束时保存状态，下次开始时恢复。
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from learning_assistant.services.models import SessionContext

if TYPE_CHECKING:
    from learning_assistant.context.client import LearningAssistantClient
    from learning_assistant.llm.tutor import TutorLLM


class SessionService:
    """学习会话服务

    职责：
    - 创建/恢复学习会话
    - 管理交互式教学对话
    - 记录练习经验 (Experience)
    - 保存会话状态用于跨会话恢复
    """

    def __init__(self, client: LearningAssistantClient, tutor: TutorLLM):
        self._client = client
        self._tutor = tutor
        self._current_session: SessionContext | None = None

    async def start_session(
        self,
        course_scope_id: str,
        topic: str,
        resume: bool = True,
    ) -> SessionContext:
        """开始新的学习会话"""
        session_scope_id = await self._client.create_session_scope(
            session_topic=topic,
            parent_scope_id=course_scope_id,
        )

        resumed_state = None
        if resume:
            resumed_state = await self._client.load_session_state(course_scope_id)

        self._current_session = SessionContext(
            session_id=session_scope_id,
            course_scope_id=course_scope_id,
            session_scope_id=session_scope_id,
            topic=topic,
            resumed_from=resumed_state,
        )

        return self._current_session

    async def end_session(
        self,
        progress_summary: list[str],
        next_action: str | None = None,
    ):
        """结束当前会话，保存状态"""
        if not self._current_session:
            raise RuntimeError("没有活跃的会话，请先调用 start_session()")

        session = self._current_session

        state = {
            "topic": session.topic,
            "progress": progress_summary,
            "next_action": next_action or "继续当前主题",
            "session_id": session.session_id,
        }

        await self._client.save_session_state(
            scope_id=session.course_scope_id,
            state=state,
        )

        try:
            await self._client.flush_memories(session.session_scope_id)
        except Exception:
            pass  # flush requires inference config; skip if unavailable

        self._current_session = None

    async def chat(self, message: str) -> str:
        """与教学 AI 对话"""
        if not self._current_session:
            raise RuntimeError("没有活跃的会话，请先调用 start_session()")

        session = self._current_session

        context = await self._client.get_context(
            scope_id=session.course_scope_id,
            query=message,
            max_bytes=4000,
        )

        resume_info = ""
        if session.resumed_from:
            progress = session.resumed_from.get("progress", [])
            next_act = session.resumed_from.get("next_action", "")
            if progress:
                resume_info = f"上次进度: {'; '.join(progress)}"
            if next_act:
                resume_info += f"\n下一步: {next_act}"

        response = await self._tutor.respond(
            message=message,
            context=context.content if context else "",
            resume_info=resume_info,
            topic=session.topic,
        )

        await self._client.save_learning_material(
            scope_id=session.session_scope_id,
            material_type="dialogue",
            content={"user": message, "assistant": response},
        )

        return response

    async def record_exercise(
        self,
        situation: str,
        action: str,
        outcome: str,
        lesson: str,
    ):
        """记录练习经验"""
        if not self._current_session:
            raise RuntimeError("没有活跃的会话")

        await self._client.record_practice_experience(
            scope_id=self._current_session.session_scope_id,
            situation=situation,
            action=action,
            outcome=outcome,
            lesson=lesson,
        )

    @property
    def current_session(self) -> SessionContext | None:
        return self._current_session
