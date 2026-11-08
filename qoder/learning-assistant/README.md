# 基于 PowerContext 的自适应学习助手

一个利用 [PowerContext](https://github.com/oceanbase/powercontext) 上下文管理能力构建的智能学习助手。通过 seekdb 嵌入式数据库存储学习数据，结合 LLM 实现个性化学习计划生成、跨会话进度追踪和自适应教学策略。

## 核心特性

- **学习计划生成** — 输入目标和周期，LLM 自动生成结构化学习计划并持久化到 PowerContext Memory
- **跨会话连续性** — 每次学习会话结束自动保存状态，下次启动时恢复上下文（"上次你学到了 X，今天继续 Y"）
- **交互式教学** — 苏格拉底式对话，引导学生思考而非直接给出答案
- **练习经验记录** — 记录每次练习的情境/做法/结果/教训，写入 PowerContext Experience
- **进度追踪与分析** — 从 Memory 中检索学习数据，LLM 分析生成进度报告和建议
- **自适应策略引擎** — 根据练习正确率自动调整难度、识别薄弱点、安排间隔复习
- **seekdb 混合检索** — 利用 seekdb 的 FULLTEXT + VECTOR 索引实现精准知识召回

## 架构

```
┌─────────────────────────────────────────────────┐
│                  CLI (Typer + Rich)              │
├─────────────────────────────────────────────────┤
│              服务层 (Services)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ PlanSvc  │ │SessionSvc│ │ AdaptiveSvc      │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
├─────────────────────────────────────────────────┤
│              LLM 层 (OpenAI SDK)                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ Planner  │ │  Tutor   │ │  Analyzer        │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
├─────────────────────────────────────────────────┤
│           PowerContext SDK                       │
│  ┌────────┐ ┌────────┐ ┌──────┐ ┌────────────┐ │
│  │ Memory │ │ Source │ │Skill │ │ Experience │ │
│  └────────┘ └────────┘ └──────┘ └────────────┘ │
├─────────────────────────────────────────────────┤
│         存储层 (seekdb / SQLite)                 │
└─────────────────────────────────────────────────┘
```

### PowerContext 数据模型映射

| 功能 | PowerContext 原语 | 说明 |
|------|-------------------|------|
| 学习材料 | Source | 课件、笔记、对话记录 |
| 学生画像 | Atomic Memory (`student_profile`) | 姓名、水平、偏好 |
| 学习计划 | Atomic Memory (`plan`) | 里程碑、时间线 |
| 知识掌握 | Atomic Memory (`mastery` / `weakness`) | 已掌握/薄弱知识点 |
| 会话状态 | Atomic Memory (`session_state`) | 跨会话恢复数据 |
| 练习经验 | Experience | situation/action/outcome/lesson |
| 知识检索 | seekdb FULLTEXT + VECTOR | 混合搜索学习材料 |

### Scope 层级

```
Student Scope (学生根 scope)
├── Course Scope (课程 scope)
│   ├── Session Scope (会话 1)
│   ├── Session Scope (会话 2)
│   └── ...
├── Course Scope (另一门课程)
│   └── ...
└── ...
```

## 项目结构

```
learning-assistant/
├── pyproject.toml                          # 项目配置与依赖
├── config/
│   └── settings.py                         # 全局配置（数据库、LLM、服务器）
├── src/learning_assistant/
│   ├── __init__.py
│   ├── context/
│   │   ├── server.py                       # 内嵌 PowerContext 服务器
│   │   └── client.py                       # 高层客户端封装
│   ├── llm/
│   │   ├── base.py                         # LLM 基类
│   │   ├── planner.py                      # 计划生成 LLM
│   │   ├── tutor.py                        # 教学交互 LLM
│   │   └── analyzer.py                     # 学习分析 LLM
│   ├── services/
│   │   ├── models.py                       # 数据模型
│   │   ├── plan_service.py                 # 学习计划服务
│   │   ├── session_service.py              # 会话管理服务
│   │   ├── progress_service.py             # 进度追踪服务
│   │   └── adaptive_service.py             # 自适应策略引擎
│   └── cli/
│       └── app.py                          # CLI 命令行应用
└── README.md
```

## 环境要求

- Python >= 3.11
- OpenAI API Key（或其他兼容 API）
- **seekdb**: 仅支持 Linux / macOS
- **SQLite**: 所有平台（Windows 自动回退）

## 安装

### 1. 安装 PowerContext

```bash
# 从源码安装（推荐，确保版本兼容）
cd /path/to/powercontext
pip install -e ".[server,client,seekdb]"

# 或仅使用 SQLite（Windows 用户）
pip install -e ".[server,client]"
```

### 2. 安装学习助手

```bash
cd learning-assistant
pip install -e .
```

### 3. 配置环境变量

```bash
# 必须
export OPENAI_API_KEY="sk-..."

# 可选：使用自定义 API 端点
export OPENAI_BASE_URL="https://your-api-proxy/v1"
```

## 使用方法

### 初始化学生档案

```bash
learn init "张三" --level intermediate
```

输出示例：
```
┌──────────── 🎓 初始化完成 ────────────┐
│ 学生档案已创建                         │
│   姓名: 张三                           │
│   水平: intermediate                   │
│   Scope ID: abc123...                  │
│   数据库: seekdb                       │
└────────────────────────────────────────┘
请保存 Scope ID: abc123...
```

### 创建学习计划

```bash
learn create-plan "Rust 入门" \
  --goal "掌握 Rust 基础语法和所有权系统" \
  --weeks 8 \
  --background "有 Python 和 C 经验" \
  --student-scope <学生Scope ID>
```

### 开始学习会话

```bash
learn study "变量与类型" --course-scope <课程Scope ID>
```

进入交互式对话：
```
┌──────── 📖 新学习会话 ────────┐
│ 主题: 变量与类型              │
└───────────────────────────────┘

交互命令:
  quit     - 退出并保存进度
  save     - 手动保存当前进度
  exercise - 记录一次练习

你 > Rust 中的变量默认是不可变的吗？
助手 > 好问题！让我们想想——如果你有一个变量 x = 5，
       然后尝试 x = 6，你觉得会发生什么？
       提示：试试在你的编译器中运行看看。

你 > exercise
  记录练习经验:
  题目/情境 > 编写一个交换两个变量值的函数
  你的做法 > 直接用 a = b 赋值
  结果 > 编译错误
  学到什么 > Rust 中赋值是移动语义，原变量不再可用

你 > quit
┌──────── ✅ 会话结束 ────────┐
│ 会话已保存                   │
│   主题: 变量与类型           │
│   记录: 2 条                 │
└──────────────────────────────┘
```

### 查看学习进度

```bash
learn progress <课程Scope ID> --course-name "Rust 入门"
```

### 查看自适应策略

```bash
learn adaptive <Scope ID> --topic "所有权系统"
```

## 配置说明

所有配置通过环境变量或命令行参数控制：

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | (必填) |
| `OPENAI_BASE_URL` | 自定义 API 端点 | `https://api.openai.com/v1` |
| `LEARNING_ASSISTANT_DATABASE__KIND` | 数据库类型 | 自动检测 (seekdb/sqlite) |

### 数据库选择

- **seekdb** (Linux/macOS): 嵌入式数据库，支持 FULLTEXT + VECTOR 混合检索
- **SQLite** (所有平台): 轻量级替代，支持 FTS5 全文检索

数据库文件默认存储在 `~/.learning-assistant/` 目录下。

## 开发

### 项目结构说明

```
context/
  server.py    - EmbeddedPowerContextServer: 进程内启动 PowerContext 服务器
  client.py    - LearningAssistantClient: 封装 PowerContext SDK 的高层 API

llm/
  base.py      - BaseLLM: OpenAI 客户端封装
  planner.py   - PlanLLM: 生成结构化学习计划 (JSON)
  tutor.py     - TutorLLM: 苏格拉底式教学对话
  analyzer.py  - AnalyzerLLM: 进度分析与建议生成

services/
  plan_service.py      - 计划创建、查询、里程碑更新
  session_service.py   - 会话开始/结束、对话、练习记录
  progress_service.py  - 进度报告生成
  adaptive_service.py  - 难度调整、薄弱点追踪、间隔复习
```

### 扩展教学策略

在 `services/adaptive_service.py` 中扩展 `AdaptiveService`：

```python
# 添加新的教学策略
async def get_teaching_strategy(self, course_scope_id, topic):
    return {
        "difficulty": self._state.current_difficulty.value,
        "style": self._state.learning_style.value,
        "focus_areas": self._state.focus_areas,
        # 添加更多策略参数...
    }
```

### 添加新的 Source 类型

在 `context/client.py` 的 `save_learning_material` 中扩展：

```python
await client.save_learning_material(
    scope_id=scope_id,
    material_type="flashcard",  # 新类型
    content={"front": "问题", "back": "答案"},
)
```

## 许可证

Apache License 2.0
