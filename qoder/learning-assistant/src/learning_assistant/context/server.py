"""内嵌 PowerContext 服务器管理

在进程内启动 PowerContext Server，使用 seekdb 或 SQLite 作为存储后端。
"""
from __future__ import annotations

import socket
import sys
import threading
from pathlib import Path

import uvicorn

from powercontext.builtin.persistence.sqlite import SQLiteConfig
from powercontext.builtin.runtime.config import (
    InferenceConfig,
    RuntimeConfig,
)
from powercontext.server.factory import create_server_app
from powercontext.server.settings import (
    AccessControlConfig,
    BearerAuthConfig,
    DashboardConfig,
    HttpConfig,
    McpConfig,
    MetricsConfig,
    ServerSettings,
    TracingConfig,
)


def _build_seekdb_config(path: Path, database: str):
    if sys.platform not in ("linux", "darwin"):
        raise RuntimeError(f"seekdb 不支持 {sys.platform}，请使用 SQLite")
    from powercontext.builtin.persistence.seekdb import SeekDBConfig
    return SeekDBConfig(path=path, database=database)


class EmbeddedPowerContextServer:
    """进程内 PowerContext 服务器

    用法::

        server = EmbeddedPowerContextServer(workspace=Path("./data"))
        url = server.start()
        # ... 使用 url 创建客户端 ...
        server.stop()
    """

    def __init__(
        self,
        workspace: Path,
        *,
        database_kind: str = "sqlite",
        seekdb_path: Path | None = None,
        seekdb_database: str = "powercontext",
        sqlite_url: str | None = None,
        host: str = "127.0.0.1",
        port: int = 0,
        generation_model: str | None = None,
        generation_base_url: str | None = None,
        generation_api_key: str | None = None,
        embedding_model: str | None = None,
        embedding_base_url: str | None = None,
        embedding_api_key: str | None = None,
    ):
        self.workspace = workspace
        self.database_kind = database_kind
        self.seekdb_path = seekdb_path or (workspace / "seekdb_data")
        self.seekdb_database = seekdb_database
        self.sqlite_url = sqlite_url or f"sqlite+aiosqlite:///{workspace / 'powercontext.db'}"
        self.host = host
        self._requested_port = port
        self._generation_model = generation_model
        self._generation_base_url = generation_base_url
        self._generation_api_key = generation_api_key
        self._embedding_model = embedding_model
        self._embedding_base_url = embedding_base_url
        self._embedding_api_key = embedding_api_key
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._actual_port: int | None = None

    @property
    def base_url(self) -> str:
        assert self._actual_port is not None
        return f"http://{self.host}:{self._actual_port}"

    def _build_database_config(self):
        if self.database_kind == "seekdb":
            return _build_seekdb_config(self.seekdb_path, self.seekdb_database)
        return SQLiteConfig(url=self.sqlite_url)

    def _build_inference_config(self) -> InferenceConfig:
        from pydantic import SecretStr

        kwargs: dict = {}
        if self._generation_model:
            kwargs["generation_model"] = self._generation_model
        if self._generation_base_url:
            kwargs["generation_base_url"] = self._generation_base_url
        if self._generation_api_key:
            kwargs["generation_headers"] = {"Authorization": SecretStr(f"Bearer {self._generation_api_key}")}
        return InferenceConfig(**kwargs)

    def _build_settings(self) -> ServerSettings:
        return ServerSettings(
            workspace=self.workspace,
            database=self._build_database_config(),
            http=HttpConfig(host=self.host),
            auth=BearerAuthConfig(enabled=False),
            access=AccessControlConfig(mode="disabled"),
            inference=self._build_inference_config(),
            runtime=RuntimeConfig(
                memory_schedule_seconds=None,
                source_window_limit=50,
                artifact_processing_role="all",
            ),
            mcp=McpConfig(enabled=False),
            metrics=MetricsConfig(enabled=False),
            dashboard=DashboardConfig(enabled=False),
            tracing=TracingConfig(enabled=False),
        )

    def start(self) -> str:
        """启动服务器，返回 base_url"""
        self.workspace.mkdir(parents=True, exist_ok=True)
        settings = self._build_settings()

        app = create_server_app(
            settings=settings,
            scheduler_path=self.workspace / "scheduler.db",
        )

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self.host, self._requested_port))
        self._actual_port = listener.getsockname()[1]
        listener.close()

        config = uvicorn.Config(
            app,
            host=self.host,
            port=self._actual_port,
            log_level="warning",
            lifespan="on",
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()

        import time
        time.sleep(1.5)

        return self.base_url

    def stop(self):
        """停止服务器"""
        if self._server:
            self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout=5)
        self._server = None
        self._thread = None
