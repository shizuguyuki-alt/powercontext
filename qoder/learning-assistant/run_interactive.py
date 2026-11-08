"""Interactive study session - user types, DeepSeek tutor responds"""
import asyncio
import json
import sys
import os
from pathlib import Path

os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

API_KEY = os.environ.get("OPENAI_API_KEY", "sk-your-api-key-here")
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"

workspace = Path.home() / ".learning-assistant-interactive"
workspace.mkdir(parents=True, exist_ok=True)


async def main():
    from openai import AsyncOpenAI
    from learning_assistant.context.server import EmbeddedPowerContextServer
    from learning_assistant.context.client import LearningAssistantClient
    from learning_assistant.llm.tutor import TutorLLM
    from learning_assistant.services.session_service import SessionService
    from powercontext.http import CreateScopeRequest

    # Start server
    server = EmbeddedPowerContextServer(
        workspace=workspace,
        database_kind="sqlite",
    )
    url = server.start()

    client = LearningAssistantClient(url)
    llm = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)

    async with client as pc:
        # Create student scope
        s = await pc.create_scope(CreateScopeRequest(
            title="Student: Interactive User",
            summary="Interactive test session",
            idempotency_key=f"interactive:student:{id(client)}",
        ))
        student_id = s.scope_id
        client.scopes.student = student_id

        # Create course scope
        c = await pc.create_scope(CreateScopeRequest(
            title="Course: Interactive Test",
            summary="User-driven interactive session",
            idempotency_key=f"interactive:course:{id(client)}",
            parent_scope_id=student_id,
        ))
        course_id = c.scope_id
        client.scopes.course = course_id

        # Save some initial context
        await client.remember(
            student_id, "student_profile",
            "Interactive test user, exploring the learning assistant",
            reason="init",
        )

        # Start session
        session_svc = SessionService(client, TutorLLM(llm, model=MODEL))
        session = await session_svc.start_session(
            course_scope_id=course_id,
            topic="Free-form interactive learning",
        )

        # Print welcome
        print("\n" + "=" * 60)
        print("  Learning Assistant - Interactive Session")
        print("  Powered by DeepSeek + PowerContext")
        print("=" * 60)
        print(f"\n  Server: {url}")
        print(f"  Student Scope: {student_id}")
        print(f"  Course Scope:  {course_id}")
        print(f"  Session:       {session.session_id}")
        print("\n" + "-" * 60)
        print("  Type your questions. Commands:")
        print("    /quit    - end session and save progress")
        print("    /save    - manually save progress note")
        print("    /status  - show current session state")
        print("-" * 60 + "\n")

        progress_notes = []

        while True:
            try:
                user_input = input("You > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\nInterrupted.")
                break

            if not user_input:
                continue

            if user_input.lower() == "/quit":
                break

            if user_input.lower() == "/save":
                note = input("  Note > ").strip()
                if note:
                    progress_notes.append(note)
                    print(f"  [saved] {note}\n")
                continue

            if user_input.lower() == "/status":
                print(f"\n  Session: {session.session_id}")
                print(f"  Topic: {session.topic}")
                print(f"  Notes saved: {len(progress_notes)}")
                if session.resumed_from:
                    print(f"  Resumed from: {session.resumed_from.get('topic', '?')}")
                print()
                continue

            # Get tutor response
            try:
                response = await session_svc.chat(user_input)
                print(f"\nTutor > {response}\n")
            except Exception as e:
                print(f"\n  [error] {e}\n")

        # End session
        summary = progress_notes or ["Completed interactive test session"]
        await session_svc.end_session(
            progress_summary=summary,
            next_action="Continue exploring topics",
        )

        print("\n" + "=" * 60)
        print(f"  Session ended. {len(summary)} progress note(s) saved.")
        print("=" * 60 + "\n")

    server.stop()


if __name__ == "__main__":
    asyncio.run(main())
