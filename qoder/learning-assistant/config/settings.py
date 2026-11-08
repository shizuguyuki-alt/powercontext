"""学习助手全局配置"""
from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings


DEFAULT_WORKSPACE = Path.home() / ".learning-assistant"


class DatabaseSettings(BaseModel):
    kind: str = "seekdb" if sys.platform in ("linux", "darwin") else "sqlite"
    seekdb_path: Path = DEFAULT_WORKSPACE / "seekdb_data"
    sqlite_url: str = f"sqlite+aiosqlite:///{DEFAULT_WORKSPACE / 'powercontext.db'}"
    database_name: str = "powercontext"


class LLMSettings(BaseModel):
    generation_model: str = "gpt-4o-mini"
    generation_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    embedding_base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    temperature: float = 0.7


class ServerSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 0
    workspace: Path = DEFAULT_WORKSPACE


class AppSettings(BaseSettings):
    model_config = {"env_prefix": "LEARNING_ASSISTANT_"}

    database: DatabaseSettings = DatabaseSettings()
    llm: LLMSettings = LLMSettings()
    server: ServerSettings = ServerSettings()


def load_settings() -> AppSettings:
    return AppSettings()


def ensure_workspace(workspace: Path | None = None) -> Path:
    ws = workspace or DEFAULT_WORKSPACE
    ws.mkdir(parents=True, exist_ok=True)
    return ws
