"""CLI 命令行应用

提供学习助手的完整命令行交互：
  learn init          - 初始化学生档案
  learn create-plan   - 创建学习计划
  learn study         - 开始学习会话（交互式）
  learn progress      - 查看学习进度
  learn adaptive      - 查看自适应策略状态
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from openai import AsyncOpenAI
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from learning_assistant.context.client import LearningAssistantClient
from learning_assistant.context.server import EmbeddedPowerContextServer
from learning_assistant.llm.analyzer import AnalyzerLLM
from learning_assistant.llm.planner import PlanLLM
from learning_assistant.llm.tutor import TutorLLM
from learning_assistant.services.adaptive_service import AdaptiveService
from learning_assistant.services.plan_service import PlanService
from learning_assistant.services.progress_service import ProgressService
from learning_assistant.services.session_service import SessionService

console = Console()
app = typer.Typer(
    name="learn",
    help="基于 PowerContext 的自适应学习助手",
    no_args_is_help=True,
)


# ── 内部工具函数 ──────────────────────────────────────────────


def _default_workspace() -> Path:
    ws = Path.home() / ".learning-assistant"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def _detect_database_kind() -> str:
    if sys.platform in ("linux", "darwin"):
        return "seekdb"
    return "sqlite"


async def _start_server(
    workspace: Path,
    api_key: str,
    base_url: str | None = None,
    database_kind: str | None = None,
) -> tuple[EmbeddedPowerContextServer, str]:
    """启动内嵌 PowerContext 服务器"""
    db_kind = database_kind or _detect_database()

    server = EmbeddedPowerContextServer(
        workspace=workspace,
        database_kind=db_kind,
        generation_model="gpt-4o-mini",
        generation_base_url=base_url or "https://api.openai.com/v1",
        generation_api_key=api_key,
        embedding_model="text-embedding-3-small",
        embedding_base_url=base_url or "https://api.openai.com/v1",
        embedding_api_key=api_key,
    )
    url = server.start()
    return server, url


def _make_llm_client(api_key: str, base_url: str | None = None) -> AsyncOpenAI:
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


# ── CLI 命令 ──────────────────────────────────────────────────


@app.command()
def init(
    student_name: str = typer.Argument(..., help="学生姓名"),
    level: str = typer.Option("beginner", help="学习水平: beginner/intermediate/advanced"),
    api_key: str = typer.Option(..., envvar="OPENAI_API_KEY", help="OpenAI API Key"),
    base_url: Optional[str] = typer.Option(None, envvar="OPENAI_BASE_URL", help="API Base URL (可选)"),
    workspace: Optional[Path] = typer.Option(None, help="工作目录"),
):
    """初始化学生档案"""

    async def _run():
        ws = workspace or _default_workspace()
        server, url = await _start_server(ws, api_key, base_url)
        try:
            client = LearningAssistantClient(url)
            async with client as pc:
                scope_id = await client.create_student_scope(
                    student_name=student_name,
                    profile={"name": student_name, "level": level},
                )
                await client.remember(
                    scope_id=scope_id,
                    kind="student_profile",
                    text=f"学生: {student_name}，水平: {level}",
                    reason="初始化学生档案",
                )
                console.print(Panel(
                    f"[bold green]学生档案已创建[/]\n"
                    f"  姓名: {student_name}\n"
                    f"  水平: {level}\n"
                    f"  Scope ID: [cyan]{scope_id}[/]\n"
                    f"  数据库: [yellow]{server.database_kind}[/]\n"
                    f"  工作目录: {ws}",
                    title="🎓 初始化完成",
                ))
                console.print(f"\n[dim]请保存 Scope ID: [bold]{scope_id}[/bold][/dim]")
        finally:
            server.stop()

    asyncio.run(_run())


@app.command()
def create_plan(
    course: str = typer.Argument(..., help="课程名称"),
    goal: str = typer.Option(..., help="学习目标"),
    weeks: int = typer.Option(4, help="学习周期（周）"),
    background: str = typer.Option("", help="学生背景描述"),
    api_key: str = typer.Option(..., envvar="OPENAI_API_KEY", help="OpenAI API Key"),
    base_url: Optional[str] = typer.Option(None, envvar="OPENAI_BASE_URL", help="API Base URL"),
    student_scope: str = typer.Option(..., help="学生 Scope ID"),
    workspace: Optional[Path] = typer.Option(None, help="工作目录"),
):
    """创建学习计划"""

    async def _run():
        ws = workspace or _default_workspace()
        server, url = await _start_server(ws, api_key, base_url)
        try:
            client = LearningAssistantClient(url)
            async with client as pc:
                client.scopes.student = student_scope
                llm = _make_llm_client(api_key, base_url)
                plan_service = PlanService(client, PlanLLM(llm))

                with console.status("[bold green]正在生成学习计划..."):
                    plan = await plan_service.create_plan(
                        course_name=course,
                        goal=goal,
                        total_weeks=weeks,
                        student_background=background,
                    )

                console.print(Panel(plan.summary(), title=f"📋 {course}"))
                console.print(f"\n[dim]课程 Scope ID: [bold]{client.scopes.course}[/bold][/dim]")
        finally:
            server.stop()

    asyncio.run(_run())


@app.command()
def study(
    topic: str = typer.Argument(..., help="本次学习主题"),
    course_scope: str = typer.Option(..., help="课程 Scope ID"),
    api_key: str = typer.Option(..., envvar="OPENAI_API_KEY", help="OpenAI API Key"),
    base_url: Optional[str] = typer.Option(None, envvar="OPENAI_BASE_URL", help="API Base URL"),
    workspace: Optional[Path] = typer.Option(None, help="工作目录"),
):
    """开始交互式学习会话"""

    async def _run():
        ws = workspace or _default_workspace()
        server, url = await _start_server(ws, api_key, base_url)
        try:
            client = LearningAssistantClient(url)
            async with client as pc:
                llm = _make_llm_client(api_key, base_url)
                session_service = SessionService(client, TutorLLM(llm))

                with console.status("[bold green]正在恢复学习上下文..."):
                    session = await session_service.start_session(
                        course_scope_id=course_scope,
                        topic=topic,
                    )

                if session.resumed_from:
                    prev = session.resumed_from
                    progress = prev.get("progress", [])
                    next_act = prev.get("next_action", "")
                    console.print(Panel(
                        f"[dim]上次进度: {'; '.join(progress) if progress else '无'}[/]\n"
                        f"[dim]下一步: {next_act}[/]",
                        title="🔄 已恢复学习上下文",
                        border_style="blue",
                    ))
                else:
                    console.print(Panel(
                        f"主题: {topic}",
                        title="📖 新学习会话",
                        border_style="green",
                    ))

                console.print("\n[bold]交互命令:[/bold]")
                console.print("  [cyan]quit[/cyan]  - 退出并保存进度")
                console.print("  [cyan]save[/cyan]  - 手动保存当前进度")
                console.print("  [cyan]exercise[/cyan] - 记录一次练习\n")

                progress_notes: list[str] = []

                while True:
                    try:
                        user_input = console.input("[bold green]你 > [/bold green]").strip()
                    except (EOFError, KeyboardInterrupt):
                        console.print("\n[yellow]中断退出[/]")
                        break

                    if not user_input:
                        continue

                    if user_input.lower() == "quit":
                        break

                    if user_input.lower() == "save":
                        note = console.input("[dim]记录学习成果 > [/dim]").strip()
                        if note:
                            progress_notes.append(note)
                            console.print(f"[green]✓ 已记录: {note}[/]")
                        continue

                    if user_input.lower() == "exercise":
                        console.print("[dim]记录练习经验:[/]")
                        situation = console.input("  题目/情境 > ").strip()
                        action = console.input("  你的做法 > ").strip()
                        outcome = console.input("  结果 > ").strip()
                        lesson = console.input("  学到什么 > ").strip()
                        await session_service.record_exercise(situation, action, outcome, lesson)
                        console.print("[green]✓ 练习经验已记录[/]\n")
                        continue

                    with console.status("[bold blue]思考中..."):
                        response = await session_service.chat(user_input)
                    console.print(f"\n[bold blue]助手 > [/bold blue]{response}\n")

                next_action = ""
                try:
                    next_action = console.input(
                        "\n[dim]下一步计划 (回车跳过) > [/dim]"
                    ).strip()
                except (EOFError, KeyboardInterrupt):
                    pass

                summary = progress_notes or [f"完成主题 '{topic}' 的学习"]
                await session_service.end_session(
                    progress_summary=summary,
                    next_action=next_action or None,
                )
                console.print(Panel(
                    f"[green]会话已保存[/]\n"
                    f"  主题: {topic}\n"
                    f"  记录: {len(summary)} 条",
                    title="✅ 会话结束",
                ))
        finally:
            server.stop()

    asyncio.run(_run())


@app.command()
def progress(
    course_scope: str = typer.Argument(..., help="课程 Scope ID"),
    course_name: str = typer.Option(..., help="课程名称"),
    api_key: str = typer.Option(..., envvar="OPENAI_API_KEY", help="OpenAI API Key"),
    base_url: Optional[str] = typer.Option(None, envvar="OPENAI_BASE_URL", help="API Base URL"),
    workspace: Optional[Path] = typer.Option(None, help="工作目录"),
):
    """查看学习进度报告"""

    async def _run():
        ws = workspace or _default_workspace()
        server, url = await _start_server(ws, api_key, base_url)
        try:
            client = LearningAssistantClient(url)
            async with client as pc:
                llm = _make_llm_client(api_key, base_url)
                progress_service = ProgressService(client, AnalyzerLLM(llm))

                with console.status("[bold green]正在分析学习进度..."):
                    report = await progress_service.generate_report(
                        course_scope_id=course_scope,
                        course_name=course_name,
                    )

                console.print(Panel(report.summary(), title="📊 进度报告"))
        finally:
            server.stop()

    asyncio.run(_run())


@app.command()
def adaptive(
    scope_id: str = typer.Argument(..., help="课程或学生 Scope ID"),
    topic: str = typer.Option("", help="当前学习主题"),
    api_key: str = typer.Option(..., envvar="OPENAI_API_KEY", help="OpenAI API Key"),
    base_url: Optional[str] = typer.Option(None, envvar="OPENAI_BASE_URL", help="API Base URL"),
    workspace: Optional[Path] = typer.Option(None, help="工作目录"),
):
    """查看自适应策略状态与建议"""

    async def _run():
        ws = workspace or _default_workspace()
        server, url = await _start_server(ws, api_key, base_url)
        try:
            client = LearningAssistantClient(url)
            async with client as pc:
                llm = _make_llm_client(api_key, base_url)
                adaptive_service = AdaptiveService(client, AnalyzerLLM(llm))

                await adaptive_service.load_state(scope_id)

                if topic:
                    strategy = await adaptive_service.get_teaching_strategy(scope_id, topic)
                    console.print(Panel(
                        f"  难度: [bold]{strategy['difficulty']}[/]\n"
                        f"  风格: {strategy['style']}\n"
                        f"  重点关注: {', '.join(strategy['focus_areas']) or '无'}\n"
                        f"  需要复习: {'是' if strategy['review_due'] else '否'}\n"
                        f"  复习间隔: {strategy['review_interval_days']}天",
                        title="🎯 教学策略",
                    ))

                progress_service = ProgressService(client, AnalyzerLLM(llm))
                suggestions = await progress_service.get_adaptive_suggestions(scope_id)
                if suggestions:
                    text = "\n".join(f"  • {s}" for s in suggestions)
                    console.print(Panel(text, title="💡 学习建议"))
        finally:
            server.stop()

    asyncio.run(_run())


if __name__ == "__main__":
    app()
