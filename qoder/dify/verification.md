# 验证样例 — AI 人生模拟器

> 本文档提供完整的验证步骤，用于确认应用功能正常、技术集成有效。

---

## 验证环境要求

| 组件 | 版本 | 状态检查 |
|------|------|---------|
| Dify | ≥ 0.15.0 | `docker ps` 确认容器运行 |
| PowerContext Server | ≥ 0.1.0 | `curl http://localhost:8000/health/live` |
| seekdb/SQLite | - | PowerContext 启动时自动初始化 |
| LLM 服务 | DeepSeek/OpenAI | API Key 已配置 |

---

## 样例 1: 完整人生开局流程

### 目标
验证从角色创建到首次行动的完整流程，确认 Dify 工作流、PowerContext 记忆存储正常工作。

### 初始状态
- PowerContext 中无相关 scope
- Dify 应用已导入并配置完成

### 操作步骤

#### 步骤 1: 创建角色

**输入：**
```
我叫李明，男，出生在一个小城市的普通工薪家庭。
```

**预期输出：**
Dify 应返回角色创建确认，包含：
- 角色姓名：李明
- 性别：男
- 出身：小城市工薪家庭
- 初始能力值（10 项，F 阶起步）
- 开场叙事

**验证点：**
- [ ] Dify 工作流正常执行
- [ ] LLM 生成符合格式的叙事
- [ ] 返回内容包含角色信息

#### 步骤 2: 执行首次行动

**输入：**
```
我选择锻炼
```

**预期输出：**
叙事文本描述锻炼场景，如：
```
你在小区附近的操场上跑了几圈，虽然气喘吁吁，但感觉身体更结实了。
汗水浸湿了 T 恤，你觉得自己又强壮了一点。
```

**验证点：**
- [ ] 叙事内容符合"锻炼"行动主题
- [ ] 字数在 60-150 字范围内
- [ ] 使用第二人称"你"叙述

#### 步骤 3: 检查记忆存储

**命令：**
```bash
# 获取 scope_id（从 Dify 环境变量或日志中获取）
SCOPE_ID="your-scope-id-here"

# 查询已存储的记忆
curl -X POST http://127.0.0.1:8000/v1/memory/entries/list \
  -H "Content-Type: application/json" \
  -d "{\"scope_id\": \"$SCOPE_ID\", \"limit\": 10}"
```

**预期结果：**
返回 JSON 数组，包含至少 1 条记忆记录：
```json
[
  {
    "entry_id": "xxx",
    "kind": "life",
    "text": "[行动] 你在小区附近的操场上跑了几圈...",
    "created_at": "2026-01-07T..."
  }
]
```

**验证点：**
- [ ] PowerContext 成功存储记忆
- [ ] 记忆内容包含本次行动的叙事摘要
- [ ] kind 字段为 "life" 或 "body"

---

## 样例 2: 记忆召回与叙事呼应

### 目标
验证 PowerContext 的上下文召回功能，确认 LLM 叙事能引用历史记忆。

### 前置条件
- 已执行样例 1，存储了多条记忆（建议 3-5 条不同行动）

### 操作步骤

#### 步骤 1: 累积更多记忆

依次执行以下行动：
```
我选择学习
我选择阅读
我选择社交
```

每次确认叙事已生成并存储。

#### 步骤 2: 触发记忆召回

**输入：**
```
我选择锻炼
```

**预期输出：**
叙事中应包含对之前经历的呼应，例如：
```
想起之前学习时养成的专注力，你决定把这份毅力也用在锻炼上。
你在操场上坚持跑了十圈，虽然累但内心充实。
```

**验证点：**
- [ ] 叙事中体现对历史行动的回忆
- [ ] PowerContext 的 `/v1/context/prepare` 被调用
- [ ] 召回的记忆内容影响了 LLM 生成

#### 步骤 3: 检查上下文召回日志

**命令：**
```bash
# 查看 PowerContext 服务端日志
# 应能看到类似：
# POST /v1/context/prepare 200
# scope_id=xxx query="锻炼" max_bytes=4000
```

**验证点：**
- [ ] PowerContext 收到 context/prepare 请求
- [ ] 返回的 content 包含历史记忆

---

## 样例 3: 人生教训提取

### 目标
验证 PowerContext Experience 功能，确认重大事件后能提取人生教训。

### 操作步骤

#### 步骤 1: 触发重大事件

**输入（模拟一个高难度或特殊行动）：**
```
我决定创业，开一家小公司
```

**预期输出：**
叙事描述创业过程，可能包含挑战或失败：
```
你拿出所有积蓄，租下一间小办公室。创业的路充满未知，
但你相信自己的能力。第一天，你签下了一个小小的订单。
```

#### 步骤 2: 检查经验提取

如果工作流配置了 `pc_experience_generate`，应能看到教训提取：

**命令：**
```bash
# 查询该 scope 的经验教训
curl -X POST http://127.0.0.1:8000/v1/experience/list \
  -H "Content-Type: application/json" \
  -d "{\"scope_id\": \"$SCOPE_ID\"}"
```

**预期结果：**
返回包含 situation → action → outcome → lesson 结构的经验记录。

**验证点：**
- [ ] Experience 被成功提取
- [ ] lesson 字段包含有意义的人生教训

---

## 样例 4: seekdb 存储验证

### 目标
验证 seekdb 作为 PowerContext 底层存储的实际数据读写。

### 操作步骤

#### 步骤 1: 确认 seekdb 运行状态

**命令：**
```bash
# 检查 PowerContext 使用的数据库类型
curl http://127.0.0.1:8000/health/live
```

**预期输出：**
```json
{"status": "ok", "database": "seekdb"}
```

#### 步骤 2: 执行多次行动写入数据

连续执行 5 次不同行动，确保有足够数据写入。

#### 步骤 3: 验证全文检索

**命令：**
```bash
# 使用 seekdb 的全文检索能力搜索记忆
curl -X POST http://127.0.0.1:8000/v1/memory/search \
  -H "Content-Type: application/json" \
  -d "{\"scope_id\": \"$SCOPE_ID\", \"query\": \"锻炼 跑步 操场\", \"limit\": 5}"
```

**预期结果：**
返回与"锻炼"相关的记忆，证明 seekdb 全文检索工作正常。

**验证点：**
- [ ] seekdb 成功存储所有记忆数据
- [ ] 全文检索能返回相关结果
- [ ] 检索结果按相关性排序

---

## 技术作用总结

### Dify 的作用

| 功能 | 实现方式 |
|------|---------|
| 工作流编排 | Workflow 节点串联 |
| LLM 调用 | LLM 节点 + 系统提示词 |
| 用户交互 | Dify 内置聊天界面 |
| HTTP 集成 | HTTP Request 节点调用 PowerContext API |

### PowerContext 的作用

| 功能 | API 端点 | 说明 |
|------|---------|------|
| 记忆存储 | `/v1/memory/remember` | 每次行动后存储事件记忆 |
| 上下文召回 | `/v1/context/prepare` | 行动前召回相关历史 |
| 记忆搜索 | `/v1/memory/search` | 全文检索历史记忆 |
| 经验提取 | `/v1/experience/generate` | 重大事件后提取教训 |
| 存档读档 | `/v1/handoff/*` | 人生状态持久化 |

### seekdb 的作用

| 功能 | 说明 |
|------|------|
| 数据存储 | PowerContext 底层持久化 |
| 全文检索 | 支持记忆内容的关键词搜索 |
| 向量检索 | 支持语义相似度召回（如配置） |

---

## 截图指引

验证时建议截取以下画面：

1. **Dify 工作流编辑器** — 展示完整节点连接
2. **Dify 聊天界面** — 展示用户输入和 AI 回复
3. **PowerContext Dashboard** (`http://localhost:8000/docs`) — 展示 API 调用记录
4. **记忆列表** — 展示存储的记忆条目
5. **seekdb 日志** — 展示数据读写操作

---

## 故障排查

| 问题 | 可能原因 | 解决方法 |
|------|---------|---------|
| 工作流执行失败 | PowerContext 未启动 | 检查 `http://localhost:8000/health/live` |
| 记忆未存储 | scope_id 未配置 | 检查环境变量 `pc_scope_id` |
| LLM 无响应 | API Key 未配置 | 在 Dify 中配置模型凭据 |
| 召回内容为空 | 无历史记忆 | 先执行几次行动积累记忆 |
| HTTP 节点报错 | 网络不通 | 检查 Dify 到 PowerContext 的网络连通性 |

---

## 复现步骤

如需从零开始复现：

```bash
# 1. 启动 PowerContext
pip install "powercontext[cli,server,seekdb]"
export POWERCONTEXT_SERVER_DATABASE_KIND=seekdb
powercontext server run &

# 2. 启动 Dify (参考官方文档)
# docker compose up -d

# 3. 导入 DSL
# 在 Dify 中导入 dify/ai-life-simulator.yml

# 4. 配置环境变量
# pc_server_url = http://host.docker.internal:8000
# pc_scope_id = (创建新 scope 后填入)

# 5. 配置模型
# 在 Dify 中绑定 DeepSeek 或 OpenAI

# 6. 开始验证
# 按照上述样例操作
```
