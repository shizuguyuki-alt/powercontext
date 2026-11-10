"""FastAPI application for AI Life Simulator — action-based edition."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import load_settings
from .engine import GameEngine
from .models import (
    ABILITY_CATEGORIES,
    ABILITY_LABELS,
    CATEGORY_LABELS,
    PerformActionRequest,
    StartGameRequest,
    get_available_actions,
    get_rank,
    RANK_COLORS,
    STAGE_LABELS,
)

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
engine: GameEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    settings = load_settings()
    engine = GameEngine(settings)
    await engine.initialize()
    logger.info("AI Life Simulator started — PowerContext: %s", "connected" if engine.pc_available else "offline")
    yield
    if engine:
        await engine.shutdown()


app = FastAPI(title="AI Life Simulator", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _eng() -> GameEngine:
    if engine is None:
        raise HTTPException(503, "Engine not initialized")
    return engine


def _char_dict(char) -> dict:
    abilities = {}
    for key, val in char.abilities.items():
        abilities[key] = {
            "value": val,
            "rank": get_rank(val),
            "label": ABILITY_LABELS.get(key, key),
            "color": RANK_COLORS.get(get_rank(val), "#666"),
        }
    return {
        "name": char.profile.name,
        "gender": char.profile.gender,
        "age": char.age,
        "life_stage": char.life_stage.value,
        "life_stage_label": STAGE_LABELS.get(char.life_stage, ""),
        "birth_city": char.profile.birth_city,
        "family_background": char.profile.family_background,
        "occupation": char.occupation,
        "vitals": {
            "health": char.vitals.health,
            "happiness": char.vitals.happiness,
            "energy": char.vitals.energy,
        },
        "abilities": abilities,
        "ability_categories": {
            cat: {"label": CATEGORY_LABELS[cat], "keys": keys}
            for cat, keys in ABILITY_CATEGORIES.items()
        },
        "skills": char.skills,
        "relationships": char.relationships,
    }


def _action_dict(action) -> dict:
    return {
        "id": action.id,
        "name": action.name,
        "icon": action.icon,
        "description": action.description,
        "category": action.category,
        "category_label": CATEGORY_LABELS.get(action.category, action.category),
        "effects": [
            {"ability": e.ability, "label": ABILITY_LABELS.get(e.ability, e.ability), "amount": e.amount}
            for e in action.effects
        ],
        "vitality_changes": action.vitality_changes,
        "energy_cost": action.energy_cost,
        "months_advance": action.months_advance,
        "min_age": action.min_age,
        "tags": action.tags,
    }


def _session_dict(s, include_actions=True) -> dict:
    result = {
        "session_id": s.session_id,
        "scope_id": s.scope_id,
        "character": _char_dict(s.character),
        "turn_count": s.turn_count,
        "is_active": s.is_active,
        "memory_count": len(s.memories),
        "experience_count": len(s.experiences),
        "action_log": s.action_log[-10:],
    }
    if include_actions:
        actions = get_available_actions(s.character)
        result["available_actions"] = [_action_dict(a) for a in actions]
    return result


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/status")
async def status():
    eng = _eng()
    return {
        "status": "running",
        "powercontext": "connected" if eng.pc_available else "offline",
        "active_sessions": len(eng._sessions),
    }


@app.post("/api/game/start")
async def start_game(req: StartGameRequest):
    eng = _eng()
    session = await eng.start_game(name=req.name, gender=req.gender, background=req.background)
    return _session_dict(session)


@app.post("/api/game/{session_id}/action")
async def perform_action(session_id: str, req: PerformActionRequest):
    eng = _eng()
    try:
        result = await eng.perform_action(session_id, req.action_id)
        session = eng._get_session(session_id)
        return {
            "result": result.model_dump(),
            "character": _char_dict(session.character),
            "available_actions": [_action_dict(a) for a in get_available_actions(session.character)],
            "turn_count": session.turn_count,
            "is_active": session.is_active,
        }
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.get("/api/game/{session_id}/actions")
async def list_actions(session_id: str):
    eng = _eng()
    try:
        session = eng._get_session(session_id)
        actions = get_available_actions(session.character)
        return {"actions": [_action_dict(a) for a in actions]}
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/api/game/{session_id}/save")
async def save_game(session_id: str):
    eng = _eng()
    try:
        return await eng.save_game(session_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/api/game/load")
async def load_game(req: dict):
    eng = _eng()
    session = await eng.load_game(req.get("scope_id", ""))
    if session is None:
        raise HTTPException(404, "无法加载存档")
    return _session_dict(session)


@app.get("/api/game/{session_id}/timeline")
async def get_timeline(session_id: str):
    eng = _eng()
    try:
        timeline = await eng.get_memory_timeline(session_id)
        experiences = await eng.get_experiences(session_id)
        return {"timeline": timeline, "experiences": experiences}
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.get("/api/game/sessions")
async def list_sessions():
    eng = _eng()
    return {"sessions": eng.list_sessions()}


if __name__ == "__main__":
    import uvicorn
    settings = load_settings()
    uvicorn.run("src.main:app", host=settings.game.host, port=settings.game.port, reload=True)
