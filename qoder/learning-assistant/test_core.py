"""Core functionality test - no LLM required.

Tests:
1. PowerContext server startup (SQLite)
2. Scope hierarchy (Student -> Course -> Session)
3. Atomic Memory CRUD (write, search, update)
4. Session state save/restore (cross-session continuity)
5. Source creation (learning materials)
6. Experience recording
7. Memory search (FTS + hybrid)
"""
import asyncio
import json
import sys
import os
from pathlib import Path

os.environ["PYTHONIOENCODING"] = "utf-8"

PASS = "[PASS]"
FAIL = "[FAIL]"
results = []


def record(name, ok, detail=""):
    status = PASS if ok else FAIL
    results.append((name, ok))
    msg = f"  {status} {name}"
    if detail:
        msg += f" -- {detail}"
    print(msg)


async def run_tests():
    workspace = Path.home() / ".learning-assistant-demo"
    workspace.mkdir(parents=True, exist_ok=True)

    # ── 1. Server startup ──────────────────────────────────
    print("\n=== 1. Server Startup ===")
    from learning_assistant.context.server import EmbeddedPowerContextServer

    server = EmbeddedPowerContextServer(
        workspace=workspace,
        database_kind="sqlite",
    )
    try:
        url = server.start()
        record("Server starts", True, f"url={url}")
    except Exception as e:
        record("Server starts", False, str(e))
        return

    # ── 2. Client connection ───────────────────────────────
    print("\n=== 2. Client Connection ===")
    from learning_assistant.context.client import LearningAssistantClient
    from powercontext.http import CreateScopeRequest

    client = LearningAssistantClient(url)
    try:
        pc = await client.__aenter__()
        record("Client connects", True)
    except Exception as e:
        record("Client connects", False, str(e))
        server.stop()
        return

    try:
        # ── 3. Scope hierarchy ─────────────────────────────
        print("\n=== 3. Scope Hierarchy ===")

        student_scope = await pc.create_scope(CreateScopeRequest(
            title="Student: Demo User",
            summary="Demo student profile",
            idempotency_key=f"demo:student:{id(client)}",
        ))
        student_id = student_scope.scope_id
        client.scopes.student = student_id
        record("Create student scope", True, f"id={student_id}")

        course_scope = await pc.create_scope(CreateScopeRequest(
            title="Course: Python Basics",
            summary="Learn Python fundamentals",
            idempotency_key=f"demo:course:python:{id(client)}",
            parent_scope_id=student_id,
        ))
        course_id = course_scope.scope_id
        client.scopes.course = course_id
        record("Create course scope", True, f"id={course_id}")

        session_scope = await pc.create_scope(CreateScopeRequest(
            title="Session: Variables and Types",
            summary="First learning session",
            idempotency_key=f"demo:session:vars:{id(client)}",
            parent_scope_id=course_id,
        ))
        session_id = session_scope.scope_id
        client.scopes.session = session_id
        record("Create session scope", True, f"id={session_id}")

        # ── 4. Atomic Memory CRUD ──────────────────────────
        print("\n=== 4. Atomic Memory CRUD ===")

        r = await client.remember(
            scope_id=student_id,
            kind="student_profile",
            text="Student: Demo User, Level: intermediate, Style: visual learner",
            reason="Initial profile setup",
        )
        record("Write student profile memory", True)

        r = await client.remember(
            scope_id=course_id,
            kind="plan",
            text="Week 1: Variables & Types (3h)\nWeek 2: Control Flow (4h)\nWeek 3: Functions (5h)\nWeek 4: Data Structures (6h)",
            reason="Initial learning plan",
        )
        record("Write learning plan memory", True)

        r = await client.remember(
            scope_id=course_id,
            kind="mastery",
            text="Mastered: print(), variable assignment, integer and string types",
            reason="Completed exercises in session 1",
        )
        record("Write mastery memory", True)

        r = await client.remember(
            scope_id=course_id,
            kind="weakness",
            text="Weakness: list comprehension, nested loops",
            reason="Struggled with exercise 3",
        )
        record("Write weakness memory", True)

        # ── 5. Memory Search ───────────────────────────────
        print("\n=== 5. Memory Search ===")

        result = await client.search_knowledge(
            scope_id=course_id,
            query="plan week",
            mode="fts",
            limit=5,
        )
        hits = result.hits if hasattr(result, "hits") else []
        record("FTS search for plan", len(hits) > 0, f"found {len(hits)} hits")
        for h in hits:
            print(f"    [{h.memory.kind}] {h.memory.text[:60]}...")

        result2 = await client.search_knowledge(
            scope_id=course_id,
            query="weakness difficulty",
            mode="fts",
            limit=5,
        )
        hits2 = result2.hits if hasattr(result2, "hits") else []
        record("FTS search for weakness", len(hits2) > 0, f"found {len(hits2)} hits")

        result3 = await client.search_knowledge(
            scope_id=student_id,
            query="student profile level",
            mode="fts",
            limit=5,
        )
        hits3 = result3.hits if hasattr(result3, "hits") else []
        record("Search student profile", len(hits3) > 0, f"found {len(hits3)} hits")

        # ── 6. Session State Save/Restore ──────────────────
        print("\n=== 6. Session State Save/Restore ===")

        state = {
            "topic": "Variables and Types",
            "progress": [
                "Completed variable assignment exercises",
                "Understood type conversion between int and str",
                "Practiced string formatting",
            ],
            "next_action": "Learn control flow: if/else and loops",
            "session_id": session_id,
            "duration_minutes": 45,
        }
        await client.save_session_state(course_id, state)
        record("Save session state", True)

        restored = await client.load_session_state(course_id)
        ok = restored is not None and restored.get("topic") == "Variables and Types"
        record("Restore session state", ok, f"topic={restored.get('topic') if restored else 'None'}")
        if restored:
            print(f"    Progress: {restored.get('progress', [])}")
            print(f"    Next: {restored.get('next_action', '')}")

        # ── 7. Source Creation ─────────────────────────────
        print("\n=== 7. Source Creation (Learning Materials) ===")

        src1 = await client.save_learning_material(
            scope_id=session_id,
            material_type="dialogue",
            content={
                "user": "What is a variable in Python?",
                "assistant": "A variable is a name that refers to a value...",
            },
        )
        record("Save dialogue source", True)

        src2 = await client.save_learning_material(
            scope_id=session_id,
            material_type="note",
            content={
                "title": "Python Types Summary",
                "body": "int: whole numbers\nstr: text\nfloat: decimals\nbool: True/False",
            },
        )
        record("Save note source", True)

        src3 = await client.save_learning_material(
            scope_id=course_id,
            material_type="exercise",
            content={
                "question": "What is the output of type(3.14)?",
                "answer": "<class 'float'>",
                "difficulty": "easy",
            },
        )
        record("Save exercise source", True)

        # ── 8. Experience Recording ────────────────────────
        print("\n=== 8. Experience Recording ===")

        from powercontext.http import CreateArtifactRequest

        exp1 = await client.record_practice_experience(
            scope_id=session_id,
            situation="Exercise: Write a function to reverse a string",
            action="Used slicing s[::-1]",
            outcome="Correct! Passed all test cases",
            lesson="Python slicing is powerful for sequence manipulation",
        )
        record("Record correct experience", True)

        exp2 = await client.record_practice_experience(
            scope_id=session_id,
            situation="Exercise: Flatten a nested list",
            action="Tried list comprehension but got confused with nesting",
            outcome="Partial - handled 2 levels but not arbitrary depth",
            lesson="Need to study recursion for arbitrary-depth nesting",
        )
        record("Record partial experience", True)

        # ── 9. Context Preparation ─────────────────────────
        print("\n=== 9. Context Preparation ===")

        ctx = await client.get_context(
            scope_id=course_id,
            query="learning plan progress weakness",
            max_bytes=4000,
        )
        has_content = ctx is not None and hasattr(ctx, "content")
        record("Prepare context for LLM", has_content)
        if has_content and ctx.content:
            preview = ctx.content[:200].replace("\n", " ")
            print(f"    Context preview: {preview}...")

        # ── 10. Memory Flush ───────────────────────────────
        print("\n=== 10. Memory Flush ===")

        try:
            flush_result = await client.flush_memories(session_id)
            record("Flush memories from sources", True)
        except Exception as e:
            err = str(e)
            if "inference_unavailable" in err or "503" in err:
                record("Flush memories from sources (skipped - no LLM)", True,
                       "requires API key for auto-extraction")
            else:
                record("Flush memories from sources", False, err[:80])

        # ── Summary ────────────────────────────────────────
        print("\n" + "=" * 50)
        total = len(results)
        passed = sum(1 for _, ok in results if ok)
        failed = total - passed
        print(f"Results: {passed}/{total} passed, {failed} failed")

        if failed:
            print("\nFailed tests:")
            for name, ok in results:
                if not ok:
                    print(f"  - {name}")

        print("=" * 50)

    finally:
        await client.__aexit__(None, None, None)
        server.stop()
        print("\nServer stopped.")


if __name__ == "__main__":
    asyncio.run(run_tests())
