# AI 人生模拟器 — 行动驱动的人生沙盒

> 基于 [PowerContext](https://github.com/oceanbase/powercontext) + [seekdb](https://github.com/oceanbase/seekdb) + [Dify](https://dify.ai) 构建的行动驱动人生模拟游戏。
>
> 每一次行动，都塑造一段不同的人生。10 项能力从 F 到 S 阶，18 种行动自由组合，AI 记住你的每一步经历。

---

## 目录

- [项目特色](#项目特色)
- [玩法系统](#玩法系统)
- [系统架构](#系统架构)
- [快速开始](#快速开始)
- [PowerContext 集成说明](#powercontext-集成说明)
- [API 文档](#api-文档)
- [项目结构](#项目结构)
- [配置参考](#配置参考)
- [常见问题](#常见问题)

---

## 项目特色

| 特性 | 技术支撑 | 游戏体验 |
|---|---|---|
| 行动驱动 | 18 种行动 × 10 项能力（F~S 阶） | 不做选择题，用行动塑造人生 |
| 长期记忆 | PowerContext Atomic Memory + seekdb 全文检索 | AI 记住你的每一次行动，在叙事中呼应 |
| 人生教训 | PowerContext Experience (situation→action→outcome→lesson) | 吃过的亏变成智慧，影响未来走向 |
| 存档/读档 | PowerContext Handoff (prepare→finalize→commit→continue) | 随时暂停人生，下次无缝接续 |
| 上下文控制 | PowerContext PreparedContext (byte budget) | 在 token 预算内精准召回最相关的人生记忆 |
| Scope 隔离 | PowerContext Scope | 每个玩家每次人生完全独立 |

---

## 玩法系统

### 能力维度（10 项，F~S 阶）

| 类别 | 能力 | 说明 |
|---|---|---|
| 体能 | 力量 / 敏捷 / 耐力 | 身体素质 |
| 智力 | 逻辑 / 创造力 / 知识 | 思维水平 |
| 社交 | 魅力 / 共情 | 人际交往 |
| 生活 | 财力 / 事业 | 社会资源 |

等阶划分：

| 等阶 | 数值范围 | 颜色 |
|---|---|---|
| F | 0-19 | 灰色 |
| D | 20-39 | 灰白 |
| C | 40-59 | 紫色 |
| B | 60-74 | 蓝色 |
| A | 75-89 | 绿色 |
| S | 90-100 | 金色 |

### 生命状态（3 项）

- **健康** (0-100)：归零则人生结束
- **幸福** (0-100)：心理状态
- **精力** (0-100)：每次行动消耗精力，精力不足时部分行动不可用

### 行动列表（18 种）

| 行动 | 图标 | 主要效果 | 精力消耗 | 最低年龄 |
|---|---|---|---|---|
| 学习 | 📚 | 知识+3 | 15 | 0 |
| 锻炼 | 🏃 | 力量+2, 耐力+2 | 20 | 0 |
| 阅读 | 📖 | 知识+2, 逻辑+1 | 10 | 0 |
| 社交 | 🗣️ | 魅力+2, 共情+1 | 15 | 0 |
| 打工 | 💼 | 事业+2, 财力+2 | 25 | 16 |
| 艺术创作 | 🎨 | 创造力+3 | 15 | 0 |
| 冥想 | 🧘 | 共情+1, 恢复精力 | -15 | 0 |
| 休息 | 😴 | 恢复精力+30 | -30 | 0 |
| 娱乐 | 🎮 | 幸福+5, 恢复精力 | -10 | 0 |
| 学技能 | 🔧 | 逻辑+2, 创造力+1 | 20 | 0 |
| 做志愿 | ❤️ | 共情+3, 魅力+1 | 20 | 10 |
| 竞技比赛 | 🏆 | 敏捷+2, 耐力+2 | 30 | 8 |
| 旅行 | ✈️ | 知识+1, 创造力+1 | 10 | 18 |
| 投资理财 | 📈 | 财力+4 | 15 | 20 (财力≥30) |
| 深入研究 | 🔬 | 知识+5, 逻辑+2 | 30 | 18 (知识≥40) |
| 领导项目 | 👔 | 事业+4, 魅力+2 | 30 | 22 (事业≥30) |
| 表演展示 | 🎭 | 魅力+4, 创造力+2 | 25 | 10 (创造力≥30) |
| 冒险探索 | 🗺️ | 敏捷+3, 耐力+3 | 35 | 12 |

高级行动有能力和年龄门槛。行动消耗精力，精力为 0 时只能选择恢复类行动（冥想/休息/娱乐）。

### 人生阶段

| 阶段 | 年龄 | 职业变化 |
|---|---|---|
| 童年 | 0-12 | 幼儿 → 小学生 → 初中生 |
| 青少年 | 13-17 | 高中生 |
| 青年 | 18-29 | 大学生 → 工作者 |
| 壮年 | 30-49 | 职场人士 / 高管 / 创业者 |
| 中年 | 50-64 | 高管/专家 |
| 老年 | 65+ | 退休 → 安享晚年 |

职业由能力和年龄自动决定。

---

## 系统架构

```
┌──────────────────────────────────────────────────────────┐
│                    Web 前端 (HTML/JS/CSS)                  │
│     行动卡片 · 能力面板 · 生命状态条 · 记忆时间线          │
└────────────────────────┬─────────────────────────────────┘
                         │ HTTP
                         ▼
┌──────────────────────────────────────────────────────────┐
│              Game Server (FastAPI + Python)               │
│                                                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐ │
│  │ Game Engine │  │ LLM Client │  │  Action Resolver   │ │
│  │ (会话管理)  │  │(OpenAI API)│  │  (能力/精力计算)   │ │
│  └─────┬──────┘  └────────────┘  └────────────────────┘ │
│        │                                                 │
│  ┌─────┴──────────────────────────────────────────────┐ │
│  │         PowerContext Client (HTTP API)              │ │
│  │  scope · memory · experience · handoff · context    │ │
│  └─────────────────────┬──────────────────────────────┘ │
└────────────────────────┼────────────────────────────────┘
                         │ HTTP
                         ▼
┌──────────────────────────────────────────────────────────┐
│            PowerContext Server (:8000)                     │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │ Scope   │ │ Atomic   │ │Experience│ │  Handoff    │ │
│  │ Manager │ │ Memory   │ │ Engine   │ │  Service    │ │
│  └─────────┘ └──────────┘ └──────────┘ └─────────────┘ │
│  ┌──────────────────────────────────────────────────┐    │
│  │              seekdb (嵌入式存储)                    │    │
│  │    MySQL 兼容 · 全文检索 · 本地持久化              │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

### 数据流（一个完整回合）

```
玩家选择行动（如：锻炼）
    │
    ▼
① 检查精力是否足够 → 不足则拒绝
    │
    ▼
② pc_prepare_context(query=行动名+类别) → 召回人生记忆+教训
    │
    ▼
③ LLM 生成叙事 (System Prompt + 角色状态 + 召回记忆 + 教训)
    │
    ▼
④ 解析 JSON → 提取额外能力变化/生命状态变化/新技能/新关系/教训
    │
    ├─→ 应用行动基础效果 + LLM 奖励效果
    ├─→ 扣除精力 / 推进月数 / 更新年龄和职业
    ├─→ pc_remember(kind, text) → 存储新记忆
    ├─→ pc_capture_source(content) → 存档剧情快照
    └─→ pc_experience_generate() → 重大事件提取教训
    │
    ▼
⑤ 返回叙事 + 能力变化 + 更新后的行动列表给前端
```

---

## 快速开始

### 前置条件

- Python 3.12+
- PowerContext Server（带 seekdb 或 SQLite 后端）
- OpenAI 兼容的 LLM API（OpenAI / DeepSeek / 本地 Ollama 等）

### 方式一：本地运行（推荐开发）

#### 1. 安装 PowerContext Server

```bash
# seekdb 后端（仅 Linux/macOS）
pip install "powercontext[cli,server,seekdb]"

# SQLite 后端（全平台）
pip install "powercontext[cli,server]"
```

#### 2. 启动 PowerContext Server

```bash
# seekdb（Linux/macOS）
export POWERCONTEXT_SERVER_DATABASE_KIND=seekdb
powercontext server run

# SQLite（全平台）
export POWERCONTEXT_SERVER_DATABASE_KIND=sqlite
powercontext server run
```

服务默认运行在 `http://127.0.0.1:8000`。

#### 3. 安装并启动游戏服务

```bash
cd D:/Github/powercontext/qoder

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY

# 启动游戏服务
python -m uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
```

#### 4. 打开游戏

浏览器访问 `http://localhost:8080`

> **无 LLM API Key？** 游戏可在 fallback 模式下运行——行动效果正常计算，仅叙事文本为通用描述。

---

### 方式二：Docker 部署

```bash
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY

docker compose up -d
docker compose logs -f
```

服务地址：
- 游戏前端: `http://localhost:8080`
- PowerContext API: `http://localhost:8000`
- PowerContext Dashboard: `http://localhost:8000/docs`

> **注意**: seekdb 仅支持 Linux。Docker Compose 默认使用 seekdb，Windows/macOS Docker Desktop 可正常工作。如需 SQLite，修改 `docker-compose.yml` 中的 `POWERCONTEXT_SERVER_DATABASE_KIND` 为 `sqlite`。

---

### 方式三：Dify 集成

如果你想用 Dify 作为工作流编排器：

#### 1. 安装 PowerContext Dify 插件

```bash
cd <powercontext-repo>/integrations/dify/plugin
zip -r powercontext-plugin.zip .
# 在 Dify 管理面板 → 工具 → 插件市场 → 本地安装 → 上传 zip
```

#### 2. 配置插件参数

| 参数 | 值 |
|---|---|
| server_url | `http://<powercontext-host>:8000` |
| api_token | (如果启用了认证) |
| scope_id | 留空（动态创建） |
| max_bytes | `4000` |

#### 3. 创建 Dify Agent

- 类型: Agent
- 系统提示词: 复制 `dify/dify-prompt.yaml` 中的 `system_prompt`
- 工具: 添加 PowerContext 插件的所有工具

详细的 Dify 集成说明见 [dify/README.md](dify/README.md)。

---

## PowerContext 集成说明

### Memory（记忆系统）

每次行动事件存储为 Atomic Memory：

```python
await pc.remember_memory(
    scope_id=session.scope_id,
    kind="exercise",          # 行动类别
    text="[12岁] 锻炼：坚持跑步，感觉身体更结实了",
)
```

记忆类型对应行动类别：`body` / `mind` / `social` / `life`，以及特殊类型 `birth` / `milestone`。

### Experience（经验教训）

重大行动后自动提取人生教训：

```python
await pc.generate_experience(
    scope_id=session.scope_id,
    reason="创业失败，负债累累",
    source_ids=["event_001", "event_002"]
)
# → situation → action → outcome → lesson
```

教训在后续行动时被 PreparedContext 召回，影响 AI 叙事。

### Handoff（存档/读档）

```python
# 存档
await pc.handoff_activate(scope_id, source_id)
draft = await pc.handoff_prepare(scope_id, "人生存档", 8000)
prepared = await pc.handoff_finalize(scope_id, draft)
result = await pc.handoff_commit(scope_id, prepared)

# 读档
resolution = await pc.handoff_continue(scope_id)
```

### PreparedContext（上下文召回）

每次行动前，在 token 预算内召回最相关的人生记忆：

```python
context = await pc.prepare_context(
    scope_id=session.scope_id,
    query="锻炼 body 青少年",
    max_bytes=4000,
    memory_limit=6,
    experience_limit=2
)
```

### Scope（数据隔离）

每个玩家每次人生 = 一个独立 Scope：

```python
scope = await pc.create_scope(
    title="张三的人生",
    summary="男，小城市，工薪家庭",
    idempotency_key="life-sim-abc123"
)
```

---

## API 文档

### `GET /api/status`

获取服务状态。

```json
{
  "status": "running",
  "powercontext": "connected",
  "active_sessions": 2
}
```

### `POST /api/game/start`

开始新人生。

请求体：
```json
{
  "name": "张三",
  "gender": "男",
  "background": "普通工薪家庭"
}
```

所有字段可选，留空随机生成。

响应包含角色信息（10 项能力 + 等阶 + 颜色）、可用行动列表、初始叙事。

### `POST /api/game/{session_id}/action`

执行一个行动。

请求体：
```json
{
  "action_id": "exercise"
}
```

响应：
```json
{
  "result": {
    "action_id": "exercise",
    "action_name": "锻炼",
    "narrative": "你在操场上跑了几圈...",
    "ability_changes": {"strength": 2, "endurance": 2},
    "vitality_changes": {"health": 3, "happiness": 1},
    "energy_change": -20,
    "months_advanced": 1,
    "new_skill": null,
    "life_lesson": null,
    "special_event": null,
    "is_game_over": false
  },
  "character": { ... },
  "available_actions": [ ... ],
  "turn_count": 5,
  "is_active": true
}
```

### `GET /api/game/{session_id}/actions`

获取当前可用行动列表（受年龄和能力门槛限制）。

### `POST /api/game/{session_id}/save`

存档当前人生（通过 PowerContext Handoff）。

### `POST /api/game/load`

读取存档。

### `GET /api/game/{session_id}/timeline`

获取记忆时间线和人生教训。

### `GET /api/game/sessions`

列出所有活跃会话。

---

## 项目结构

```
qoder/
├── src/                          # Python 后端
│   ├── main.py                   # FastAPI 应用入口 + API 路由
│   ├── engine.py                 # 游戏引擎（行动解析 + LLM 调用 + 状态更新）
│   ├── pc_client.py              # PowerContext HTTP API 客户端
│   ├── models.py                 # 数据模型 + 行动目录（18 种行动）
│   └── config.py                 # 配置管理
├── static/                       # Web 前端
│   ├── index.html                # 主页面（三栏布局）
│   ├── css/style.css             # 样式（暗色主题 + 等阶配色）
│   └── js/app.js                 # 前端逻辑（行动卡片 + 能力面板）
├── dify/                         # Dify 集成
│   ├── README.md                 # Dify 集成指南
│   └── dify-prompt.yaml          # Dify 系统提示词模板
├── docker-compose.yml            # Docker 编排
├── Dockerfile                    # 游戏服务容器镜像
├── requirements.txt              # Python 依赖
├── .env.example                  # 环境变量模板
└── README.md                     # 本文件
```

---

## 配置参考

所有配置通过环境变量或 `.env` 文件管理：

### PowerContext 连接

| 变量 | 默认值 | 说明 |
|---|---|---|
| `PC_SERVER_URL` | `http://127.0.0.1:8000` | PowerContext Server 地址 |
| `PC_API_TOKEN` | (空) | Bearer 认证 Token |
| `PC_MAX_BYTES` | `4000` | PreparedContext 字节预算 |
| `PC_TIMEOUT` | `30` | HTTP 请求超时(秒) |

### LLM 配置

| 变量 | 默认值 | 说明 |
|---|---|---|
| `LLM_API_BASE` | `https://api.openai.com/v1` | OpenAI 兼容 API 地址 |
| `LLM_API_KEY` | (空) | API Key（空则 fallback 模式） |
| `LLM_MODEL` | `gpt-4o-mini` | 模型名称 |
| `LLM_TEMPERATURE` | `0.85` | 生成温度 |
| `LLM_MAX_TOKENS` | `2000` | 最大输出 token |
| `LLM_TIMEOUT` | `60` | 请求超时(秒) |

### 游戏服务

| 变量 | 默认值 | 说明 |
|---|---|---|
| `GAME_HOST` | `0.0.0.0` | 监听地址 |
| `GAME_PORT` | `8080` | 监听端口 |
| `GAME_MAX_SESSIONS` | `100` | 最大并发会话数 |
| `GAME_MAX_AGE` | `80` | 人生最大年龄 |

### 兼容的 LLM 服务

| 服务 | API Base | 推荐模型 |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| Ollama (本地) | `http://localhost:11434/v1` | `qwen2.5:14b` |
| Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |

---

## 常见问题

### Q: seekdb 在 Windows 上不可用怎么办？

两种方案：

1. **SQLite 后端**（推荐开发环境）：
   ```bash
   export POWERCONTEXT_SERVER_DATABASE_KIND=sqlite
   powercontext server run
   ```
2. **Docker Desktop**：容器内运行 Linux，seekdb 正常工作。

### Q: 没有 LLM API Key 能玩吗？

可以。游戏在 fallback 模式下运行——行动效果（能力提升、精力消耗、年龄推进）全部正常计算，仅叙事文本为通用描述（如"你进行了锻炼，感觉有所收获"）。配置 API Key 后获得 AI 生成的个性化叙事。

### Q: PowerContext Server 没启动，游戏能运行吗？

可以。引擎自动检测 PowerContext 连接状态，不可用时降级为本地内存模式——游戏正常进行，但记忆不持久化，关闭服务后进度丢失。

### Q: 如何添加新行动？

在 `src/models.py` 的 `_build_actions()` 函数中添加新的 `ActionDef` 条目：

```python
ActionDef(
    id="cook", name="烹饪", icon="🍳",
    description="学习烹饪，提升创造力",
    category="mind",
    effects=[ActionEffect(ability="creativity", amount=2)],
    vitality_changes={"happiness": 2},
    energy_cost=15, months_advance=2,
    min_age=6, tags=["basic"],
)
```

### Q: 如何调整能力等阶阈值？

修改 `src/models.py` 中的 `get_rank()` 函数。当前阈值：F(0-19), D(20-39), C(40-59), B(60-74), A(75-89), S(90-100)。

### Q: 如何查看 PowerContext 中存储的记忆？

访问 PowerContext Dashboard: `http://localhost:8000/docs`。

---

## License

MIT
