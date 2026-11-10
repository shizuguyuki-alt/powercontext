"""Data models for AI Life Simulator — action-based edition."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Life Stage ──

class LifeStage(str, Enum):
    CHILDHOOD = "childhood"
    TEENAGE = "teenage"
    YOUNG_ADULT = "young_adult"
    ADULT = "adult"
    MIDDLE_AGE = "middle_age"
    RETIREMENT = "retirement"


LIFE_STAGE_THRESHOLDS = [
    (0, LifeStage.CHILDHOOD),
    (13, LifeStage.TEENAGE),
    (18, LifeStage.YOUNG_ADULT),
    (30, LifeStage.ADULT),
    (50, LifeStage.MIDDLE_AGE),
    (65, LifeStage.RETIREMENT),
]

STAGE_LABELS = {
    LifeStage.CHILDHOOD: "童年",
    LifeStage.TEENAGE: "青少年",
    LifeStage.YOUNG_ADULT: "青年",
    LifeStage.ADULT: "壮年",
    LifeStage.MIDDLE_AGE: "中年",
    LifeStage.RETIREMENT: "老年",
}


# ── Ability / Rank ──

ABILITY_KEYS = [
    "strength", "agility", "endurance",
    "logic", "creativity", "knowledge",
    "charisma", "empathy",
    "finance", "career",
]

ABILITY_LABELS = {
    "strength": "力量", "agility": "敏捷", "endurance": "耐力",
    "logic": "逻辑", "creativity": "创造力", "knowledge": "知识",
    "charisma": "魅力", "empathy": "共情",
    "finance": "财力", "career": "事业",
}

ABILITY_CATEGORIES = {
    "body": ["strength", "agility", "endurance"],
    "mind": ["logic", "creativity", "knowledge"],
    "social": ["charisma", "empathy"],
    "life": ["finance", "career"],
}

CATEGORY_LABELS = {
    "body": "体能", "mind": "智力", "social": "社交", "life": "生活",
}


def get_rank(value: int) -> str:
    if value >= 90: return "S"
    if value >= 75: return "A"
    if value >= 60: return "B"
    if value >= 40: return "C"
    if value >= 20: return "D"
    return "F"


RANK_COLORS = {
    "S": "#f59e0b", "A": "#22c55e", "B": "#3b82f6",
    "C": "#a855f7", "D": "#9ca3af", "F": "#6b7280",
}


# ── Vital Stats ──

class VitalStats(BaseModel):
    health: int = Field(default=80, ge=0, le=100)
    happiness: int = Field(default=70, ge=0, le=100)
    energy: int = Field(default=100, ge=0, le=100)


# ── Action Definition ──

class ActionEffect(BaseModel):
    ability: str
    amount: int


class ActionDef(BaseModel):
    id: str
    name: str
    icon: str
    description: str
    category: str
    effects: list[ActionEffect]
    vitality_changes: dict[str, int] = Field(default_factory=dict)
    energy_cost: int = 15
    months_advance: int = 2
    min_age: int = 0
    max_age: int = 100
    min_ability: Optional[str] = None
    min_ability_level: int = 0
    tags: list[str] = Field(default_factory=list)


# ── Character ──

class CharacterProfile(BaseModel):
    name: str = ""
    gender: str = ""
    birth_city: str = ""
    family_background: str = ""


class Character(BaseModel):
    profile: CharacterProfile = Field(default_factory=CharacterProfile)
    age: int = 0
    life_stage: LifeStage = LifeStage.CHILDHOOD
    vitals: VitalStats = Field(default_factory=VitalStats)
    abilities: dict[str, int] = Field(default_factory=lambda: {k: 10 for k in ABILITY_KEYS})
    skills: list[str] = Field(default_factory=list)
    relationships: list[dict] = Field(default_factory=list)
    occupation: str = "学生"

    def to_narrative_summary(self) -> str:
        abils = ", ".join(
            f"{ABILITY_LABELS.get(k, k)}{v}({get_rank(v)})"
            for k, v in self.abilities.items()
        )
        return (
            f"{self.profile.name}，{self.age}岁，{STAGE_LABELS.get(self.life_stage, '')}，{self.occupation}。"
            f"出生于{self.profile.birth_city}，{self.profile.family_background}。"
            f"健康:{self.vitals.health} 幸福:{self.vitals.happiness} 精力:{self.vitals.energy}。"
            f"能力: {abils}。"
        )


# ── Action Catalog ──

def _build_actions() -> list[ActionDef]:
    return [
        ActionDef(id="study", name="学习", icon="📚", description="读书学习，提升知识",
                  category="mind", effects=[ActionEffect(ability="knowledge", amount=3)],
                  vitality_changes={"happiness": -2}, energy_cost=15, months_advance=2, tags=["basic"]),
        ActionDef(id="exercise", name="锻炼", icon="🏃", description="跑步健身，提升力量和耐力",
                  category="body", effects=[
                      ActionEffect(ability="strength", amount=2),
                      ActionEffect(ability="endurance", amount=2),
                  ], vitality_changes={"health": 3, "happiness": 1}, energy_cost=20, months_advance=1, tags=["basic"]),
        ActionDef(id="read", name="阅读", icon="📖", description="广泛阅读，提升知识和逻辑",
                  category="mind", effects=[
                      ActionEffect(ability="knowledge", amount=2),
                      ActionEffect(ability="logic", amount=1),
                  ], vitality_changes={"happiness": 1}, energy_cost=10, months_advance=2, tags=["basic"]),
        ActionDef(id="socialize", name="社交", icon="🗣️", description="参加聚会，提升魅力和共情",
                  category="social", effects=[
                      ActionEffect(ability="charisma", amount=2),
                      ActionEffect(ability="empathy", amount=1),
                  ], vitality_changes={"happiness": 2}, energy_cost=15, months_advance=1, tags=["basic"]),
        ActionDef(id="work", name="打工", icon="💼", description="兼职工作，提升事业和财力",
                  category="life", effects=[
                      ActionEffect(ability="career", amount=2),
                      ActionEffect(ability="finance", amount=2),
                  ], vitality_changes={"happiness": -3, "energy": -5}, energy_cost=25, months_advance=3,
                  min_age=16, tags=["basic"]),
        ActionDef(id="create_art", name="艺术创作", icon="🎨", description="绘画、音乐等创作，提升创造力",
                  category="mind", effects=[ActionEffect(ability="creativity", amount=3)],
                  vitality_changes={"happiness": 3}, energy_cost=15, months_advance=2, tags=["basic"]),
        ActionDef(id="meditate", name="冥想", icon="🧘", description="静坐冥想，恢复精力提升共情",
                  category="social", effects=[ActionEffect(ability="empathy", amount=1)],
                  vitality_changes={"happiness": 2, "energy": 15}, energy_cost=-15, months_advance=1, tags=["basic"]),
        ActionDef(id="rest", name="休息", icon="😴", description="好好休息，恢复精力和健康",
                  category="body", effects=[],
                  vitality_changes={"health": 2}, energy_cost=-30, months_advance=1, tags=["basic"]),
        ActionDef(id="entertainment", name="娱乐", icon="🎮", description="看电影、玩游戏，提升幸福",
                  category="social", effects=[],
                  vitality_changes={"happiness": 5, "energy": 10}, energy_cost=-10, months_advance=1, tags=["basic"]),
        ActionDef(id="learn_skill", name="学技能", icon="🔧", description="学习新技能，提升逻辑和创造力",
                  category="mind", effects=[
                      ActionEffect(ability="logic", amount=2),
                      ActionEffect(ability="creativity", amount=1),
                  ], vitality_changes={"happiness": -1}, energy_cost=20, months_advance=3, tags=["basic"]),
        ActionDef(id="volunteer", name="做志愿", icon="❤️", description="帮助他人，提升共情和魅力",
                  category="social", effects=[
                      ActionEffect(ability="empathy", amount=3),
                      ActionEffect(ability="charisma", amount=1),
                  ], vitality_changes={"happiness": 3}, energy_cost=20, months_advance=2,
                  min_age=10, tags=["basic"]),
        ActionDef(id="compete", name="竞技比赛", icon="🏆", description="参加体育竞赛，全面提升体能",
                  category="body", effects=[
                      ActionEffect(ability="strength", amount=1),
                      ActionEffect(ability="agility", amount=2),
                      ActionEffect(ability="endurance", amount=2),
                  ], vitality_changes={"health": 2, "happiness": 3}, energy_cost=30, months_advance=2,
                  min_age=8, tags=["basic"]),
        ActionDef(id="travel", name="旅行", icon="✈️", description="外出旅行，开阔视野",
                  category="mind", effects=[
                      ActionEffect(ability="knowledge", amount=1),
                      ActionEffect(ability="creativity", amount=1),
                  ], vitality_changes={"happiness": 5, "finance": -3}, energy_cost=10, months_advance=2,
                  min_age=18, tags=["basic"]),
        ActionDef(id="invest", name="投资理财", icon="📈", description="研究投资，提升财力",
                  category="life", effects=[ActionEffect(ability="finance", amount=4)],
                  vitality_changes={"happiness": -1}, energy_cost=15, months_advance=3,
                  min_age=20, min_ability="finance", min_ability_level=30, tags=["advanced"]),
        ActionDef(id="research", name="深入研究", icon="🔬", description="专注研究课题，大幅提升知识",
                  category="mind", effects=[
                      ActionEffect(ability="knowledge", amount=5),
                      ActionEffect(ability="logic", amount=2),
                  ], vitality_changes={"happiness": -3}, energy_cost=30, months_advance=4,
                  min_age=18, min_ability="knowledge", min_ability_level=40, tags=["advanced"]),
        ActionDef(id="lead", name="领导项目", icon="👔", description="带领团队，提升事业和魅力",
                  category="life", effects=[
                      ActionEffect(ability="career", amount=4),
                      ActionEffect(ability="charisma", amount=2),
                  ], vitality_changes={"happiness": -2}, energy_cost=30, months_advance=4,
                  min_age=22, min_ability="career", min_ability_level=30, tags=["advanced"]),
        ActionDef(id="perform", name="表演展示", icon="🎭", description="公开表演，提升魅力和创造力",
                  category="social", effects=[
                      ActionEffect(ability="charisma", amount=4),
                      ActionEffect(ability="creativity", amount=2),
                  ], vitality_changes={"happiness": 3}, energy_cost=25, months_advance=2,
                  min_age=10, min_ability="creativity", min_ability_level=30, tags=["advanced"]),
        ActionDef(id="adventure", name="冒险探索", icon="🗺️", description="户外探险，提升敏捷和耐力",
                  category="body", effects=[
                      ActionEffect(ability="agility", amount=3),
                      ActionEffect(ability="endurance", amount=3),
                  ], vitality_changes={"health": 3, "happiness": 4}, energy_cost=35, months_advance=2,
                  min_age=12, tags=["basic"]),
    ]


ACTION_CATALOG: list[ActionDef] = _build_actions()
ACTION_MAP: dict[str, ActionDef] = {a.id: a for a in ACTION_CATALOG}


def get_available_actions(character: Character) -> list[ActionDef]:
    available = []
    for action in ACTION_CATALOG:
        if character.age < action.min_age or character.age > action.max_age:
            continue
        if action.min_ability:
            if character.abilities.get(action.min_ability, 0) < action.min_ability_level:
                continue
        available.append(action)
    return available


# ── Game Response ──

class ActionResult(BaseModel):
    action_id: str
    action_name: str
    narrative: str
    ability_changes: dict[str, int] = Field(default_factory=dict)
    vitality_changes: dict[str, int] = Field(default_factory=dict)
    energy_change: int = 0
    months_advanced: int = 0
    new_skill: Optional[str] = None
    new_relationship: Optional[dict] = None
    life_lesson: Optional[str] = None
    special_event: Optional[str] = None
    is_game_over: bool = False
    game_over_text: Optional[str] = None


class MemoryRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    kind: str
    text: str
    age: int = 0
    timestamp: float = 0.0


class ExperienceRecord(BaseModel):
    situation: str
    action: str
    outcome: str
    lesson: str
    age: int = 0


class GameSession(BaseModel):
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    scope_id: Optional[str] = None
    character: Character = Field(default_factory=Character)
    memories: list[MemoryRecord] = Field(default_factory=list)
    experiences: list[ExperienceRecord] = Field(default_factory=list)
    messages: list[dict] = Field(default_factory=list)
    action_log: list[dict] = Field(default_factory=list)
    turn_count: int = 0
    is_active: bool = True
    last_handoff_revision: Optional[str] = None


# ── API Request/Response ──

class StartGameRequest(BaseModel):
    name: str = ""
    gender: str = "随机"
    background: str = "随机"


class PerformActionRequest(BaseModel):
    action_id: str


class GameStatusResponse(BaseModel):
    session_id: str
    scope_id: Optional[str]
    character: dict
    available_actions: list[dict]
    turn_count: int
    is_active: bool
    last_action_result: Optional[dict] = None
