"""数据模型"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Milestone:
    """学习里程碑"""
    week: int
    topic: str
    objectives: list[str] = field(default_factory=list)
    estimated_hours: float = 5.0
    completed: bool = False
    notes: str = ""


@dataclass
class LearningPlan:
    """学习计划"""
    course_name: str
    goal: str
    total_weeks: int
    milestones: list[Milestone] = field(default_factory=list)
    start_date: date = field(default_factory=date.today)
    created_at: datetime = field(default_factory=datetime.now)

    def current_milestone(self, current_week: int) -> Milestone | None:
        """获取当前周的里程碑"""
        for m in self.milestones:
            if m.week == current_week and not m.completed:
                return m
        return None

    def progress_percent(self) -> float:
        """计算完成百分比"""
        if not self.milestones:
            return 0.0
        done = sum(1 for m in self.milestones if m.completed)
        return done / len(self.milestones) * 100

    def summary(self) -> str:
        """生成计划摘要"""
        lines = [f"课程: {self.course_name} | 目标: {self.goal} | 周期: {self.total_weeks}周"]
        for m in self.milestones:
            status = "✓" if m.completed else "○"
            lines.append(f"  {status} 第{m.week}周: {m.topic} ({m.estimated_hours}h)")
        lines.append(f"  进度: {self.progress_percent():.0f}%")
        return "\n".join(lines)


@dataclass
class SessionContext:
    """当前学习会话上下文"""
    session_id: str
    course_scope_id: str
    session_scope_id: str
    topic: str
    resumed_from: dict | None = None
    started_at: datetime = field(default_factory=datetime.now)


@dataclass
class ProgressReport:
    """学习进度报告"""
    course_name: str
    total_milestones: int = 0
    completed_milestones: int = 0
    weak_areas: list[str] = field(default_factory=list)
    strong_areas: list[str] = field(default_factory=list)
    recent_experiences: list[dict] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"📊 学习进度报告: {self.course_name}"]
        lines.append(f"  里程碑: {self.completed_milestones}/{self.total_milestones}")
        if self.weak_areas:
            lines.append(f"  薄弱点: {', '.join(self.weak_areas)}")
        if self.strong_areas:
            lines.append(f"  已掌握: {', '.join(self.strong_areas)}")
        if self.suggestions:
            lines.append("\n💡 建议:")
            for s in self.suggestions:
                lines.append(f"  • {s}")
        return "\n".join(lines)
