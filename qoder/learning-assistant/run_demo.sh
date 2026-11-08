#!/bin/bash
# ============================================================
#  Learning Assistant - 一键运行脚本
#  基于 PowerContext + seekdb/SQLite 的自适应学习助手
# ============================================================
#
#  使用方法:
#    1. 填入下面的 API_KEY 和 BASE_URL
#    2. 运行: bash run_demo.sh
#
# ============================================================

# ── 配置区 (请填入你的 API 信息) ─────────────────────────────
API_KEY="${OPENAI_API_KEY:-sk-请替换为你的key}"
BASE_URL="${OPENAI_BASE_URL:-https://api.openai.com/v1}"

# ── 项目路径 ─────────────────────────────────────────────────
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR" || exit 1

# ── 颜色 ─────────────────────────────────────────────────────
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  Learning Assistant - Demo Run${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""
echo -e "  API Base URL: ${YELLOW}${BASE_URL}${NC}"
echo -e "  API Key:      ${YELLOW}${API_KEY:0:8}...${NC}"
echo ""

# ── 检查 Python 依赖 ─────────────────────────────────────────
echo -e "${GREEN}[1/6] 检查依赖...${NC}"
python -c "import powercontext" 2>/dev/null || {
    echo -e "${RED}错误: powercontext 未安装${NC}"
    echo "请运行: pip install \"powercontext[server,client] @ git+https://github.com/oceanbase/powercontext.git@master\""
    exit 1
}
python -c "import learning_assistant" 2>/dev/null || {
    echo -e "${RED}错误: learning_assistant 未安装${NC}"
    echo "请运行: cd $PROJECT_DIR && pip install -e ."
    exit 1
}
python -c "import openai" 2>/dev/null || {
    echo -e "${RED}错误: openai 未安装${NC}"
    echo "请运行: pip install openai"
    exit 1
}
echo -e "  ${GREEN}OK${NC} - 所有依赖已安装"
echo ""

# ── 清理旧数据 ───────────────────────────────────────────────
echo -e "${GREEN}[2/6] 准备工作目录...${NC}"
WORKSPACE="$HOME/.learning-assistant-demo"
rm -rf "$WORKSPACE"
mkdir -p "$WORKSPACE"
echo -e "  工作目录: ${YELLOW}$WORKSPACE${NC}"
echo ""

# ── 运行完整 Demo ────────────────────────────────────────────
echo -e "${GREEN}[3/6] 运行完整 Demo 流程...${NC}"
echo ""

PYTHONIOENCODING=utf-8 python - "$API_KEY" "$BASE_URL" "$WORKSPACE" <<'PYTHON_SCRIPT'
"""
Full demo: init -> create plan -> study session -> progress report
"""
import asyncio
import sys
import json
from pathlib import Path

api_key = sys.argv[1]
base_url = sys.argv[2]
workspace = Path(sys.argv[3])

GREEN = "\033[0;32m"
CYAN = "\033[0;36m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
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

    # ── Start server ──
    print(f"  {CYAN}Starting PowerContext server (SQLite)...{NC}")
    server = EmbeddedPowerContextServer(
        workspace=workspace,
        database_kind="sqlite",
        generation_model="gpt-4o-mini",
        generation_base_url=base_url,
        generation_api_key=api_key,
        embedding_model="text-embedding-3-small",
        embedding_base_url=base_url,
        embedding_api_key=api_key,
    )
    url = server.start()
    print(f"  {GREEN}OK{NC} - Server running at {url}\n")

    client = LearningAssistantClient(url)
    llm = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async with client as pc:
        # ══════════════════════════════════════════════════════
        # Step 1: Init student
        # ══════════════════════════════════════════════════════
        print(f"  {CYAN}{'='*50}{NC}")
        print(f"  {CYAN}  Step 1: Initialize Student Profile{NC}")
        print(f"  {CYAN}{'='*50}{NC}\n")

        student_scope = await pc.create_scope(CreateScopeRequest(
            title="Student: Demo Learner",
            summary="Demo student - intermediate level, prefers visual learning",
            idempotency_key=f"demo:student:full:{id(client)}",
        ))
        student_id = student_scope.scope_id
        client.scopes.student = student_id

        await client.remember(
            scope_id=student_id,
            kind="student_profile",
            text="Student: Demo Learner, Level: intermediate, Style: visual learner, Background: knows Python basics, wants to learn Rust",
            reason="Initial profile",
        )
        print(f"  Student Scope: {YELLOW}{student_id}{NC}")
        print(f"  Profile: intermediate level, visual learner\n")

        # ══════════════════════════════════════════════════════
        # Step 2: Create learning plan
        # ══════════════════════════════════════════════════════
        print(f"  {CYAN}{'='*50}{NC}")
        print(f"  {CYAN}  Step 2: Generate Learning Plan (LLM){NC}")
        print(f"  {CYAN}{'='*50}{NC}\n")

        plan_service = PlanService(client, PlanLLM(llm))

        print(f"  Generating plan for: {YELLOW}Rust Programming{NC}")
        print(f"  Goal: Master Rust basics and ownership system")
        print(f"  Duration: 4 weeks\n")

        try:
            plan = await plan_service.create_plan(
                course_name="Rust Programming",
                goal="Master Rust basics, ownership, and lifetimes",
                total_weeks=4,
                student_background="Intermediate Python developer, basic C knowledge",
            )
            course_id = client.scopes.course
            print(f"  {GREEN}Plan generated!{NC}")
            print(f"  Course Scope: {YELLOW}{course_id}{NC}\n")
            print(f"  {plan.summary()}\n")
        except Exception as e:
            print(f"  {YELLOW}LLM plan generation failed ({e}), using fallback plan{NC}\n")
            course_scope = await pc.create_scope(CreateScopeRequest(
                title="Course: Rust Programming",
                summary="Learn Rust basics and ownership",
                idempotency_key=f"demo:course:rust:{id(client)}",
                parent_scope_id=student_id,
            ))
            course_id = course_scope.scope_id
            client.scopes.course = course_id

            await client.remember(
                scope_id=course_id,
                kind="plan",
                text="Week 1: Syntax basics (variables, types, functions)\nWeek 2: Ownership & borrowing\nWeek 3: Structs, enums, pattern matching\nWeek 4: Error handling & projects",
                reason="Fallback plan",
            )
            await client.remember(
                scope_id=course_id,
                kind="learning_goal",
                text="Goal: Master Rust basics, ownership, and lifetimes. Duration: 4 weeks",
                reason="Course goal",
            )
            print(f"  Course Scope: {YELLOW}{course_id}{NC}\n")

        # ══════════════════════════════════════════════════════
        # Step 3: Start study session
        # ══════════════════════════════════════════════════════
        print(f"  {CYAN}{'='*50}{NC}")
        print(f"  {CYAN}  Step 3: Interactive Study Session (LLM){NC}")
        print(f"  {CYAN}{'='*50}{NC}\n")

        session_service = SessionService(client, TutorLLM(llm))

        print(f"  Starting session: {YELLOW}Variables and Types in Rust{NC}\n")

        try:
            session = await session_service.start_session(
                course_scope_id=course_id,
                topic="Variables and Types in Rust",
            )
            print(f"  Session Scope: {YELLOW}{session.session_id}{NC}")

            # Simulate a conversation
            questions = [
                "What are variables in Rust? Are they different from Python?",
                "Can you give me an example of type annotation in Rust?",
                "What does 'immutable by default' mean in practice?",
            ]

            for q in questions:
                print(f"\n  {BLUE}Student > {NC}{q}")
                response = await session_service.chat(q)
                # Truncate long responses for display
                display = response[:200] + "..." if len(response) > 200 else response
                print(f"  {GREEN}Tutor   > {NC}{display}")

            # Record a practice experience
            print(f"\n  Recording practice experience...")
            await session_service.record_exercise(
                situation="Exercise: Declare a mutable variable and change its value",
                action="Used 'let mut x = 5; x = 10;'",
                outcome="Correct! Understood mut keyword",
                lesson="Rust requires explicit 'mut' for mutable variables, unlike Python",
            )
            print(f"  {GREEN}OK{NC} - Experience recorded")

            # End session
            await session_service.end_session(
                progress_summary=[
                    "Learned Rust variable declarations (let/let mut)",
                    "Understood type annotations and type inference",
                    "Practiced immutability concepts",
                ],
                next_action="Learn about Rust data types: integers, floats, booleans, chars",
            )
            print(f"  {GREEN}OK{NC} - Session saved\n")

        except Exception as e:
            print(f"  {YELLOW}LLM session failed ({e}), simulating with direct Memory writes{NC}\n")

            session_scope = await pc.create_scope(CreateScopeRequest(
                title="Session: Variables and Types",
                summary="First study session",
                idempotency_key=f"demo:session:vars:{id(client)}",
                parent_scope_id=course_id,
            ))
            session_id = session_scope.scope_id

            await client.remember(
                scope_id=course_id,
                kind="session_state",
                text=json.dumps({
                    "topic": "Variables and Types in Rust",
                    "progress": [
                        "Learned Rust variable declarations (let/let mut)",
                        "Understood type annotations",
                        "Practiced immutability concepts",
                    ],
                    "next_action": "Learn about Rust data types",
                }, ensure_ascii=False),
                reason="Session end state",
            )

            await client.record_practice_experience(
                scope_id=session_id,
                situation="Exercise: Declare a mutable variable",
                action="Used let mut x = 5",
                outcome="Correct",
                lesson="Rust requires explicit mut for mutable variables",
            )
            print(f"  Session Scope: {YELLOW}{session_id}{NC}")
            print(f"  {GREEN}OK{NC} - Session state saved (fallback)\n")

        # ══════════════════════════════════════════════════════
        # Step 4: Check progress
        # ══════════════════════════════════════════════════════
        print(f"  {CYAN}{'='*50}{NC}")
        print(f"  {CYAN}  Step 4: Progress Report (LLM){NC}")
        print(f"  {CYAN}{'='*50}{NC}\n")

        progress_service = ProgressService(client, AnalyzerLLM(llm))

        try:
            report = await progress_service.generate_report(
                course_scope_id=course_id,
                course_name="Rust Programming",
            )
            print(f"  {report.summary()}\n")
        except Exception as e:
            print(f"  {YELLOW}LLM analysis failed ({e}), showing raw memory data{NC}\n")

            plan_result = await client.search_knowledge(
                scope_id=course_id, query="plan", mode="fts", limit=3,
            )
            print(f"  Learning Plan:")
            for h in plan_result.hits:
                print(f"    {h.memory.text[:100]}")

            state = await client.load_session_state(course_id)
            if state:
                print(f"\n  Last Session:")
                print(f"    Topic: {state.get('topic', '?')}")
                print(f"    Progress: {state.get('progress', [])}")
                print(f"    Next: {state.get('next_action', '?')}")
            print()

        # ══════════════════════════════════════════════════════
        # Step 5: Adaptive strategy
        # ══════════════════════════════════════════════════════
        print(f"  {CYAN}{'='*50}{NC}")
        print(f"  {CYAN}  Step 5: Adaptive Strategy{NC}")
        print(f"  {CYAN}{'='*50}{NC}\n")

        adaptive_service = AdaptiveService(client, AnalyzerLLM(llm))
        await adaptive_service.load_state(course_id)

        # Simulate exercise results to trigger adaptation
        await adaptive_service.update_after_exercise(course_id, "correct", "variable declaration")
        await adaptive_service.update_after_exercise(course_id, "incorrect", "ownership concept")
        await adaptive_service.update_after_exercise(course_id, "correct", "type annotation")

        strategy = await adaptive_service.get_teaching_strategy(course_id, "ownership")
        print(f"  Current Strategy:")
        print(f"    Difficulty: {YELLOW}{strategy['difficulty']}{NC}")
        print(f"    Style: {strategy['style']}")
        print(f"    Focus Areas: {', '.join(strategy['focus_areas']) or 'none'}")
        print(f"    Review Due: {'Yes' if strategy['review_due'] else 'No'}")
        print()

        # Show all stored memories
        print(f"  {CYAN}{'='*50}{NC}")
        print(f"  {CYAN}  Memory Inventory{NC}")
        print(f"  {CYAN}{'='*50}{NC}\n")

        for scope_name, scope_id_val in [("Student", student_id), ("Course", course_id)]:
            result = await client.search_knowledge(
                scope_id=scope_id_val, query="", mode="fts", limit=20,
            )
            print(f"  {scope_name} Scope ({scope_id_val}):")
            if result.hits:
                for h in result.hits:
                    text_preview = h.memory.text[:80].replace("\n", " ")
                    print(f"    [{h.memory.kind}] {text_preview}...")
            else:
                print(f"    (no memories)")
            print()

    server.stop()
    print(f"  {GREEN}Demo complete! Server stopped.{NC}")


asyncio.run(run_demo())
PYTHON_SCRIPT

DEMO_EXIT=$?

echo ""
if [ $DEMO_EXIT -eq 0 ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Demo completed successfully!${NC}"
    echo -e "${GREEN}========================================${NC}"
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}  Demo failed (exit code: $DEMO_EXIT)${NC}"
    echo -e "${RED}========================================${NC}"
fi
echo ""

# ── 清理 ─────────────────────────────────────────────────────
echo -n "Clean up demo data? [y/N] "
read -r answer
if [[ "$answer" =~ ^[Yy]$ ]]; then
    rm -rf "$WORKSPACE"
    echo "Cleaned up."
fi
echo ""
