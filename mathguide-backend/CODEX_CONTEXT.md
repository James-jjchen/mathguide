# MathGuide — Codex Onboarding Context

> 生成时间：2026-07-11 14:54  
> Codex 核验更新：2026-07-11 15:05（以当前代码和实际启动结果为准）
> 项目路径：`D:\PythonProject\workspace\`
> Backend：`mathguide-backend/` | Frontend：`mathguide-frontend/`

---

## 一、项目定位

MathGuide（技能图谱学习系统）是一个微积分自适应学习平台。核心设计：将知识点拆解至细粒度 **技能维度（Skill Dimension）**，通过对每个维度的 Beta-Bayesian 建模实现精准掌握度追踪，再通过五类路径规划动作（L1-L4 补偿事件）驱动自适应学习。

原为命令行 demo，后来扩展为 Flask 后端 + React 前端的完整 Web 应用。

---

## 二、架构概览（两阶段演进）

### Phase 1 — 命令行原型（engine/）

`engine/__init__.py` 包含纯 Python 的完整原型框架：

| 类 | 职责 |
|:---|:-----|
| `SkillGraph` | 从 `data/skill_graph.json` 加载 43 个节点 + 106 个维度 + 98 条边，构建查询索引 |
| `UserState` | 内存状态（dim_mastery / dim_confidence / stuck_count / momentum / recent_history），挂载 apply_correct/wrong/stuck + recompute_all/bottlenecks |
| `ProblemEngine` | 从 `data/problems.json` 加载 20 道分步骤题，提供 get_warmup / get_adaptive |
| `PathPlanner` | 生成 3 类动作（bottleneck / unlock / transfer），按 momentum 排序 |
| `Engine` | 编排引擎：run_problem → 分步诊断 + 错误传播 + 补偿事件检测（L1-L4）+ 推荐下一步 |

`demo_cli.py` 演示了 Phase 1 的 3 个场景。

### Phase 2 — Web 应用（Flask + React）

保持 Phase 1 的核心算法思想，但重构为数据库驱动的持久化架构：

| 文件 | 职责 |
|:-----|:------|
| `app.py` | Flask 路由 + 全局配置 (~1100 行) |
| `database.py` | 数据库操作层 (~1780 行) |
| `path_planner.py` | DB 版路径规划器（5 类动作 + 评分排序） |
| `recommend.py` | **旧版** 网络X 图推荐（兼容保留） |
| `llm_api.py` | DeepSeek API 封装（问答 / 评估 / 出题） |

Phase 2 的**前端**是 React (Vite) 应用，位于 `mathguide-frontend/`。

---

## 三、目录结构

```
mathguide-backend/
├── app.py                 # Flask 路由入口 (~1100行)
├── database.py            # 数据库操作层 (~1780行)
├── path_planner.py        # DB版路径规划器 (5类动作)
├── recommend.py           # 旧版推荐引擎 (兼容保留)
├── llm_api.py             # DeepSeek API封装
├── demo_cli.py            # Phase 1 原型演示
├── requirements.txt       # Flask, flask-cors, requests, networkx
├── .venv/                 # Python 3.13 虚拟环境
├── data/                  # 静态数据
│   ├── skill_graph.json   # 知识图谱 (43节点, 106维度, 98边)
│   ├── problems.json      # 20道分步骤题
│   ├── knowledge_nodes.csv # 旧版节点数据
│   └── prerequisites.csv   # 旧版前置关系
├── engine/                # Phase 1 原型
│   └── __init__.py        # SkillGraph, UserState, ProblemEngine, PathPlanner, Engine
├── instance/
│   └── mathguide.db       # SQLite 数据库
└── tests/
    └── api_tests.postman_collection.json

mathguide-frontend/
├── src/
│   ├── App.jsx, main.jsx
│   ├── api/mathguide.js        # 原生 fetch API 封装（含超时与 SSE）
│   ├── context/UserContext.jsx  # 全局状态管理
│   ├── components/             # 通用组件
│   │   ├── Header.jsx          # 顶部导航 (设定位+用户名)
│   │   ├── Sidebar.jsx         # 侧边导航
│   │   ├── MainLayout.jsx      # 布局框架
│   │   ├── ChatPanel.jsx       # 聊天面板 (SSE流式)
│   │   ├── ChatMessage.jsx     # 单条消息渲染 (含LaTeX)
│   │   ├── ChatInput.jsx       # 输入框
│   │   ├── CognitiveMap.jsx    # D3认知地图
│   │   ├── KnowledgeMap.jsx    # 知识图谱可视化
│   │   ├── RecommendationPanel.jsx    # v1推荐面板
│   │   ├── RecommendationCard.jsx     # 推荐卡片
│   │   ├── MasteryBar.jsx, ProgressBar.jsx  # 进度展示
│   │   ├── DimMasteryList.jsx   # 维度级掌握度列表
│   │   ├── PracticeOverlay.jsx  # 练习悬浮层
│   │   ├── Onboarding.jsx       # 首次引导
│   │   ├── DevMode.jsx          # 开发者调试面板
│   │   ├── LatexBlock.jsx       # LaTeX渲染块
│   │   ├── AdminLoginModal.jsx  # 管理员登录
│   │   ├── ErrorBanner.jsx
│   │   ├── LoadingSpinner.jsx
│   │   └── EmptyState.jsx
│   └── pages/
│       ├── WelcomePage.jsx           # 欢迎/登录
│       ├── DashboardPage.jsx         # 仪表盘
│       ├── ChatPage.jsx              # AI聊天
│       ├── PracticePage.jsx          # 练习
│       ├── StageMapPage.jsx          # 闯关地图
│       ├── StageChallengePage.jsx    # 闯关挑战
│       └── AdminPage.jsx             # 管理员界面
└── dist/                     # 构建产物
```

---

## 四、数据模型

### 4.1 三元分层

```
知识节点 (knowledge_node)         — 粗粒度概念，如「分部积分法」
  └─ 技能维度 (skill_dimension)    — 细粒度可训练技能，如「LIATE法则选择」「基本求导公式」
      └─ 步 (step in problems.js)  — 一道分步骤题的解题步骤，每个step对应一个dim_id
```

### 4.2 SQLite schema（8 张核心表）

```sql
-- 旧版知识节点 (23条, 持续存在)
knowledge_nodes(id PK, name, difficulty, chapter_id)

-- 旧版前置关系
prerequisites(from_id, to_id PK)

-- 节点级掌握度 (Phase 1兼容)
user_mastery(user_id, node_id PK, mastery, last_updated)

-- 练习记录
practice_sessions(id PK, user_id, target_nodes, questions_json,
                  results_json, average_score, total_questions, created_at)

-- 维度级掌握度 (Beta分布参数)
skill_dimensions(dim_id PK, name, parent_node_id FK, difficulty, node_weight)
skill_edges(from_dim, to_dim PK, transfer_gain, cognitive_distance, edge_type)
user_dim_params(user_id, dim_id PK, alpha, beta, stuck_count, last_updated)
user_meta(user_id PK, momentum, state_json)
```

### 4.3 核心算法：Bayesian 掌握度模型

每个用户技能维度服从 Beta 分布 Beta(alpha, beta)：

- **alpha** = 正确信号的累积（+1 per correct）
- **beta** = 错误信号的累积（+1 per wrong, +0.5 per stuck）
- **掌握度** = alpha / (alpha + beta)
- **置信度** = alpha + beta（样本量越大越精确）
- **节点掌握度** = 其所有维度的加权平均

---

## 五、API 端点

### 基础 (v1)

| 端点 | 方法 | 说明 |
|:-----|:-----|:-----|
| `/api/init_user` | POST | 初始化用户 (传 node_mastery dict 或 chapter_ids) |
| `/api/ask` | POST | 数学问答（带知识边界 + 后台掌握度更新）|
| `/api/ask/stream` | POST | SSE 流式问答 |
| `/api/recommend` | POST | 节点级推荐（v1, 复习/新知识）|
| `/api/generate-practice` | POST | LLM 生成练习题 |
| `/api/submit-practice` | POST | 提交练习 + LLM 评估 |
| `/api/diagnose` | POST | 知识点诊断（LLM评估回答）|
| `/api/diagnose-weaknesses` | POST | 数据库查询薄弱点（无需LLM）|
| `/api/mastery` | GET | 获取所有节点掌握度 |
| `/api/nodes` | GET | 所有知识点列表 |
| `/api/node/<id>` | GET | 单个知识点 |
| `/api/chapters` | GET | 章节列表 |
| `/api/stage-map` | GET | 闯关地图（层级 + 状态 + 掌握度）|
| `/api/practice-history` | GET | 练习历史 |
| `/api/reset_mastery` | POST | 重置用户掌握度 |
| `/api/reset` | POST | 重置整个数据库 |

### v2（新引擎）

| 端点 | 方法 | 说明 |
|:-----|:-----|:-----|
| `/api/recommend-v2` | POST | 路径规划器 Top-3 推荐（5类动作+评分）|
| `/api/submit-practice-v2` | POST | v2 提交（含补偿事件 L1-L4 检测+动量更新）|
| `/api/dim-mastery` | GET | 维度级掌握度全量数据 |
| `/api/problem-for-dim` | GET | 获取某维度的推荐题目 |

### 管理

| 端点 | 方法 | 说明 |
|:-----|:-----|:-----|
| `/api/admin/login` | POST | 管理员登录（env 配置账号）|
| `/api/admin/users` | GET | 所有用户 |
| `/api/admin/users/<id>` | DELETE | 删除用户 |

---

## 六、五类推荐动作（`path_planner.py`）

| 类型 | 条件 | 说明 |
|:-----|:------|:-----|
| `bottleneck` | mastery < 0.5 或 (mastery < 0.6 且 confidence < 5) | 薄弱维度突破 |
| `unlock` | 前置全部 ≥ 0.45 且自身 < 0.45 | 即将解锁的新维度 |
| `transfer` | 源维度 ≥ 0.6 且目标 < 0.5 | 利用迁移学习规律 |
| `recovery` | momentum < -0.3 且难度=1 的维度 | 动量恢复（简单题救命）|
| `discovery` | confidence ≤ 2 且难度 ≤ 2 | 探索未尝试领域 |

**评分** = reward / cost，top-3 返回。

---

## 七、六层补偿系统（L1–L4 from submit-practice-v2）

| 层级 | 触发条件 | 说明 |
|:-----|:---------|:-----|
| L1 | 每次提交练习 | 记录该维度的 mastery delta |
| L2 | 跨过 0.5/0.7 阈值 | 阈值突破事件 |
| L3 | 维度间传播 | 兄弟维度通过 skill_edges 获得增益 |
| L4 | 从 <0.3 跃升至 ≥0.5 | 严重瓶颈突破 |
| (L5) | 跨节点传播 | (todo) |
| (L6) | 串联补偿 | (todo) |

当前 `submit-practice-v2` 只实现了 L1, L2, L4（见 `app.py` submit_practice_v2）。L3 的传播已在 `database.py` 的 `propagate_to_siblings` 实现，但还没接到前端 API 回调事件中。

---

## 八、重要设计决策

### 8.1 双轨数据库更新

`update_mastery`（`database.py`）的更新链路：
1. 获取 node_id 对应的所有 dims
2. 对每个 dim 调用 `apply_bayesian_feedback` （更新 alpha/beta）
3. 如果 delta > 0，调用 `propagate_to_siblings` 传播增益（L3）
4. 重新计算该节点的衍生掌握度（维度加权平均）
5. 同步回 `user_mastery` 表

### 8.2 knowledge_nodes 的 23 条 vs skill_graph 的 43 个节点

- **knowledge_nodes**（23 条, 从旧版 CSV 导入）：高教版微积分精简大纲
- **skill_graph.json**（43 节点, 106 维度）：当前知识图谱，更精细
- 两者通过 `_fuzzy_match_node` 函数在 migration 时做模糊匹配

**迁移策略**：`database.py::migrate_skill_dimensions()` 将 skill_graph 的数据写入新表，旧 knowledge_nodes 表保留用于 v1 推荐兼容。

### 8.3 LLM 集成

- 模型：DeepSeek v4 Pro（通过 `deepseek-v4-pro` model name）
- API 封装在 `llm_api.py`：问答 / 出题 / 评估 三种模式
- 流式问答通过 SSE（`/api/ask/stream`）
- 知识边界由 `build_knowledge_boundary_prompt` 动态生成

---

## 九、知识图谱数据（`data/skill_graph.json`）

- **版本**：1.0
- **节点数**：43（覆盖 3 章：函数与极限 / 导数与微分 / 积分学）
- **维度数**：106
- **边数**：98（包括 transfer 边 + sibling 边）
- **edge_type**：transfer / sibling
- **problems.json**：20 道分步骤题（每道题 3-5 步）

---

## 十、已知问题 / 待办

### 待修复
1. **DATA_DIR 硬编码（已修复，2026-07-11）**：`engine/__init__.py` 现在根据文件位置解析 `../data`，不再依赖机器绝对路径。
2. **V2 前端未完成**：`/api/dim-mastery`, `/api/recommend-v2`, `/api/submit-practice-v2` 的后端已就绪，但前端 `RecommendationPanel.jsx` 和 `PracticeOverlay.jsx` 仍调用 v1 API
3. **补偿事件 L3 未接回前端**：`propagate_to_siblings` 在 database 层已实现，但 `submit-practice-v2` 的路由中未捕获并返回 L3 事件列表

### 待开发
4. **L5/L6 补偿**：跨节点传播和串联补偿尚未实现
5. **自适应难度阶梯**：当前 `problem-for-dim` 直接从 problems.json 选难度最近的题，未实现真正的 IRT 难度阶梯
6. **前端 v2 集成**：dashboard 需要展示维度级掌握度 vs 节点级掌握度的区分
7. **多用户并发**：当前 `_bg_processing` 集合做防抖，如果用户快速连续提问会丢失掌握度更新
8. **依赖声明缺口**：`llm_api.py` 使用 `python-dotenv`，但 `requirements.txt` 尚未声明；当前新建的后端 `.venv` 已显式安装 `python-dotenv==1.2.2`。
9. **Python 3.14 路径警告**：`database.py` 中 `instance\mathguide.db`、`data\knowledge_nodes.csv`、`data\prerequisites.csv` 使用普通反斜杠字符串，运行不受影响，但会产生 `SyntaxWarning`，后续应改用 `pathlib.Path` 或 `os.path.join`。

---

## 十一、启动方式

```bash
# Backend (Flask, 端口5000；已在 Python 3.14.6 验证)
cd D:\PythonProject\workspace\mathguide-backend
.venv\Scripts\activate
python app.py

# Frontend (Vite dev server, 端口5173)
cd D:\PythonProject\workspace\mathguide-frontend
npm run dev
```

当前机器的全局 `npm` 入口损坏，但项目本地依赖完整，可用以下等价命令启动前端：

```powershell
cd D:\PythonProject\workspace\mathguide-frontend
node node_modules\vite\bin\vite.js --host 127.0.0.1
```

### 12.1 2026-07-11 实际运行状态

- Backend：`http://127.0.0.1:5000`，`GET /api/nodes` 返回 200（23 个兼容层知识节点）
- Frontend：`http://127.0.0.1:5173`，首页返回 200
- Vite proxy：`GET http://127.0.0.1:5173/api/chapters` 返回 200
- 日志目录：`D:\PythonProject\runlogs\`（位于 Git 仓库外）

---

## 十二、这个项目由谁做了什么

### 我的工作（OpenClaw / Vivian — 2026-06-19～2026-07-10）

- **设计并实现了 Phase 1 原型框架**（`engine/__init__.py`）：SkillGraph 加载/查询、UserState 多维度状态管理（mastery/confidence/stuck/momentum）、ProblemEngine 分步骤题型引擎、PathPlanner 三类动作规划、Engine 编排的完整 L1-L4 补偿事件系统
- **设计 skill_graph.json 知识图谱**：43 节点、106 技能维度、98 条边的手写微积分知识库结构
- **设计了 Phase 2 数据库架构**：从 Phase 1 的内存原型→数据库持久化，包括 skill_dimensions/skill_edges/user_dim_params/user_meta 等表的设计
- **实现 database.py 全部数据库操作**：约 1780 行的 CRUD + Bayesian 更新 + 维度传播 + 迁移脚本
- **实现 path_planner.py**：DB 版的 5 类动作推荐引擎（bottleneck/unlock/transfer/recovery/discovery）+ 评分排序
- **实现 app.py 的 v2 API**：`/api/recommend-v2`, `/api/submit-practice-v2`, `/api/dim-mastery`, `/api/problem-for-dim`
- **写了 demo_cli.py**：3 个场景的端到端演示

### 之前的工作（其余开发者）

- `app.py` 的 v1 API（`/api/ask`, `/api/recommend`, `/api/generate-practice` 等基础端点）
- `llm_api.py` 的 DeepSeek 封装
- `recommend.py` 的 networkX 旧版推荐
- 前端 `mathguide-frontend/` 的全部 React 组件（Dashboard、Chat、Practice、StageMap 等页面）
- 初始的 SQLite schema 和 CSV 数据导入
- Postman 测试集合

### 我希望 Codex 接下来做的

见 `CLAUDE.md`（如果存在）或在 James 明确需求后制定计划。关键方向：
1. **前端 v2 集成** — 把 dimension-level mastery 展示接入 UI
2. **修复已知问题** — DATA_DIR 硬编码、L3 事件接回
3. **开发 L5/L6** — 跨节点传播和串联补偿
4. **自适应难度阶梯** — 真正的 IRT/难度自适应出题
