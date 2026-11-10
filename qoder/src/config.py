"""Configuration for AI Life Simulator."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class PowerContextConfig:
    server_url: str = "http://127.0.0.1:8000"
    api_token: str = ""
    default_max_bytes: int = 4000
    timeout: int = 30


@dataclass
class LLMConfig:
    api_base: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    temperature: float = 0.85
    max_tokens: int = 2000
    timeout: int = 60


@dataclass
class GameConfig:
    host: str = "0.0.0.0"
    port: int = 8080
    max_sessions: int = 100
    session_timeout_hours: int = 24
    starting_age_range: tuple[int, int] = (0, 5)
    max_age: int = 100
    significance_threshold: float = 0.6


@dataclass
class Settings:
    pc: PowerContextConfig = field(default_factory=PowerContextConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    game: GameConfig = field(default_factory=GameConfig)


def load_settings() -> Settings:
    return Settings(
        pc=PowerContextConfig(
            server_url=os.getenv("PC_SERVER_URL", "http://127.0.0.1:8000"),
            api_token=os.getenv("PC_API_TOKEN", ""),
            default_max_bytes=int(os.getenv("PC_MAX_BYTES", "4000")),
            timeout=int(os.getenv("PC_TIMEOUT", "30")),
        ),
        llm=LLMConfig(
            api_base=os.getenv("LLM_API_BASE", "https://api.openai.com/v1"),
            api_key=os.getenv("LLM_API_KEY", ""),
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.85")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2000")),
            timeout=int(os.getenv("LLM_TIMEOUT", "60")),
        ),
        game=GameConfig(
            host=os.getenv("GAME_HOST", "0.0.0.0"),
            port=int(os.getenv("GAME_PORT", "8080")),
            max_sessions=int(os.getenv("GAME_MAX_SESSIONS", "100")),
        ),
    )
