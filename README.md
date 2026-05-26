# 多 Agent 评论管理平台

**AI-native 跨平台评论管理工具 — 5 个 Agent 协作，帮创作者理解粉丝、写好回复。**

覆盖小红书 · 抖音 · B站 | FastAPI + Next.js + MySQL + Redis + Milvus | 自建 Agent 框架（无 LangChain）

---

## 为什么选这个？

现有评论管理工具分两类：浏览器扩展（只有前端，没有分析）和企业客服平台（规则引擎，不服务个人）。**没有一个产品把 AI Agent 当核心引擎来设计。**

| | 本项目 | 浏览器扩展类 | 企业平台类 |
|---|---|---|---|
| AI 引擎 | **5 Agent 协作** | 单次 LLM 调用 | 关键词匹配 |
| 评论洞察挖掘 | ✅ 趋势/选题/粉丝关切 | ❌ | ❌ |
| 创作者人设学习 | ✅ 从编辑中学习 | ❌ | ❌ |
| 回复质量自检 | ✅ Generator→Critic 循环 | ❌ | ❌ |
| 面向个人创作者 | ✅ | ✅ | ❌（企业定价） |
| 数据飞轮（SFT） | ✅ 自动积累训练数据 | ❌ | ❌ |

---

## 系统架构

### 5 Agent 协作链路

```
实时链路：
  评论入库 → ClassifyRouterAgent（分类+意图）
                ├── spam/neutral → 跳过
                └── 需回复 → ReplyGenerateAgent（3 种风格草稿）
                                ↓
                        ReplyCriticAgent（评价草稿质量）
                          ├── all_good → 展示给创作者
                          └── needs_regeneration → 重新生成

离线链路（每周）：
  InsightMiningAgent（挖掘趋势/UGC/粉丝关切）
         ↓
  ContentStrategyAgent（洞察 → 可执行的行动建议）
```

### 三层数据架构

| 存储 | 职责 |
|---|---|
| MySQL 8.0 | 业务数据 + Agent 任务队列（`FOR UPDATE SKIP LOCKED`） |
| Redis 7 | 限流 / 上下文缓存 / 熔断状态 / 去重缓冲 |
| Milvus 2.5 | 评论语义搜索 / 编辑记录相似检索 |

### Harness 工程化（自建，替代 LangChain）

Agent = Model + Harness。模型只提供推理，Harness 把状态、工具、反馈、安全边界串起来。

| 组件 | 职责 |
|---|---|
| AgentRunner | observe→plan→act→verify→output 模板方法 |
| HookPipeline | pre_model / post_model / on_error 五阶段 hook 注入 |
| ModelProvider | 可替换 LLM 抽象，改配置切模型 |
| EmbeddingProvider | 可替换 Embedding 抽象（bge-large-zh 本地免费） |
| ContextBuilder | 三层上下文组装 + 分级压缩 |
| CircuitBreaker | 滑动窗口熔断 |
| TraceRecorder | 工作记忆 + 决策审计链 |

---

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 20+
- Docker + Docker Compose
- DeepSeek API Key

### 60 秒启动

```bash
# 1. 克隆项目
git clone https://github.com/benbixuanshou/Multi-platform-backend.git
cd Multi-platform-backend

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 DeepSeek API Key

# 3. 启动所有服务
docker compose up -d

# 4. 初始化数据库
docker compose exec mysql mysql -u root -p comment_platform < backend/migrations/001_initial_schema.sql
python backend/migrations/002_milvus_collections.py

# 5. 启动后端
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 6. 启动前端（新终端）
cd frontend && npm install && npm run dev

# 打开 http://localhost:3000
```

---

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | FastAPI (Python) |
| 前端 | Next.js 14 + React + TanStack Query |
| 扩展 | Plasmo (浏览器扩展) |
| 数据库 | MySQL 8.0 + Redis 7 + Milvus 2.5 |
| LLM | DeepSeek V4 Pro（ModelProvider 可替换） |
| Embedding | bge-large-zh（本地免费，中文最强） |
| 部署 | Docker Compose + Caddy |
| AI 框架 | **不用 LangChain** — 全部手写 |

---

## 项目结构

```
├── backend/         FastAPI + Agent 引擎 + Worker
│   ├── agents/      5 个 Agent（Classify/Reply/Critic/Insight/Strategy）
│   ├── harness/     7 个通用组件 + 2 个 Hook
│   ├── adapters/    平台适配器（XHS/Douyin/Bilibili）
│   ├── api/         27 个 REST 接口
│   ├── worker/      Agent 主循环
│   └── migrations/  MySQL DDL + Milvus 脚本
├── frontend/        Next.js Dashboard
├── extension/       Plasmo 浏览器扩展
├── .claude/skills/   Claude Code 开发工作流 Skill（prompt审查/migration审查/组件生成）
└── docs/            设计文档（见下方链接）
```

---

## 文档

- [完整技术方案](golden-seeking-lobster.md) — 十四章节，数据模型 + API Schema + Agent Prompt + 10 个 Harness 模块设计
- [系统架构](ARCHITECTURE.md) — 架构全景图 + 数据流向
- [开发计划](DEVELOPMENT_PLAN.md) — 8 Phase，每 Phase 独立测试门

---

## 开发路线

| Phase | 内容 | 状态 |
|---|---|---|
| 0 | 环境搭建 + 数据库初始化 | ✅ 完成 |
| 1 | FastAPI 骨架 + JWT 认证 | ✅ 完成 |
| 2 | Harness 组件（AgentRunner/HookPipeline 等） | 🚧 下一步 |
| 3 | ClassifyRouterAgent + eval set 验证 | ⬜ |
| 4 | ReplyGenerateAgent + ReplyCriticAgent | ⬜ |
| 5 | Worker 主循环 + 全链路联调 | ⬜ |
| 6 | 前端 Dashboard | ⬜ |
| 7 | 浏览器扩展（小红书 DOM 解析） | ⬜ |
| 8 | 多平台 + InsightMining + 部署 | ⬜ |

---

## License

MIT
