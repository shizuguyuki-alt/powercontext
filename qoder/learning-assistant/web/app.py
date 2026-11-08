"""Web client for Learning Assistant - FastAPI server with chat UI"""
import asyncio
import json
import sys
import os
from pathlib import Path
from contextlib import asynccontextmanager

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import AsyncOpenAI

from learning_assistant.context.server import EmbeddedPowerContextServer
from learning_assistant.context.client import LearningAssistantClient
from learning_assistant.llm.planner import PlanLLM
from learning_assistant.llm.tutor import TutorLLM
from learning_assistant.llm.analyzer import AnalyzerLLM
from learning_assistant.services.plan_service import PlanService
from learning_assistant.services.session_service import SessionService
from learning_assistant.services.progress_service import ProgressService
from learning_assistant.services.adaptive_service import AdaptiveService
from powercontext.http import CreateScopeRequest

API_KEY = os.environ.get("OPENAI_API_KEY", "sk-your-api-key-here")
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")
MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")
HOST = "127.0.0.1"
PORT = 8090

workspace = Path.home() / ".learning-assistant-web"
workspace.mkdir(parents=True, exist_ok=True)

pc_server: EmbeddedPowerContextServer | None = None
pc_client: LearningAssistantClient | None = None
llm_client: AsyncOpenAI | None = None
student_id: str = ""
course_id: str = ""
session_svc: SessionService | None = None
plan_svc: PlanService | None = None
progress_svc: ProgressService | None = None
adaptive_svc: AdaptiveService | None = None
current_session_id: str = ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pc_server, pc_client, llm_client
    global session_svc, plan_svc, progress_svc, adaptive_svc
    global student_id, course_id

    print("[startup] Starting PowerContext server...")
    pc_server = EmbeddedPowerContextServer(workspace=workspace, database_kind="sqlite")
    url = pc_server.start()
    print(f"[startup] PowerContext at {url}")

    pc_client = LearningAssistantClient(url)
    await pc_client.__aenter__()
    llm_client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)

    session_svc = SessionService(pc_client, TutorLLM(llm_client, model=MODEL))
    plan_svc = PlanService(pc_client, PlanLLM(llm_client, model=MODEL))
    progress_svc = ProgressService(pc_client, AnalyzerLLM(llm_client, model=MODEL))
    adaptive_svc = AdaptiveService(pc_client, AnalyzerLLM(llm_client, model=MODEL))

    print("[startup] Ready!")
    yield

    print("[shutdown] Stopping...")
    await pc_client.__aexit__(None, None, None)
    pc_server.stop()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


async def safe_json(request: Request) -> dict:
    try:
        return await request.json()
    except Exception:
        raw = await request.body()
        return json.loads(raw.decode("utf-8", errors="replace"))


@app.get("/", response_class=HTMLResponse)
async def index():
    return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


@app.post("/api/init")
async def api_init(request: Request):
    global student_id, course_id
    body = await safe_json(request)
    student_name = body.get("student_name", "Student")
    student_level = body.get("level", "beginner")

    scope = await pc_client.client.create_scope(CreateScopeRequest(
        title=f"Student: {student_name}",
        summary=f"{student_level} level learner",
        idempotency_key=f"web:student:{student_name}:{id(pc_client)}",
    ))
    student_id = scope.scope_id
    pc_client.scopes.student = student_id

    await pc_client.remember(
        student_id, "student_profile",
        f"Student: {student_name}, Level: {student_level}",
        reason="Web UI init",
    )
    return {"status": "ok", "student_id": student_id}


@app.post("/api/plan")
async def api_create_plan(request: Request):
    global course_id
    body = await safe_json(request)
    course_name = body.get("course", "Untitled Course")
    goal = body.get("goal", "Learn")
    weeks = body.get("weeks", 4)
    background = body.get("background", "")

    try:
        plan = await plan_svc.create_plan(
            course_name=course_name, goal=goal,
            total_weeks=weeks, student_background=background,
        )
        course_id = pc_client.scopes.course
        return {
            "status": "ok",
            "course_id": course_id,
            "plan": {
                "course_name": plan.course_name,
                "goal": plan.goal,
                "total_weeks": plan.total_weeks,
                "progress": plan.progress_percent(),
                "milestones": [
                    {"week": m.week, "topic": m.topic, "objectives": m.objectives,
                     "hours": m.estimated_hours, "completed": m.completed}
                    for m in plan.milestones
                ],
            },
        }
    except Exception as e:
        c = await pc_client.client.create_scope(CreateScopeRequest(
            title=f"Course: {course_name}", summary=f"Goal: {goal}",
            idempotency_key=f"web:course:{course_name}:{id(pc_client)}",
            parent_scope_id=student_id,
        ))
        course_id = c.scope_id
        pc_client.scopes.course = course_id
        await pc_client.remember(course_id, "plan",
            f"Goal: {goal}, Duration: {weeks} weeks", reason="fallback")
        return {
            "status": "ok", "course_id": course_id,
            "plan": {"course_name": course_name, "goal": goal,
                     "total_weeks": weeks, "progress": 0, "milestones": []},
            "warning": str(e),
        }


@app.post("/api/session/start")
async def api_start_session(request: Request):
    global current_session_id
    body = await safe_json(request)
    topic = body.get("topic", "General learning")

    session = await session_svc.start_session(
        course_scope_id=course_id, topic=topic,
    )
    current_session_id = session.session_id

    resume_info = None
    if session.resumed_from:
        resume_info = {
            "topic": session.resumed_from.get("topic", ""),
            "progress": session.resumed_from.get("progress", []),
            "next_action": session.resumed_from.get("next_action", ""),
        }

    return {
        "status": "ok",
        "session_id": current_session_id,
        "topic": topic,
        "resumed": resume_info,
    }


@app.post("/api/chat")
async def api_chat(request: Request):
    body = await safe_json(request)
    message = body.get("message", "")

    try:
        response = await session_svc.chat(message)
        return {"status": "ok", "response": response}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/session/end")
async def api_end_session(request: Request):
    body = await safe_json(request)
    notes = body.get("notes", [])
    next_action = body.get("next_action", "")

    try:
        await session_svc.end_session(
            progress_summary=notes or ["Session completed"],
            next_action=next_action or None,
        )
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/exercise")
async def api_record_exercise(request: Request):
    body = await safe_json(request)
    try:
        await session_svc.record_exercise(
            situation=body.get("situation", ""),
            action=body.get("action", ""),
            outcome=body.get("outcome", ""),
            lesson=body.get("lesson", ""),
        )
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/progress")
async def api_progress():
    if not course_id:
        return {"status": "error", "error": "No course created"}
    try:
        report = await progress_svc.generate_report(course_id, "Course")
        return {
            "status": "ok",
            "report": {
                "total": report.total_milestones,
                "completed": report.completed_milestones,
                "weak_areas": report.weak_areas,
                "strong_areas": report.strong_areas,
                "suggestions": report.suggestions,
            },
        }
    except Exception as e:
        plan_r = await pc_client.search_knowledge(course_id, "plan", mode="fts", limit=3)
        memories = [{"kind": h.memory.kind, "text": h.memory.text} for h in plan_r.hits]
        return {"status": "ok", "report": None, "memories": memories, "warning": str(e)}


@app.get("/api/strategy")
async def api_strategy():
    if not course_id:
        return {"status": "error", "error": "No course created"}
    try:
        await adaptive_svc.load_state(course_id)
        strategy = await adaptive_svc.get_teaching_strategy(course_id, "general")
        return {"status": "ok", "strategy": strategy}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/memories")
async def api_memories(scope: str = "student"):
    sid = student_id if scope == "student" else course_id
    if not sid:
        return {"hits": []}
    r = await pc_client.search_knowledge(sid, "learning plan progress mastery weakness session profile", mode="fts", limit=20)
    return {
        "hits": [
            {"kind": h.memory.kind, "text": h.memory.text, "score": h.score}
            for h in r.hits
        ]
    }


if __name__ == "__main__":
    import uvicorn
    print(f"\n  Learning Assistant Web Client")
    print(f"  Open: http://{HOST}:{PORT}\n")
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
