"""自适应学习策略引擎

根据学生的练习记录和记忆中的薄弱点，动态调整教学策略。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from learning_assistant.context.client import LearningAssistantClient
    from learning_assistant.llm.analyzer import AnalyzerLLM


class DifficultyLevel(Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class LearningStyle(Enum):
    THEORY_FIRST = "theory_first"
    PRACTICE_FIRST = "practice_first"
    VISUAL = "visual"
    TEXTUAL = "textual"


@dataclass
class AdaptiveState:
    """自适应状态"""
    current_difficulty: DifficultyLevel = DifficultyLevel.BEGINNER
    learning_style: LearningStyle = LearningStyle.THEORY_FIRST
    review_interval_days: int = 7
    focus_areas: list[str] = field(default_factory=list)


class AdaptiveService:
    """自适应策略引擎

    职责：
    - 追踪学生答题正确率
    - 自动调整难度等级
    - 识别薄弱知识点并安排间隔复习
    - 将自适应状态持久化到 PowerContext Memory
    """

    def __init__(self, client: LearningAssistantClient, analyzer: AnalyzerLLM):
        self._client = client
        self._analyzer = analyzer
        self._state = AdaptiveState()

    async def load_state(self, student_scope_id: str):
        """从 Memory 加载自适应状态"""
        result = await self._client.search_knowledge(
            scope_id=student_scope_id,
            query="adaptive_state 学习偏好 难度 风格",
            mode="fts",
            limit=5,
        )
        if result.hits:
            self._parse_state_from_memory(result.hits)

    async def update_after_exercise(
        self,
        course_scope_id: str,
        exercise_result: str,
        topic: str,
    ):
        """根据练习结果更新自适应状态

        Args:
            course_scope_id: 课程 Scope ID
            exercise_result: "correct" | "incorrect" | "partial"
            topic: 练习主题
        """
        if exercise_result == "correct":
            await self._maybe_increase_difficulty(course_scope_id, topic)
        elif exercise_result == "incorrect":
            await self._record_weakness(course_scope_id, topic)
            await self._schedule_review(course_scope_id, topic)

    async def get_teaching_strategy(
        self,
        course_scope_id: str,
        topic: str,
    ) -> dict[str, Any]:
        """获取当前教学策略"""
        return {
            "difficulty": self._state.current_difficulty.value,
            "style": self._state.learning_style.value,
            "focus_areas": list(self._state.focus_areas),
            "review_due": self._check_review_due(topic),
            "review_interval_days": self._state.review_interval_days,
        }

    async def _maybe_increase_difficulty(self, scope_id: str, topic: str):
        levels = list(DifficultyLevel)
        current_idx = levels.index(self._state.current_difficulty)
        if current_idx < len(levels) - 1:
            self._state.current_difficulty = levels[current_idx + 1]
            await self._client.remember(
                scope_id=scope_id,
                kind="adaptive_state",
                text=f"难度提升至 {self._state.current_difficulty.value}，主题: {topic}",
                reason="连续正确，自动调整难度",
            )

    async def _record_weakness(self, scope_id: str, topic: str):
        await self._client.remember(
            scope_id=scope_id,
            kind="weakness",
            text=f"薄弱知识点: {topic}",
            reason="练习错误，记录薄弱点",
        )
        if topic not in self._state.focus_areas:
            self._state.focus_areas.append(topic)

    async def _schedule_review(self, scope_id: str, topic: str):
        await self._client.remember(
            scope_id=scope_id,
            kind="review_schedule",
            text=f"需复习: {topic}，间隔: {self._state.review_interval_days}天",
            reason="错误后安排间隔复习",
        )

    def _check_review_due(self, topic: str) -> bool:
        return topic in self._state.focus_areas

    def _parse_state_from_memory(self, hits: list):
        for hit in hits:
            text = hit.memory.text.lower()
            if "难度" in text or "difficulty" in text:
                for level in DifficultyLevel:
                    if level.value in text:
                        self._state.current_difficulty = level
            if "偏好" in text or "style" in text:
                for style in LearningStyle:
                    if style.value in text:
                        self._state.learning_style = style
