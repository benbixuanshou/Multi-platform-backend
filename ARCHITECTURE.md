# 系统架构全景

## 整体架构图

```
创作者浏览器                          创作者浏览器
    │                                      │
    │  小红书/抖音/B站 页面                  │  Dashboard 页面
    │                                      │
    ▼                                      ▼
┌─────────────────────┐       ┌──────────────────────────────┐
│   Browser Extension │       │     Next.js Frontend          │
│                     │       │                              │
│ ┌─────────────────┐ │       │ ┌──────────────────────────┐ │
│ │ Content Scripts │ │       │ │ Dashboard (核心)          │ │
│ │ ─ DOM 解析      │ │       │ │ • CommentFeed (虚拟滚动)  │ │
│ │ ─ MutationObsv  │ │       │ │ • ReplyDraftPanel         │ │
│ │ ─ 三个平台      │ │       │ │ • FilterSidebar           │ │
│ └────────┬────────┘ │       │ └────────────┬─────────────┘ │
│          │          │       │ ┌────────────┴─────────────┐ │
│ ┌────────┴────────┐ │       │ │ TanStack Query           │ │
│ │Background Worker│ │       │ │ (30s 轮询 + 缓存)        │ │
│ │ ─ 批量聚合      │ │       │ └────────────┬─────────────┘ │
│ │ ─ 去重缓冲      │ │       │              │               │
│ │ ─ Cookie 加密   │ │       │  Analytics / Settings / Login│
│ └────────┬────────┘ │       └──────────────┼───────────────┘
└──────────┼──────────┘                      │
           │                                 │
     POST /api/internal/comments/batch       │ REST API
     (HTTPS + crypto)                        │ (JWT Bearer)
           │                                 │
           └────────────┬────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────┐
│                  FastAPI Backend (:8000)                   │
│                                                            │
│  ┌─────────┐ ┌──────────┐ ┌───────┐ ┌────────┐ ┌───────┐│
│  │ Auth    │ │ Comments │ │Drafts │ │Batch   │ │Analytics││
│  │ 4 routes│ │ 5 routes │ │5 rt   │ │2 rt    │ │2 routes││
│  └────┬────┘ └────┬─────┘ └───┬───┘ └───┬────┘ └───┬───┘│
│       └───────────┼───────────┼─────────┼──────────┼─────│
│                   │     ┌─────┴─────┐   │          │     │
│                   │     │ Services  │   │          │     │
│                   │     │ Layer     │   │          │     │
│                   │     └─────┬─────┘   │          │     │
├───────────────────┼───────────┼─────────┼──────────┼─────┤
│                   │           │         │          │     │
│            ┌──────┴───────────┴─────────┴──────────┴──┐  │
│            │           Agent Worker (独立进程)         │  │
│            │                                           │  │
│            │  ┌───────────────────────────────────┐   │  │
│            │  │         AgentRunner               │   │  │
│            │  │   observe→plan→act→verify→output  │   │  │
│            │  └───────────────┬───────────────────┘   │  │
│            │                  │                       │  │
│            │  ┌───────────────┴───────────────────┐   │  │
│            │  │          HookPipeline              │   │  │
│            │  │  pre_model → post_model → on_error │   │  │
│            │  └───────────────┬───────────────────┘   │  │
│            │                  │                       │  │
│            │  ┌──────┐ ┌──────┴──────┐ ┌──────────┐  │  │
│            │  │Model │ │Classify/    │ │Tool      │  │  │
│            │  │Provdr│ │Reply/Insight│ │Registry  │  │  │
│            │  └──┬───┘ └──────┬──────┘ └────┬─────┘  │  │
│            │     │            │              │        │  │
│            │  ┌──┴────────────┴──────────────┴──┐     │  │
│            │  │  ContextBuilder                 │     │  │
│            │  │  CircuitBreaker                 │     │  │
│            │  │  TraceRecorder                  │     │  │
│            │  └─────────────────────────────────┘     │  │
│            └──────────────────────────────────────────┘  │
│                                                            │
│  ┌──────────────────────────────────────────────────┐     │
│  │            Data Access Layer                      │     │
│  │  MySQL(业务) + Redis(缓存/控制) + Milvus(向量)    │     │
│  └──────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────┘
                        │
            ┌───────────┼───────────┐
            ▼           ▼           ▼
        ┌──────┐  ┌───────┐  ┌────────┐
        │MySQL │  │ Redis │  │ Milvus │
        │8.0   │  │ 7     │  │ 2.5    │
        │      │  │       │  │        │
        │9张表 │  │6种Key │  │3个Coll │
        └──────┘  └───────┘  └────────┘
```

## 数据流向（一条评论的完整旅程）

```
1. 创作者打开小红书 → Content Script 注入
2. MutationObserver 检测到新评论 → 解析 DOM → RawComment
3. Background Worker 聚合 → 去重 → POST /api/internal/comments/batch
4. API 校验 → INSERT MySQL (comments + posts)
5. 异步：调 Embedding API → INSERT Milvus (comment_embeddings)
6. INSERT agent_tasks (type='classify', priority=0)
7. Worker 轮询 → ClassifyRouterAgent 取任务
8. Classify: observe(post+comment) → plan → act(LLM) → verify(JSON+schema)
9. 更新 comments.classification/intent/urgency
10. 创建下游 task: type='reply' (或 insight/spam→结束)
11. Worker 轮询 → ReplyGenerateAgent 取任务
12. Reply: observe(post+comment+history+相似回复) → plan → act(LLM) → verify(SafetyCheck)
13. ReplyCriticAgent 评价草稿 → all_good / needs_regeneration（↓ 回到 11）
14. INSERT reply_drafts (3 条)
15. 前端轮询刷新 → 看到草稿
16. 创作者选择/编辑/点发送
17. POST /api/drafts/:id/send → 调 send_reply → 更新 sent_at

离线（每周）：
  InsightMiningAgent 聚合分析 → ContentStrategyAgent 转化为行动建议 → 展示在 Dashboard

全过程 trace 记录在 agent_tasks.payload.trace
```

## 组件职责总览

| 组件 | 文件 | 职责 | 依赖 |
|---|---|---|---|
| AgentRunner | harness/agent_runner.py | observe→plan→act→verify→output 模板 | HookPipeline |
| HookPipeline | harness/hook_pipeline.py | 5 阶段 hook 管道 | hooks |
| ModelProvider | harness/model_provider.py | LLM 抽象，改配置切换 | — |
| EmbeddingProvider | harness/embedding_provider.py | Embedding 抽象，当前 bge-large-zh（本地免费） | — |
| ContextBuilder | harness/context_builder.py | 三层上下文组装+预算+压缩 | ModelProvider(小模型) |
| ToolRegistry | harness/tool_registry.py | 工具注册+执行+超时 | — |
| CircuitBreaker | harness/circuit_breaker.py | 滑动窗口熔断 | Redis |
| TraceRecorder | harness/trace_recorder.py | 工作记忆+决策审计 | — |
| SafetyCheckHook | harness/hooks/safety_check.py | 禁止词/长度/空内容 | — |
| SchemaValidationHook | harness/hooks/schema_validation.py | JSON格式/必填字段 | — |
| BaseAgent | agents/base.py | Agent 骨架（prompt+parse） | 以上全部 |
| ClassifyRouterAgent | agents/classify_router.py | 分类+意图+路由 | BaseAgent+ToolRegistry |
| ReplyGenerateAgent | agents/reply_generate.py | 3 风格回复草稿 | BaseAgent+ToolRegistry |
| ReplyCriticAgent | agents/reply_critic.py | 评价草稿质量，触发重生成 | BaseAgent |
| InsightMiningAgent | agents/insight_mining.py | 周报聚合分析 | BaseAgent |
| ContentStrategyAgent | agents/content_strategy.py | 洞察→行动建议 | BaseAgent（消费InsightMining输出） |
| XhsAdapter | adapters/xhs.py | 小红书抓取+发送 | PlatformAdapter |

## 数据库职责分配

| 存储 | 存什么 | 谁写 | 谁读 |
|---|---|---|---|
| MySQL (9 表) | 所有业务数据、任务队列、日志 | API + Worker | API + Worker + 前端(通过API) |
| Redis (6 类Key) | 限流、缓存、熔断、去重、指标 | Worker | Worker + API |
| Milvus (3 Coll) | 评论向量、编辑记录向量、用户向量 | Worker(异步) | Worker(检索时) |
