"""Game engine: action-based life simulation with PowerContext integration."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Optional

import httpx

from .config import Settings
from .models import (
    ACTION_MAP,
    ActionResult,
    Character,
    CharacterProfile,
    ExperienceRecord,
    GameSession,
    LifeStage,
    LIFE_STAGE_THRESHOLDS,
    MemoryRecord,
    VitalStats,
    get_available_actions,
    get_rank,
    ABILITY_LABELS,
)
from .pc_client import PowerContextClient, PowerContextError

logger = logging.getLogger(__name__)

STARTING_SCENARIOS = [
    ("一个普通的小城市家庭，父母都是工薪阶层", "小城市"),
    ("一个富裕的商人家庭，父亲经营着一家中型企业", "大城市"),
    ("一个书香门第，爷爷奶奶都是退休教师", "省会城市"),
    ("一个农村家庭，父母以种地为生", "农村"),
    ("一个艺术家庭，母亲是画家，父亲是音乐老师", "文化名城"),
    ("一个科技家庭，父母都是软件工程师", "科技新城"),
]

AGE_EVENTS: dict[int, list[str]] = {
    3: ["幼儿园入学"],
    6: ["小学入学"],
    12: ["初中入学"],
    15: ["中考"],
    18: ["高考/进入社会"],
    22: ["大学毕业"],
    25: ["事业起步期"],
    30: ["人生而立之年"],
    35: ["事业关键期"],
    40: ["不惑之年"],
    50: ["知天命之年"],
    60: ["退休"],
    70: ["古稀之年"],
    80: ["耄耋之年"],
}

SYSTEM_PROMPT = """\
你是一位人生模拟器的叙事引擎。玩家选择了一个行动，你需要生成这个行动带来的结果和故事。

## 规则
1. 用第二人称"你"叙述
2. 回复 60-150 字，简洁生动
3. 根据角色年龄和人生阶段调整语气
4. 如果提供了历史记忆，偶尔呼应过去的经历
5. 如果提供了人生教训，在合适场景体现因果
6. 结果要合理——高难度行动不一定每次都成功
7. 偶尔触发特殊事件（遇到贵人、意外机遇、突发挑战）

## 输出 JSON 格式
```json
{
  "narrative": "叙事文本（60-150字）",
  "bonus_abilities": {"ability_key": 额外变化量},
  "bonus_vitals": {"health/happiness": 额外变化量},
  "new_skill": "获得的技能名（可选，null）",
  "new_relationship": {"name": "人名", "type": "关系"},
  "life_lesson": "人生教训（可选，null）",
  "special_event": "特殊事件描述（可选，null）"
}
```

bonus_abilities 和 bonus_vitals 是在行动基础效果之上的额外变化，范围 -3 到 +3。
大多数时候应该为空 {} 或 null。只在叙事中有特别收获/损失时才填写。
"""


def _determine_life_stage(age: int) -> LifeStage:
    stage = LifeStage.CHILDHOOD
    for threshold, s in LIFE_STAGE_THRESHOLDS:
        if age >= threshold:
            stage = s
    return stage


def _clamp(value: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, value))


class GameEngine:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._pc: Optional[PowerContextClient] = None
        self._sessions: dict[str, GameSession] = {}
        self._pc_available: bool = False

    async def initialize(self):
        self._pc = PowerContextClient(self._settings.pc)
        self._pc_available = await self._pc.health_check()
        if self._pc_available:
            logger.info("Connected to PowerContext at %s", self._settings.pc.server_url)
        else:
            logger.warning("PowerContext unavailable — running in local mode")

    async def shutdown(self):
        if self._pc:
            await self._pc.close()

    @property
    def pc_available(self) -> bool:
        return self._pc_available

    # ── Session Management ──

    def _get_session(self, session_id: str) -> GameSession:
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")
        return self._sessions[session_id]

    def list_sessions(self) -> list[dict]:
        return [
            {
                "session_id": s.session_id,
                "scope_id": s.scope_id,
                "character_name": s.character.profile.name,
                "age": s.character.age,
                "life_stage": s.character.life_stage.value,
                "turn_count": s.turn_count,
                "is_active": s.is_active,
            }
            for s in self._sessions.values()
        ]

    # ── Start Game ──

    async def start_game(
        self, name: str = "", gender: str = "随机", background: str = "随机",
    ) -> GameSession:
        if not gender or gender == "随机":
            gender = random.choice(["男", "女"])
        if not name:
            name = self._random_name(gender)

        if background == "随机":
            family_bg, birth_city = random.choice(STARTING_SCENARIOS)
        else:
            family_bg, birth_city = background, "某城市"

        session = GameSession()
        session.character = Character(
            profile=CharacterProfile(
                name=name, gender=gender,
                birth_city=birth_city, family_background=family_bg,
            ),
            age=0,
            life_stage=LifeStage.CHILDHOOD,
            vitals=VitalStats(
                health=random.randint(70, 95),
                happiness=random.randint(65, 90),
                energy=100,
            ),
            abilities={k: random.randint(5, 15) for k in ABILITY_LABELS},
            occupation="幼儿",
        )

        if self._pc_available:
            try:
                scope = await self._pc.create_scope(
                    title=f"{name}的人生",
                    summary=f"{gender}，{birth_city}，{family_bg}",
                    idempotency_key=f"life-sim-{session.session_id}",
                )
                session.scope_id = scope.get("scope_id", session.session_id)
                await self._pc.remember_memory(
                    scope_id=session.scope_id, kind="birth",
                    text=f"{name}出生在{birth_city}。{family_bg}。",
                    description="出生设定",
                )
            except PowerContextError as e:
                logger.warning("PowerContext scope creation failed: %s", e)

        self._sessions[session.session_id] = session

        opening = self._generate_opening(session)
        session.memories.append(MemoryRecord(
            kind="birth", text=opening, age=0, timestamp=time.time(),
        ))
        session.action_log.append({"turn": 0, "action": "birth", "narrative": opening})

        return session

    def _generate_opening(self, session: GameSession) -> str:
        c = session.character
        return (
            f"{c.profile.name}出生在{c.profile.birth_city}。"
            f"{c.profile.family_background}。"
            f"这是一个新的人生的起点。"
        )

    # ── Perform Action ──

    async def perform_action(self, session_id: str, action_id: str) -> ActionResult:
        session = self._get_session(session_id)
        if not session.is_active:
            return ActionResult(
                action_id=action_id, action_name="游戏结束",
                narrative="这段人生已经结束。",
                is_game_over=True, game_over_text="人生已落幕。",
            )

        action = ACTION_MAP.get(action_id)
        if not action:
            return ActionResult(
                action_id=action_id, action_name="未知行动",
                narrative="这个行动不存在。",
            )

        char = session.character

        if char.vitals.energy < action.energy_cost and action.energy_cost > 0:
            return ActionResult(
                action_id=action_id, action_name=action.name,
                narrative=f"你太累了，精力不足（当前{char.vitals.energy}，需要{action.energy_cost}）。先休息一下吧。",
                energy_change=0, months_advanced=0,
            )

        session.turn_count += 1
        context_text = await self._retrieve_context(session, action)
        llm_result = await self._call_llm(session, action, context_text)

        result = self._apply_action(session, action, llm_result)

        session.action_log.append({
            "turn": session.turn_count,
            "action": action_id,
            "narrative": result.narrative,
        })
        session.messages.append({"role": "player", "content": action.name})
        session.messages.append({"role": "narrator", "content": result.narrative})

        if len(session.messages) > 40:
            session.messages = session.messages[-30:]

        if char.age >= self._settings.game.max_age or char.vitals.health <= 0:
            result.is_game_over = True
            result.game_over_text = self._generate_ending(session)
            session.is_active = False

        return result

    # ── Apply Action Results ──

    def _apply_action(self, session: GameSession, action, llm: dict) -> ActionResult:
        char = session.character
        ability_changes: dict[str, int] = {}
        vitality_changes: dict[str, int] = {}

        for eff in action.effects:
            delta = eff.amount + llm.get("bonus_abilities", {}).get(eff.ability, 0)
            old = char.abilities.get(eff.ability, 0)
            char.abilities[eff.ability] = _clamp(old + delta)
            ability_changes[eff.ability] = delta

        for vit_key, base_delta in action.vitality_changes.items():
            bonus = llm.get("bonus_vitals", {}).get(vit_key, 0)
            delta = base_delta + bonus
            old = getattr(char.vitals, vit_key, 0)
            setattr(char.vitals, vit_key, _clamp(old + delta))
            vitality_changes[vit_key] = delta

        energy_delta = -action.energy_cost
        char.vitals.energy = _clamp(char.vitals.energy + energy_delta)

        months = action.months_advance
        prev_age = char.age
        char.age += months // 12
        if char.age != prev_age:
            char.life_stage = _determine_life_stage(char.age)
            self._update_occupation(char)

        natural_decay = random.random() < 0.3
        if natural_decay:
            char.vitals.energy = _clamp(char.vitals.energy + 5)

        new_skill = llm.get("new_skill")
        if new_skill and new_skill not in char.skills:
            char.skills.append(new_skill)

        new_rel = llm.get("new_relationship")
        if new_rel and isinstance(new_rel, dict):
            existing = next((r for r in char.relationships if r.get("name") == new_rel.get("name")), None)
            if existing:
                existing["closeness"] = _clamp(existing.get("closeness", 50) + 10)
            else:
                new_rel["closeness"] = 60
                char.relationships.append(new_rel)

        lesson = llm.get("life_lesson")
        if lesson:
            session.experiences.append(ExperienceRecord(
                situation=f"{char.age}岁时{action.name}",
                action=action.name,
                outcome=llm.get("narrative", "")[:200],
                lesson=lesson,
                age=char.age,
            ))
            if self._pc_available and session.scope_id:
                asyncio.create_task(self._pc_experience_safe(
                    session.scope_id, lesson,
                    [m.id for m in session.memories[-3:]],
                ))

        mem_text = f"[{char.age}岁] {action.name}：{llm.get('narrative', '')[:100]}"
        record = MemoryRecord(kind=action.category, text=mem_text, age=char.age, timestamp=time.time())
        session.memories.append(record)

        if self._pc_available and session.scope_id:
            asyncio.create_task(self._pc_remember_safe(session.scope_id, action.category, mem_text, char.age))

        special_event = llm.get("special_event")
        age_event = AGE_EVENTS.get(char.age)
        if age_event and not special_event:
            special_event = random.choice(age_event)

        return ActionResult(
            action_id=action.id,
            action_name=action.name,
            narrative=llm.get("narrative", f"你进行了{action.name}。"),
            ability_changes=ability_changes,
            vitality_changes=vitality_changes,
            energy_change=energy_delta,
            months_advanced=months,
            new_skill=new_skill,
            new_relationship=new_rel,
            life_lesson=lesson,
            special_event=special_event,
        )

    def _update_occupation(self, char: Character):
        age = char.age
        if age < 6:
            char.occupation = "幼儿"
        elif age < 12:
            char.occupation = "小学生"
        elif age < 15:
            char.occupation = "初中生"
        elif age < 18:
            char.occupation = "高中生"
        elif age < 22:
            char.occupation = "大学生"
        elif age < 60:
            if char.abilities.get("career", 0) >= 70:
                char.occupation = "高管/专家"
            elif char.abilities.get("career", 0) >= 50:
                char.occupation = "职场人士"
            elif char.abilities.get("finance", 0) >= 70:
                char.occupation = "创业者"
            else:
                char.occupation = "工作者"
        elif age < 70:
            char.occupation = "退休"
        else:
            char.occupation = "安享晚年"

    # ── Context Retrieval ──

    async def _retrieve_context(self, session: GameSession, action) -> str:
        if not self._pc_available or not session.scope_id:
            return self._local_context(session)

        parts = []
        try:
            prepared = await self._pc.prepare_context(
                scope_id=session.scope_id,
                query=f"{action.name} {action.category} {session.character.life_stage.value}",
                max_bytes=self._settings.pc.default_max_bytes,
            )
            if prepared:
                parts.append(prepared)
        except PowerContextError:
            pass

        try:
            related = await self._pc.search_memory(
                scope_id=session.scope_id, query=action.name, limit=5,
            )
            if related:
                mem_text = "\n".join(f"- [{m.get('kind', '?')}] {m.get('text', '')}" for m in related[:5])
                parts.append(f"## 相关记忆\n{mem_text}")
        except PowerContextError:
            pass

        return "\n\n".join(parts) if parts else self._local_context(session)

    def _local_context(self, session: GameSession) -> str:
        parts = []
        recent = session.memories[-6:]
        if recent:
            mem_text = "\n".join(f"- [{m.kind}] {m.text}" for m in recent)
            parts.append(f"## 近期记忆\n{mem_text}")
        if session.experiences:
            exp = session.experiences[-2:]
            exp_text = "\n".join(f"- 教训: {e.lesson}" for e in exp)
            parts.append(f"## 人生教训\n{exp_text}")
        return "\n\n".join(parts)

    # ── LLM Call ──

    async def _call_llm(self, session: GameSession, action, context: str) -> dict:
        char = session.character
        user_prompt = (
            f"## 角色\n{char.to_narrative_summary()}\n\n"
            f"## 选择的行动\n{action.icon} {action.name}：{action.description}\n"
            f"基础效果：{', '.join(f'{ABILITY_LABELS.get(e.ability, e.ability)}+{e.amount}' for e in action.effects) or '无直接能力提升'}\n\n"
        )
        if context:
            user_prompt += f"## 历史上下文\n{context}\n\n"
        user_prompt += "请生成这次行动的结果。"

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in session.messages[-8:]:
            role = "assistant" if msg["role"] == "narrator" else msg["role"]
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": msg["content"]})
        messages.append({"role": "user", "content": user_prompt})

        llm_cfg = self._settings.llm
        try:
            async with httpx.AsyncClient(timeout=llm_cfg.timeout) as client:
                resp = await client.post(
                    f"{llm_cfg.api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {llm_cfg.api_key}", "Content-Type": "application/json"},
                    json={"model": llm_cfg.model, "messages": messages,
                          "temperature": llm_cfg.temperature, "max_tokens": llm_cfg.max_tokens},
                )
                resp.raise_for_status()
                data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return self._parse_json(content)
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return {"narrative": f"你进行了{action.name}，感觉有所收获。"}

    def _parse_json(self, raw: str) -> dict:
        try:
            text = raw.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except (json.JSONDecodeError, IndexError, KeyError):
            return {"narrative": raw[:300] if raw else "时间继续流逝..."}

    # ── Save / Load ──

    async def save_game(self, session_id: str) -> dict:
        session = self._get_session(session_id)
        if not self._pc_available or not session.scope_id:
            return {"success": False, "message": "PowerContext 不可用"}
        try:
            summary = session.character.to_narrative_summary()
            await self._pc.handoff_activate(session.scope_id, f"save-{int(time.time())}")
            draft = await self._pc.handoff_prepare(session.scope_id, f"存档：{summary}", 8000)
            prepared = await self._pc.handoff_finalize(session.scope_id, draft)
            result = await self._pc.handoff_commit(session.scope_id, prepared)
            session.last_handoff_revision = str(result.get("revision", ""))
            return {"success": True, "message": "存档成功", "handoff_revision": session.last_handoff_revision}
        except PowerContextError as e:
            return {"success": False, "message": f"存档失败: {e}"}

    async def load_game(self, scope_id: str) -> Optional[GameSession]:
        if not self._pc_available:
            return None
        try:
            await self._pc.handoff_continue(scope_id=scope_id)
            context = await self._pc.prepare_context(scope_id=scope_id, query="人生状态", max_bytes=6000)
            session = GameSession()
            session.scope_id = scope_id
            if context:
                session.messages.append({"role": "system", "content": f"[存档恢复]\n{context}"})
            self._sessions[session.session_id] = session
            return session
        except PowerContextError as e:
            logger.error("Load failed: %s", e)
            return None

    # ── Timeline ──

    async def get_memory_timeline(self, session_id: str) -> list[dict]:
        session = self._get_session(session_id)
        if self._pc_available and session.scope_id:
            try:
                entries = await self._pc.list_memory_entries(session.scope_id, limit=100)
                if entries:
                    return entries
            except PowerContextError:
                pass
        return [{"age": m.age, "kind": m.kind, "text": m.text, "id": m.id} for m in session.memories]

    async def get_experiences(self, session_id: str) -> list[dict]:
        session = self._get_session(session_id)
        return [e.model_dump() for e in session.experiences]

    # ── Ending ──

    def _generate_ending(self, session: GameSession) -> str:
        char = session.character
        top = sorted(char.abilities.items(), key=lambda x: -x[1])[:3]
        top_str = "、".join(f"{ABILITY_LABELS.get(k, k)}({get_rank(v)})" for k, v in top)
        return (
            f"{char.profile.name}在{char.age}岁时走完了这一生。"
            f"从{char.profile.birth_city}的一个{char.profile.family_background}起步，"
            f"最终成为了{char.occupation}。"
            f"一生最突出的能力是{top_str}。"
            f"回顾往事，每一步行动都塑造了这段独一无二的人生。"
        )

    # ── PC Helpers ──

    async def _pc_remember_safe(self, scope_id: str, kind: str, text: str, age: int):
        try:
            await self._pc.remember_memory(scope_id, kind, f"[{age}岁] {text}")
        except Exception as e:
            logger.warning("PC remember failed: %s", e)

    async def _pc_experience_safe(self, scope_id: str, reason: str, source_ids: list[str]):
        try:
            await self._pc.generate_experience(scope_id=scope_id, reason=reason, source_ids=source_ids)
        except Exception as e:
            logger.warning("PC experience failed: %s", e)

    # ── Utilities ──

    def _random_name(self, gender: str) -> str:
        surnames = ["李", "王", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴", "徐", "孙", "马", "朱", "胡"]
        male_names = ["伟", "强", "磊", "军", "勇", "杰", "涛", "明", "辉", "鹏", "飞", "浩", "宇", "轩"]
        female_names = ["芳", "娜", "敏", "静", "丽", "燕", "霞", "玲", "萍", "红", "婷", "雪", "琳", "颖"]
        surname = random.choice(surnames)
        pool = male_names if gender == "男" else female_names
        given = random.choice(pool)
        if random.random() > 0.5:
            given += random.choice(pool)
        return surname + given
