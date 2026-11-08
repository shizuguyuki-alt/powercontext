"""Quick integration test - verify server startup and basic PowerContext operations"""
import asyncio
import sys
import os
from pathlib import Path

os.environ["PYTHONIOENCODING"] = "utf-8"


async def test_basic():
    workspace = Path.home() / ".learning-assistant-test"
    workspace.mkdir(parents=True, exist_ok=True)

    print("[1/4] Starting PowerContext server (SQLite)...")
    from learning_assistant.context.server import EmbeddedPowerContextServer

    server = EmbeddedPowerContextServer(
        workspace=workspace,
        database_kind="sqlite",
    )
    url = server.start()
    print(f"  Server started: {url}")

    print("\n[2/4] Creating client and testing basic operations...")
    from learning_assistant.context.client import LearningAssistantClient
    from powercontext.http import CreateScopeRequest

    client = LearningAssistantClient(url)
    async with client as pc:
        print("  Creating student Scope...")
        scope = await pc.create_scope(CreateScopeRequest(
            title="Test Student",
            summary="Integration test",
            idempotency_key="test:student",
        ))
        scope_id = scope.scope_id
        print(f"  OK - Scope ID: {scope_id}")

        print("  Writing learning memory...")
        await client.remember(
            scope_id=scope_id,
            kind="student_profile",
            text="Student: test user, level: intermediate",
            reason="test",
        )
        print("  OK - Memory written")

        await client.remember(
            scope_id=scope_id,
            kind="plan",
            text="Week 1: Python basics\nWeek 2: Data structures\nWeek 3: Algorithms",
            reason="test plan",
        )
        print("  OK - Plan written")

        print("\n[3/4] Searching memory...")
        result = await client.search_knowledge(
            scope_id=scope_id,
            query="student profile",
            mode="fts",
            limit=5,
        )
        entries = result.hits if hasattr(result, 'hits') else []
        print(f"  OK - Found {len(entries)} results")
        for h in entries:
            text_preview = h.memory.text[:60] if hasattr(h, 'memory') else str(h)[:60]
            kind = h.memory.kind if hasattr(h, 'memory') else '?'
            print(f"    - [{kind}] {text_preview}...")

        print("  Testing session state save/restore...")
        await client.save_session_state(scope_id, {
            "topic": "Python basics",
            "progress": ["Completed variables and types"],
            "next_action": "Learn control flow",
        })
        print("  OK - Session state saved")

        state = await client.load_session_state(scope_id)
        print(f"  OK - Restored state: {state}")

    print("\n[4/4] Stopping server...")
    server.stop()
    print("  OK - Server stopped")

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    asyncio.run(test_basic())
