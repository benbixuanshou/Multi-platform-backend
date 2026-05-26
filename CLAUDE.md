# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

面向个人创作者的 AI-native 跨平台评论管理工具。覆盖小红书、抖音、B站。5 个 Agent 协作驱动（非规则引擎），Harness Engineering 自建框架（无 LangChain）。

[README.md](README.md) — 项目介绍 + 快速开始
[golden-seeking-lobster.md](golden-seeking-lobster.md) — 完整技术方案（十四章节，~2400 行）
[ARCHITECTURE.md](ARCHITECTURE.md) — 系统架构全景图
[DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) — 8 Phase 开发计划（每 Phase 独立测试门）

**当前状态：Phase 0 完成（MySQL/Redis/Milvus 全部 healthy），下一步 Phase 1 — FastAPI 骨架 + JWT 认证。**

### Skills

项目 `.claude/skills/` 下有 3 个开发工作流 Skill，Claude Code 自动按需加载：
- `agent-prompt-review` — 审查 Agent System Prompt 的完整性和规范性
- `migration-review` — 审查 MySQL DDL 是否符合项目 Schema 规范
- `harness-component-generator` — 按项目接口规范生成新 Hook/Provider/Tool

## 技术栈

FastAPI / Next.js 14 / MySQL 8.0 / Redis 7 / Milvus 2.5 / Docker Compose / DeepSeek API
**不用 LangChain** — Agent Loop、HookPipeline、ToolRegistry 全部手写。

## 常用命令

```bash
# 环境启动
docker compose up -d mysql redis milvus etcd          # 启动存储层
docker compose up -d                                   # 启动全部 6 个 service
docker compose down                                    # 停止

# 数据库初始化（首次）
mysql -h 127.0.0.1 -u root -p < backend/migrations/001_initial_schema.sql
python backend/migrations/002_milvus_collections.py

# 后端
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000                  # 开发模式

# 前端
cd frontend
npm install && npm run dev                             # :3000

# 扩展
cd extension
npm install && npm run dev                             # Plasmo dev mode

# 测试
pytest tests/ -v                                       # 全部测试
pytest tests/phase2_harness/ -v                        # 单 Phase 测试
python tests/phase3_classify_eval.py                   # 分类 eval set 跑分
python tests/phase5_e2e.py                             # 端到端测试

# API 文档
open http://localhost:8000/docs                        # Swagger UI
```

## 核心架构

### 5 个 Agent 的协作链路（混合范式）

Agent 采用混合范式：基座是 **ReAct**（带 verify 增强），核心亮点是 **Reflection**（Generator→Critic→Generator 循环），编排层用 **Routing**，离线分析用 **Plan-and-Execute**。详见 [golden-seeking-lobster.md §4.0](golden-seeking-lobster.md)。

```
实时链路：
  评论入库 → ClassifyRouterAgent（分类+意图+路由）
                │
                ├── spam/neutral → 跳过
                └── 需回复 → ReplyGenerateAgent（生成 3 草案）
                                │
                                ▼
                        ReplyCriticAgent（评价草案质量）
                          ├── all_good → 展示给创作者
                          └── needs_regeneration → 回 ReplyGenerateAgent（最多 1 次）

离线链路（每周）：
  InsightMiningAgent（聚合分析）→ ContentStrategyAgent（洞察→行动建议）
```

### 三层数据架构

| 存储 | 职责 |
|---|---|
| MySQL 8.0 | 所有业务表（9 张）+ Agent 任务队列（`FOR UPDATE SKIP LOCKED` 轮询） |
| Redis 7 | 限流计数、上下文缓存、熔断状态、扩展去重缓冲、指标缓存 |
| Milvus 2.5 | 评论向量检索、编辑记录相似搜索、跨平台用户匹配（后期） |

### Harness 组件（自建，替代 LangChain）

| 组件 | 职责 |
|---|---|
| AgentRunner | observe→plan→act→verify→output 模板方法 |
| HookPipeline | pre_model / post_model / on_error 五阶段 hook 注入 |
| ModelProvider | 可替换 LLM 抽象，改配置切模型 |
| EmbeddingProvider | 可替换 Embedding 抽象，当前 bge-large-zh（本地免费） |
| ContextBuilder | 三层上下文组装 + 分级压缩 |
| ToolRegistry | 工具注册 + 超时 + fallback |
| CircuitBreaker | 滑动窗口熔断（Redis 计数） |
| TraceRecorder | 工作记忆 + 决策审计链 |

### Agent Tasks 表作为 Agent 间唯一通信媒介

Agent 之间不直接调用，通过 `agent_tasks` 表解耦。ClassifyRouter 创建 Reply 任务 → ReplyGenerate 轮询取任务 → 写完 result。任务状态枚举：`pending → processing → processing_checkpoint → done | failed | cancelled | pending_manual`。

### PlatformAdapter 接口

加新平台只需实现 `PlatformAdapter` 接口。三个适配器：XhsAdapter → DouyinAdapter → BilibiliAdapter。浏览器扩展通过 `POST /api/internal/comments/batch` 上报评论。

## 关键设计决策

- **不自动发送**：Agent 写到 reply_drafts，创作者手动确认发送。这是安全约束不是偏好设置
- **ModelProvider + EmbeddingProvider 抽象**：LLM 和 Embedding 都可替换。LLM 当前 DeepSeek V4 Pro，Embedding 当前 bge-large-zh（本地免费）
- **Classify 用轻量模型、Reply 用强模型**：分开后可独立扩容、独立计费
- **MVP 不做**：跨平台粉丝识别、SSE（用轮询）、Playwright 定时任务、自动发送、移动端 App
- **SFT 后期做**：`is_adopted`/`is_edited` 自动积累训练数据，微调替代 API 调用降低成本
