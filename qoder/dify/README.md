# Dify 集成配置 — AI 人生模拟器

> 基于 Dify Workflow + PowerContext + seekdb 构建的行动驱动人生模拟游戏。

---

## 目录

- [架构概述](#架构概述)
- [文件说明](#文件说明)
- [环境要求](#环境要求)
- [部署步骤](#部署步骤)
- [PowerContext 插件安装](#powercontext-插件安装)
- [DSL 导入](#dsl-导入)
- [配置说明](#配置说明)
- [验证样例](#验证样例)

---

## 架构概述

```
┌─────────────────────────────────────────────────────────────┐
│                      Dify 平台                                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │           AI人生模拟器 Workflow                         │  │
│  │                                                        │  │
│  │  [用户输入] → [HTTP: 召回记忆] → [LLM: 生成叙事]       │  │
│  │                      ↓                    ↓             │  │
│  │              [PowerContext]      [代码: 解析JSON]       │  │
│  │                      ↓                    ↓             │  │
│  │              [seekdb 存储]       [HTTP: 存储记忆]       │  │
│  │                                           ↓             │  │
│  │                                    [回复叙事]           │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              PowerContext Server (:8000)                      │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────┐ │
│  │ Scope   │ │ Atomic   │ │Experience│ │  Handoff        │ │
│  │ Manager │ │ Memory   │ │ Engine   │ │  Service        │ │
│  └─────────┘ └──────────┘ └──────────┘ └─────────────────┘ │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              seekdb (嵌入式存储)                         │  │
│  │    MySQL 兼容 · 全文检索 · 本地持久化                    │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 技术分工

| 组件 | 职责 |
|------|------|
| **Dify** | 工作流编排、LLM 调用、用户交互界面 |
| **PowerContext** | 记忆存储/召回、经验教训提取、存档读档、上下文管理 |
| **seekdb** | PowerContext 底层存储，提供全文检索和向量检索能力 |

---

## 文件说明

| 文件 | 用途 |
|------|------|
| `ai-life-simulator.yml` | Dify Workflow DSL，可直接导入 Dify |
| `dify-prompt.yaml` | 系统提示词模板（供参考或自定义使用） |
| `plugin/` | PowerContext Dify 插件源码 |
| `README.md` | 本文件 |

---

## 环境要求

| 组件 | 版本要求 | 说明 |
|------|---------|------|
| Dify | ≥ 0.15.0 | 推荐最新版 |
| PowerContext Server | ≥ 0.1.0 | 带 seekdb 或 SQLite 后端 |
| Python | 3.12+ | 运行 PowerContext Server |
| LLM 服务 | OpenAI 兼容 | DeepSeek / OpenAI / 通义千问 / Ollama |

---

## 部署步骤

### 1. 启动 PowerContext Server

```bash
# 安装 PowerContext（seekdb 后端，仅 Linux）
pip install "powercontext[cli,server,seekdb]"

# 启动服务
export POWERCONTEXT_SERVER_DATABASE_KIND=seekdb
powercontext server run --host 0.0.0.0 --port 8000
```

> Windows/macOS 用户请使用 SQLite 后端：
> ```bash
> pip install "powercontext[cli,server]"
> export POWERCONTEXT_SERVER_DATABASE_KIND=sqlite
> powercontext server run
> ```

验证服务启动：
```bash
curl http://127.0.0.1:8000/health/live
# 应返回: {"status": "ok"}
```

### 2. 启动 Dify

参考 [Dify 官方文档](https://docs.dify.ai/getting-started/install-self-hosted/docker-compose) 使用 Docker Compose 部署 Dify。

确保 Dify 可以访问 PowerContext Server 地址（如 `http://host.docker.internal:8000` 或局域网 IP）。

### 3. 安装 PowerContext 插件（可选）

如果需要使用插件工具，参考 [插件安装](#powercontext-插件安装)。

**或者** 直接使用 Workflow 中的 HTTP 节点调用 PowerContext API（推荐，无需额外插件）。

### 4. 导入 DSL

1. 登录 Dify 管理后台
2. 进入 **工作室** → **创建空白应用** → **导入 DSL**
3. 上传 `ai-life-simulator.yml`
4. 确认导入

### 5. 配置环境变量

在 Dify 工作流编辑器中，配置以下环境变量：

| 变量名 | 示例值 | 说明 |
|--------|--------|------|
| `pc_server_url` | `http://127.0.0.1:8000` | PowerContext 服务地址 |
| `pc_scope_id` | （留空，动态创建） | 人生会话 ID |

### 6. 配置模型

在工作流中配置 LLM 模型：

1. 点击 **生成叙事** 节点
2. 选择模型提供商（如 DeepSeek、OpenAI）
3. 配置 API Key
4. 选择模型（推荐 `deepseek-chat` 或 `gpt-4o-mini`）

---

## PowerContext 插件安装

插件位于 `plugin/` 目录，提供以下工具：

| 工具 | 功能 |
|------|------|
| `pc_prepare_context` | 召回人生记忆和教训 |
| `pc_remember` | 存储新记忆 |
| `pc_search` | 搜索历史记忆 |
| `pc_capture_source` | 存档叙事内容 |
| `pc_experience_generate` | 提取人生教训 |
| `pc_handoff_save` | 存档人生状态 |
| `pc_handoff_load` | 恢复人生状态 |

### 安装步骤

```bash
# 打包插件
cd dify/plugin
zip -r powercontext-plugin.zip . -x "*.pyc" "__pycache__/*"

# 在 Dify 中安装
# 1. 进入 工具 → 插件市场
# 2. 选择 本地安装
# 3. 上传 powercontext-plugin.zip
```

### 配置插件凭据

安装后需配置插件连接参数：

| 参数 | 值 |
|------|-----|
| `server_url` | `http://<powercontext-host>:8000` |
| `api_token` | （如启用认证则填写） |

---

## DSL 导入

### 导入文件

`ai-life-simulator.yml`

### 导入顺序

单文件，直接导入即可。

### 导入后检查

1. **环境变量**：确认 `pc_server_url` 指向正确的 PowerContext 服务
2. **模型配置**：确认 LLM 模型已绑定且 API Key 有效
3. **HTTP 节点**：确认 PowerContext API 地址可达

### 重新绑定说明

如果 PowerContext 服务地址变化，需修改：
- 环境变量 `pc_server_url`
- 或 HTTP 节点中的 URL 配置

---

## 配置说明

### 工作流节点

| 节点 | 类型 | 说明 |
|------|------|------|
| 开始 | Start | 接收用户输入 |
| 召回记忆 | HTTP Request | 调用 PowerContext `/v1/context/prepare` |
| 生成叙事 | LLM | 调用大模型生成行动结果 |
| 解析结果 | Code | 解析 JSON 输出 |
| 存储记忆 | HTTP Request | 调用 PowerContext `/v1/memory/remember` |
| 回复 | Answer | 输出叙事给玩家 |

### 系统提示词

工作流内置系统提示词，核心规则：
- 第二人称叙述
- 60-150 字简洁叙事
- 根据人生阶段调整语气
- 呼应历史记忆和教训
- JSON 格式输出（含额外效果）

---

## 验证样例

### 样例 1: 基础行动流程

**初始条件：**
- PowerContext Server 运行中
- Dify 应用已导入并配置
- 环境变量 `pc_scope_id` 已设置（或通过 API 创建）

**操作步骤：**

1. 打开 Dify 应用界面
2. 发送消息：`我叫小明，男，普通工薪家庭`
3. 等待角色创建响应
4. 发送消息：`我选择锻炼`

**预期结果：**

- 步骤 2 返回角色基本信息和开场叙事
- 步骤 4 返回类似：
  ```
  你在小区附近的公园里跑了几圈，虽然气喘吁吁，但感觉身体更结实了。
  汗水浸湿了 T 恤，你觉得自己又强壮了一点。
  ```

**验证 PowerContext 作用：**

```bash
# 查看存储的记忆
curl -X POST http://127.0.0.1:8000/v1/memory/entries/list \
  -H "Content-Type: application/json" \
  -d '{"scope_id": "<your-scope-id>", "limit": 10}'
```

应能看到刚存储的锻炼记忆。

### 样例 2: 记忆召回

**前置条件：** 已执行样例 1，存储了多条记忆

**操作步骤：**

1. 发送：`我选择学习`
2. 观察叙事是否呼应之前的经历

**预期结果：**

叙事中可能包含类似 "想起之前锻炼时养成的毅力，你决定也用在学习上" 的内容，体现记忆召回效果。

### 样例 3: 存档/读档（如使用插件）

**操作步骤：**

1. 使用 `pc_handoff_save` 工具存档
2. 关闭应用
3. 重新打开，使用 `pc_handoff_load` 工具读档

**预期结果：** 人生状态恢复，可以继续之前的进度。

---

## 已知限制

1. **seekdb 仅支持 Linux**：Windows/macOS 开发环境请使用 SQLite 后端
2. **需要网络访问**：Dify 需要能访问 PowerContext Server 的 HTTP 端口
3. **LLM 依赖**：无 LLM API Key 时工作流无法生成叙事

---

## 参考链接

- [Dify 官方文档](https://docs.dify.ai)
- [PowerContext API 文档](https://github.com/oceanbase/powercontext)
- [seekdb 项目说明](https://github.com/oceanbase/seekdb)
- [Dify HTTP Request 节点](https://docs.dify.ai/guides/workflow/node/http-request)
