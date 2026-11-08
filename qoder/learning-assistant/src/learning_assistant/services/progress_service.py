"""学习进度追踪与分析服务"""
from __future__ import annotations

from typing import TYPE_CHECKING

from learning_assistant.services.models import ProgressReport

if TYPE_CHECKING:
    from learning_assistant.context.client import LearningAssistantClient
    from learning_assistant.llm.analyzer import AnalyzerLLM


class ProgressService:
    """进度追踪服务

    职责：
    - 从 PowerContext Memory 中检索学习数据
    - 调用 LLM 分析进度并生成报告
    - 提供自适应学习建议
    """

    def __init__(self, client: LearningAssistantClient, analyzer: AnalyzerLLM):
        self._client = client
        self._analyzer = analyzer

    async def generate_report(
        self,
        course_scope_id: str,
        course_name: str,
    ) -> ProgressReport:
        """生成学习进度报告"""
        plan_result = await self._client.search_knowledge(
            scope_id=course_scope_id,
            query="学习计划 plan milestone 里程碑",
            mode="fts",
            limit=5,
        )

        weakness_result = await self._client.search_knowledge(
            scope_id=course_scope_id,
            query="薄弱 weakness difficult 困难 错误",
            mode="fts",
            limit=10,
        )

        mastery_result = await self._client.search_knowledge(
            scope_id=course_scope_id,
            query="已掌握 mastery completed 完成 理解",
            mode="fts",
            limit=10,
        )

        plan_text = ""
        if plan_result.hits:
            plan_text = "\n".join(h.memory.text for h in plan_result.hits)

        weakness_text = ""
        if weakness_result.hits:
            weakness_text = "\n".join(h.memory.text for h in weakness_result.hits)

        mastery_text = ""
        if mastery_result.hits:
            mastery_text = "\n".join(h.memory.text for h in mastery_result.hits)

        analysis = await self._analyzer.analyze_progress(
            plan=plan_text or "暂无计划数据",
            weaknesses=weakness_text or "暂无薄弱点数据",
            masteries=mastery_text or "暂无掌握数据",
        )

        return ProgressReport(
            course_name=course_name,
            total_milestones=analysis.get("total", 0),
            completed_milestones=analysis.get("completed", 0),
            weak_areas=analysis.get("weak_areas", []),
            strong_areas=analysis.get("strong_areas", []),
            recent_experiences=analysis.get("recent", []),
            suggestions=analysis.get("suggestions", []),
        )

    async def get_adaptive_suggestions(
        self,
        course_scope_id: str,
    ) -> list[str]:
        """获取自适应学习建议"""
        context = await self._client.get_context(
            scope_id=course_scope_id,
            query="学习进度 薄弱点 建议 progress weakness suggestion",
            max_bytes=8000,
        )

        if not context or not context.content:
            return ["暂无足够数据生成建议，请继续学习后再查看"]

        return await self._analyzer.suggest_next_steps(context.content)
