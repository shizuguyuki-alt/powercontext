"""Full demo run with DeepSeek API"""
import asyncio
import json
import os
import sys
from pathlib import Path

API_KEY = os.environ.get("OPENAI_API_KEY", "sk-your-api-key-here")
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"

workspace = Path.home() / ".learning-assistant-demo"
workspace.mkdir(parents=True, exist_ok=True)

GREEN = "\033[0;32m"
CYAN = "\033[0;36m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
BOLD = "\033[1m"
NC = "\033[0m"


async def run_demo():
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

    # ── Start server ──────────────────────────────────────
    print(f"\n{BOLD}{'='*55}")
    print(f"  Learning Assistant - Full Demo (DeepSeek)")
    print(f"{'='*55}{NC}\n")

    print(f"{CYAN}[1/6] Starting PowerContext server (SQLite)...{NC}")
    server = EmbeddedPowerContextServer(
        workspace=workspace,
        database_kind="sqlite",
    )
    url = server.start()
    print(f"  {GREEN}OK{NC} - Server at {url}\n")

    client = LearningAssistantClient(url)
    llm = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)

    async with client as pc:
        # ── Init student ──────────────────────────────────
        print(f"{CYAN}[2/6] Initializing student profile...{NC}")
        s = await pc.create_scope(CreateScopeRequest(
            title="Student: Demo Learner",
            summary="Intermediate Python dev learning Rust",
            idempotency_key=f"demo:run:student:{id(client)}",
        ))
        student_id = s.scope_id
        client.scopes.student = student_id

        await client.remember(
            student_id, "student_profile",
            "Student: Demo Learner, Level: intermediate, Style: visual learner, "
            "Background: Python developer with basic C knowledge, wants to learn Rust",
            reason="Initial profile setup",
        )
        print(f"  {GREEN}OK{NC} - Student Scope: {YELLOW}{student_id}{NC}\n")

        # ── Generate plan ─────────────────────────────────
        print(f"{CYAN}[3/6] Generating learning plan (DeepSeek LLM)...{NC}")
        print(f"  Course: Rust Programming | Duration: 4 weeks")
        print(f"  Calling DeepSeek API...\n")

        plan_svc = PlanService(client, PlanLLM(llm, model=MODEL))
        try:
            plan = await plan_svc.create_plan(
                course_name="Rust Programming",
                goal="Master Rust basics, ownership, and lifetimes",
                total_weeks=4,
                student_background="Python developer, basic C knowledge",
            )
            course_id = client.scopes.course
            print(f"  {GREEN}Plan generated successfully!{NC}")
            print(f"  Course Scope: {YELLOW}{course_id}{NC}\n")
            print(f"  {BOLD}--- Learning Plan ---{NC}")
            print(f"  {plan.summary()}\n")
        except Exception as e:
            print(f"  {YELLOW}LLM call failed: {e}{NC}")
            print(f"  Creating fallback plan...\n")
            c = await pc.create_scope(CreateScopeRequest(
                title="Course: Rust Programming",
                summary="Learn Rust basics",
                idempotency_key=f"demo:run:course:{id(client)}",
                parent_scope_id=student_id,
            ))
            course_id = c.scope_id
            client.scopes.course = course_id
            await client.remember(
                course_id, "plan",
                "Week 1: Syntax basics (variables, types, functions)\n"
                "Week 2: Ownership & borrowing\n"
                "Week 3: Structs, enums, pattern matching\n"
                "Week 4: Error handling & projects",
                reason="Fallback plan",
            )
            await client.remember(
                course_id, "learning_goal",
                "Goal: Master Rust basics. Duration: 4 weeks",
                reason="Course goal",
            )
            print(f"  {GREEN}Fallback plan created{NC}")
            print(f"  Course Scope: {YELLOW}{course_id}{NC}\n")

        # ── Study session ─────────────────────────────────
        print(f"{CYAN}[4/6] Starting interactive study session...{NC}")
        print(f"  Topic: Variables and Types in Rust\n")

        session_svc = SessionService(client, TutorLLM(llm, model=MODEL))
        try:
            session = await session_svc.start_session(
                course_scope_id=course_id,
                topic="Variables and Types in Rust",
            )
            print(f"  Session Scope: {YELLOW}{session.session_id}{NC}\n")

            questions = [
                "What are variables in Rust? How are they different from Python?",
                "Can you show me an example of type annotation in Rust?",
            ]

            for q in questions:
                print(f"  {BLUE}Student > {NC}{q}")
                response = await session_svc.chat(q)
                display = response[:300] + "..." if len(response) > 300 else response
                print(f"  {GREEN}Tutor   > {NC}{display}\n")

            print(f"  {CYAN}Recording practice exercise...{NC}")
            await session_svc.record_exercise(
                situation="Exercise: Declare a mutable variable and change its value",
                action="Used 'let mut x = 5; x = 10;'",
                outcome="Correct! Passed all test cases",
                lesson="Rust requires explicit 'mut' keyword for mutable variables, unlike Python where all variables are mutable by default",
            )
            print(f"  {GREEN}OK{NC} - Experience recorded\n")

            print(f"  {CYAN}Ending session and saving progress...{NC}")
            await session_svc.end_session(
                progress_summary=[
                    "Learned Rust variable declarations (let / let mut)",
                    "Understood type annotations and type inference",
                    "Practiced immutability concepts with exercises",
                ],
                next_action="Learn about Rust data types: integers, floats, booleans, chars",
            )
            print(f"  {GREEN}OK{NC} - Session saved\n")

        except Exception as e:
            print(f"  {YELLOW}Session LLM failed: {e}{NC}")
            print(f"  Creating fallback session...\n")
            ss = await pc.create_scope(CreateScopeRequest(
                title="Session: Variables and Types",
                summary="First study session",
                idempotency_key=f"demo:run:session:{id(client)}",
                parent_scope_id=course_id,
            ))
            session_id = ss.scope_id
            await client.remember(
                course_id, "session_state",
                json.dumps({
                    "topic": "Variables and Types in Rust",
                    "progress": [
                        "Learned let/let mut",
                        "Understood type annotations",
                    ],
                    "next_action": "Learn data types: int, float, bool, char",
                }, ensure_ascii=False),
                reason="Fallback session state",
            )
            await client.record_practice_experience(
                session_id,
                "Declare mutable var", "Used let mut x = 5",
                "Correct", "mut keyword needed in Rust",
            )
            print(f"  {GREEN}Fallback session saved{NC}")
            print(f"  Session: {YELLOW}{session_id}{NC}\n")

        # ── Progress report ───────────────────────────────
        print(f"{CYAN}[5/6] Generating progress report (DeepSeek LLM)...{NC}\n")

        prog_svc = ProgressService(client, AnalyzerLLM(llm, model=MODEL))
        try:
            report = await prog_svc.generate_report(course_id, "Rust Programming")
            print(f"  {BOLD}--- Progress Report ---{NC}")
            print(f"  {report.summary()}\n")
        except Exception as e:
            print(f"  {YELLOW}Report LLM failed: {e}{NC}")
            print(f"  Showing raw memory data:\n")
            plan_r = await client.search_knowledge(course_id, "plan", mode="fts", limit=3)
            for h in plan_r.hits:
                print(f"    [{h.memory.kind}] {h.memory.text[:120]}")
            state = await client.load_session_state(course_id)
            if state:
                print(f"\n  Last session topic: {state.get('topic', '?')}")
                print(f"  Next action: {state.get('next_action', '?')}")
            print()

        # ── Adaptive strategy ─────────────────────────────
        print(f"{CYAN}[6/6] Adaptive strategy engine...{NC}\n")

        adaptive_svc = AdaptiveService(client, AnalyzerLLM(llm, model=MODEL))
        await adaptive_svc.load_state(course_id)

        await adaptive_svc.update_after_exercise(course_id, "correct", "variable declaration")
        await adaptive_svc.update_after_exercise(course_id, "incorrect", "ownership concept")
        await adaptive_svc.update_after_exercise(course_id, "correct", "type annotation")
        await adaptive_svc.update_after_exercise(course_id, "incorrect", "borrowing rules")

        strategy = await adaptive_svc.get_teaching_strategy(course_id, "ownership")
        print(f"  {BOLD}--- Teaching Strategy ---{NC}")
        print(f"  Difficulty: {YELLOW}{strategy['difficulty']}{NC}")
        print(f"  Style: {strategy['style']}")
        print(f"  Focus areas: {', '.join(strategy['focus_areas']) or 'none'}")
        print(f"  Review due: {'Yes' if strategy['review_due'] else 'No'}")
        print(f"  Review interval: {strategy['review_interval_days']} days")

        # ── Memory inventory ──────────────────────────────
        print(f"\n{BOLD}{'='*55}")
        print(f"  Memory Inventory (all stored data)")
        print(f"{'='*55}{NC}")

        for name, sid in [("Student", student_id), ("Course", course_id)]:
            r = await client.search_knowledge(sid, "learning plan progress mastery weakness session", mode="fts", limit=20)
            print(f"\n  {BOLD}{name}{NC} ({sid}):")
            if r.hits:
                for h in r.hits:
                    t = h.memory.text[:80].replace("\n", " ")
                    print(f"    [{h.memory.kind}] {t}...")
            else:
                print(f"    (no memories)")

    server.stop()
    print(f"\n{GREEN}{'='*55}")
    print(f"  Demo complete! Server stopped.")
    print(f"{'='*55}{NC}\n")


if __name__ == "__main__":
    asyncio.run(run_demo())
