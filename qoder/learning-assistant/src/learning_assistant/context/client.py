"""PowerContext 客户端封装

为学习助手提供高层 API，封装 PowerContext 底层操作。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from powercontext.client import PowerContextClient
from powercontext.http import (
    CreateArtifactRequest,
    CreateScopeRequest,
    CreateSourceRequest,
    FlushMemoryRequest,
    ListArtifactsRequest,
    PrepareContextRequest,
    RememberMemoryRequest,
    SearchMemoryRequest,
)


@dataclass
class ScopeIds:
    """学习相关的 Scope ID 集合"""
    student: str = ""
    course: str | None = None
    session: str | None = None


class LearningAssistantClient:
    """学习助手专用客户端

    封装 PowerContext SDK，提供面向学习场景的高层 API::

        async with LearningAssistantClient(base_url) as client:
            scope_id = await client.create_student_scope("张三", {"level": "beginner"})
            await client.remember(scope_id, "fact", "偏好视频学习")
    """

    def __init__(self, base_url: str, *, token: str | None = None):
        self._base_url = base_url
        self._token = token
        self._client: PowerContextClient | None = None
        self.scopes = ScopeIds()

    async def __aenter__(self) -> PowerContextClient:
        self._client = PowerContextClient(
            self._base_url,
            token=self._token,
            timeout=30.0,
            allow_insecure_http=True,
        )
        self._client = await self._client.__aenter__()
        return self._client

    async def __aexit__(self, *args):
        if self._client:
            await self._client.__aexit__(*args)
            self._client = None

    @property
    def client(self) -> PowerContextClient:
        assert self._client is not None, "请先调用 await client.__aenter__() 或使用 async with"
        return self._client

    # ── Scope 管理 ──────────────────────────────────────────

    async def create_student_scope(self, student_name: str, profile: dict) -> str:
        """创建学生根 Scope"""
        scope = await self.client.create_scope(CreateScopeRequest(
            title=f"学生: {student_name}",
            summary=f"学生画像 - {profile.get('level', '未知')}水平",
            idempotency_key=f"student:{student_name}",
        ))
        self.scopes.student = scope.scope_id
        return scope.scope_id

    async def create_course_scope(
        self,
        course_name: str,
        goal: str,
        *,
        parent_scope_id: str | None = None,
    ) -> str:
        """创建课程 Scope"""
        scope = await self.client.create_scope(CreateScopeRequest(
            title=f"课程: {course_name}",
            summary=f"学习目标: {goal}",
            idempotency_key=f"course:{course_name}:{parent_scope_id or self.scopes.student}",
            parent_scope_id=parent_scope_id or self.scopes.student,
        ))
        self.scopes.course = scope.scope_id
        return scope.scope_id

    async def create_session_scope(
        self,
        session_topic: str,
        *,
        parent_scope_id: str | None = None,
    ) -> str:
        """创建单次学习会话 Scope"""
        scope = await self.client.create_scope(CreateScopeRequest(
            title=f"会话: {session_topic}",
            summary=f"学习会话 - {session_topic}",
            idempotency_key=f"session:{session_topic}:{id(self)}",
            parent_scope_id=parent_scope_id or self.scopes.course,
        ))
        self.scopes.session = scope.scope_id
        return scope.scope_id

    # ── Memory 操作 ─────────────────────────────────────────

    async def remember(
        self,
        scope_id: str,
        kind: str,
        text: str,
        *,
        reason: str = "",
        description: str | None = None,
    ):
        """记录一条学习记忆"""
        return await self.client.remember_memory(RememberMemoryRequest(
            scope_id=scope_id,
            kind=kind,
            text=text,
            reason=reason,
            description=description,
        ))

    async def search_knowledge(
        self,
        scope_id: str,
        query: str,
        *,
        mode: str = "fts",
        limit: int = 10,
    ):
        """搜索学习相关知识

        Returns response with .hits list; each hit has .memory.kind, .memory.text, .score
        默认使用 FTS 全文检索（无需 embedding 模型）
        """
        return await self.client.search_memory(SearchMemoryRequest(
            scope_id=scope_id,
            query=query,
            mode=mode,
            limit=limit,
        ))

    async def get_context(self, scope_id: str, query: str, *, max_bytes: int = 8000):
        """获取上下文（用于注入 LLM prompt）"""
        return await self.client.prepare_context(PrepareContextRequest(
            scope_id=scope_id,
            query=query,
            max_bytes=max_bytes,
        ))

    # ── Source 操作 ─────────────────────────────────────────

    async def save_learning_material(
        self,
        scope_id: str,
        material_type: str,
        content: dict[str, Any],
    ):
        """保存学习材料为 Source"""
        return await self.client.create_source(scope_id, CreateSourceRequest(
            content={"type": material_type, **content},
        ))

    # ── Experience 操作 ─────────────────────────────────────

    async def record_practice_experience(
        self,
        scope_id: str,
        situation: str,
        action: str,
        outcome: str,
        lesson: str,
    ):
        """记录一次练习经验"""
        return await self.client.create_artifact(scope_id, CreateArtifactRequest(
            family="experience",
            content={
                "situation": situation,
                "action": action,
                "outcome": outcome,
                "lesson": lesson,
            },
        ))

    # ── 记忆提取 ────────────────────────────────────────────

    async def flush_memories(self, scope_id: str):
        """触发 Source -> Memory 提取"""
        return await self.client.flush_memory(FlushMemoryRequest(
            scope_id=scope_id,
        ))

    # ── 会话状态 (用 Atomic Memory 实现轻量 Handoff) ────────

    async def save_session_state(self, scope_id: str, state: dict[str, Any]):
        """保存会话状态（用于跨会话恢复）"""
        import json
        return await self.remember(
            scope_id=scope_id,
            kind="session_state",
            text=json.dumps(state, ensure_ascii=False),
            reason="会话结束，保存学习状态",
        )

    async def load_session_state(self, scope_id: str) -> dict | None:
        """加载最近的会话状态"""
        import json
        result = await self.search_knowledge(
            scope_id=scope_id,
            query="session_state",
            mode="fts",
            limit=1,
        )
        if result.hits:
            try:
                return json.loads(result.hits[0].memory.text)
            except (json.JSONDecodeError, AttributeError):
                pass
        return None
