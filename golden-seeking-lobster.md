# 多 Agent 评论管理平台 — 完整技术方案

## 团队条件
- 一人全栈，覆盖前后端 + 基础设施 + Agent 引擎
- 有浏览器扩展开发经验
- 有 LLM API 实际调用经验
- 预计投入：日均 3-4 小时（个人项目节奏，不设硬死线）

---

## 技术选型

| 层 | 选型 | 说明 |
|---|---|---|
| 后端框架 | FastAPI (Python 3.12+) | LLM SDK 生态最强，async 原生，自动 OpenAPI |
| 前端框架 | Next.js 14 App Router + React + Tailwind CSS + TanStack Query | Dashboard 类 CSR，轮询替代 SSE |
| 浏览器扩展 | Plasmo + React | 与前端统一技术栈，Manifest V3 自动管理 |
| 关系数据库 | **MySQL 8.0** | 团队已会，所有业务表 + 轮询任务队列 |
| 缓存 | **Redis 7** | 限流 + 上下文缓存 + 熔断状态 + 去重缓冲 + 指标缓存 |
| 向量数据库 | **Milvus (standalone)** | 评论向量检索 + 编辑记录相似搜索 |
| AI 框架 | **不用 LangChain** | Agent Loop / HookPipeline / ToolRegistry 手写，100 行内完成 |
| ORM | SQLAlchemy 2.0 async + Alembic | 支持 MySQL |
| 部署 | Docker Compose | 6 个 service：api / worker / frontend / mysql / redis / milvus |
| CI/CD | GitHub Actions | push → lint → test → build image |
| 监控 | Sentry（免费 tier） | 错误监控，后期加 Grafana Loki |

### 三层数据职责

```
MySQL（关系逻辑 + 所有业务数据）
  ├── users, comments, agent_tasks, reply_drafts, reply_edit_log, ...
  ├── Agent 任务队列（FOR UPDATE SKIP LOCKED）
  └── 全文搜索（comment 关键词）

Redis（热数据 + 控制面）
  ├── 限流计数器（RateLimitHook）
  ├── 上下文缓存（System Prompt + 人设 + 平台规则）
  ├── 扩展去重缓冲（1 秒窗口）
  ├── 熔断器状态（窗口计数）
  └── 仪表盘指标缓存（5 分钟刷新）

Milvus（语义搜索，Agent 层使用）
  ├── 评论向量检索（相似回复 → 模块 1）
  ├── 编辑记录向量检索（相似编辑 → 模块 4）
  └── 跨平台用户匹配（CrossPlatformLinkAgent → 后期）
```

### 数据库 schema 适配说明

当前文档中所有 SQL schema 使用 PostgreSQL 语法。MySQL 8.0 适配：
- `UUID` → `CHAR(36)`（MySQL 8.0 支持 `UUID()` 函数）
- `JSONB` → `JSON`
- `TIMESTAMPTZ` → `TIMESTAMP`
- `vector(1536)` → 去掉（向量存 Milvus），comments 表移除 `content_embedding` 字段，reply_edit_log 表移除 `diff_embedding` 字段
- `gen_random_uuid()` → `UUID()`

---

## 一、数据模型（地基）

### 1.1 核心实体关系

```
User (我们的用户/创作者)
  │
  ├── PlatformAccount (创作者在各平台的账号绑定)
  │     ├── platform: xhs | douyin | bilibili
  │     ├── access_token / refresh_token
  │     └── platform_user_id
  │
  ├── Post (创作者发布的笔记/视频)
  │     ├── platform_post_id
  │     ├── platform: xhs | douyin | bilibili
  │     └── title, url, thumbnail
  │
  └── Comment (标准化后的评论)
        ├── post_id → Post
        ├── platform_user_id (评论者的平台ID)
        ├── parent_comment_id (回复链)
        ├── content, like_count, created_at
        │
        ├── AgentTask (多条，一条评论可触发多个 Agent)
        │     ├── task_type: classify | reply | insight | link
        │     ├── status: pending → processing → done | failed
        │     ├── payload (输入)
        │     └── result (输出)
        │
        └── ReplyDraft (AI 生成的回复草稿)
              ├── agent_task_id → AgentTask
              ├── style: professional | casual | warm
              ├── content
              ├── is_adopted, is_edited
              └── sent_at (实际发送时间)
```

### 1.2 完整 SQL Schema

```sql
-- 用户表
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(128),
    -- 创作者人设配置
    creator_tone VARCHAR(32) DEFAULT 'casual',       -- professional | casual | warm | humorous
    creator_phrases TEXT,                             -- 常用口头禅，Reply Agent 会参考
    creator_bio TEXT,                                 -- 个人简介，帮助 Agent 理解人设
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 平台账号绑定
CREATE TABLE platform_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform VARCHAR(32) NOT NULL,                    -- 'xhs', 'douyin', 'bilibili'
    platform_user_id VARCHAR(128) NOT NULL,            -- 平台侧的用户 ID
    platform_username VARCHAR(128),
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TIMESTAMPTZ,
    cookie_data JSONB,                                 -- 浏览器扩展同步的 cookie（加密存储）
    is_active BOOLEAN DEFAULT true,
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, platform)
);

-- 创作者发布的内容（笔记/视频）
CREATE TABLE posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform VARCHAR(32) NOT NULL,
    platform_post_id VARCHAR(128) NOT NULL,
    title TEXT,
    url TEXT,
    thumbnail_url TEXT,
    published_at TIMESTAMPTZ,
    comment_count INT DEFAULT 0,
    last_comment_fetch_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(platform, platform_post_id)
);

-- 标准化评论（核心表）
CREATE TABLE comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    platform VARCHAR(32) NOT NULL,
    platform_comment_id VARCHAR(128) NOT NULL,         -- 平台侧评论 ID，用于去重
    parent_comment_id UUID REFERENCES comments(id),    -- 回复链（我们的内部 ID）
    parent_platform_comment_id VARCHAR(128),            -- 平台侧父评论 ID
    -- 评论者信息
    platform_user_id VARCHAR(128) NOT NULL,             -- 平台侧用户 ID
    platform_username VARCHAR(256),
    platform_avatar_url TEXT,
    -- 内容
    content TEXT NOT NULL,
    image_urls JSONB DEFAULT '[]',                     -- 评论带图
    -- 元数据
    like_count INT DEFAULT 0,
    reply_count INT DEFAULT 0,
    is_from_creator BOOLEAN DEFAULT false,              -- 是否是创作者本人发的
    is_pinned BOOLEAN DEFAULT false,                    -- 是否被置顶
    -- 我们的处理状态
    status VARCHAR(32) DEFAULT 'pending',               -- pending | classified | replied | ignored | spam
    classification VARCHAR(32),                          -- question | complaint | praise | spam | neutral | ugc_gold
    sentiment VARCHAR(16),                               -- positive | negative | neutral
    urgency VARCHAR(16),                                 -- high | medium | low
    -- 向量（跨平台用户匹配）
    content_embedding vector(1536),                      -- pgvector，用于语义搜索和跨平台匹配
    -- 时间
    platform_created_at TIMESTAMPTZ,                     -- 评论在平台上的原始时间
    fetched_at TIMESTAMPTZ DEFAULT now(),                -- 我们抓取到的时间
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(platform, platform_comment_id)
);

CREATE INDEX idx_comments_post_status ON comments(post_id, status);
CREATE INDEX idx_comments_platform_user ON comments(platform, platform_user_id);
CREATE INDEX idx_comments_fetched ON comments(fetched_at DESC);

-- Agent 任务表（Agent 间通信的唯一媒介）
CREATE TABLE agent_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    comment_id UUID REFERENCES comments(id) ON DELETE CASCADE,
    task_type VARCHAR(64) NOT NULL,         -- 'classify' | 'reply' | 'insight' | 'cross_platform_link'
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    priority INT NOT NULL DEFAULT 0,        -- 越大越优先，负面评论直接设 100
    payload JSONB NOT NULL DEFAULT '{}',    -- 输入
    result JSONB,                           -- 输出（Agent 结果）
    agent_name VARCHAR(64),                 -- 哪个 Agent 处理的
    llm_model VARCHAR(64),
    llm_tokens INT,
    llm_duration_ms INT,
    error_message TEXT,
    retries INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    created_at TIMESTAMPTZ DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- 高效取任务的索引（只扫描 pending 行）
CREATE INDEX idx_agent_tasks_fetch ON agent_tasks (task_type, status, priority DESC, created_at)
    WHERE status IN ('pending', 'processing_checkpoint');

-- status 枚举：
--   pending → processing → processing_checkpoint → done | failed | cancelled | pending_manual
--   processing_checkpoint: Agent 的 act 完成后写 checkpoint，Worker 崩溃可从此恢复
--   cancelled: 创作者手动标 spam → 级联取消下游任务
--   pending_manual: 所有自动恢复耗尽，标记人工处理

-- 僵尸任务清理（定时任务，每分钟）
-- UPDATE agent_tasks SET status='pending', retries=retries+1
-- WHERE status='processing' AND started_at < now() - interval '5 minutes';
-- UPDATE agent_tasks SET status='processing'
-- WHERE status='processing_checkpoint' AND started_at < now() - interval '5 minutes';

-- AI 回复草稿表
CREATE TABLE reply_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    comment_id UUID NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    agent_task_id UUID REFERENCES agent_tasks(id),
    style VARCHAR(32) NOT NULL,             -- 'professional' | 'casual' | 'warm'
    content TEXT NOT NULL,
    is_adopted BOOLEAN DEFAULT false,       -- 用户是否采用了这个草稿
    is_edited BOOLEAN DEFAULT false,        -- 采用后是否编辑过
    edited_content TEXT,                    -- 编辑后的内容
    sent_at TIMESTAMPTZ,                    -- 实际发送时间
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Agent 执行日志
CREATE TABLE agent_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name VARCHAR(64) NOT NULL,
    task_id UUID REFERENCES agent_tasks(id),
    model VARCHAR(64) NOT NULL,
    prompt_version VARCHAR(32),               -- 模块 9：Prompt 版本号，用于 A/B 对比
    prompt_tokens INT NOT NULL,
    completion_tokens INT NOT NULL,
    total_tokens INT NOT NULL,
    duration_ms INT NOT NULL,
    confidence DECIMAL(3,2),                   -- 模块 10：分类/生成的置信度
    tool_name VARCHAR(64),                     -- 模块 2：工具调用记录
    tool_duration_ms INT,                      -- 模块 2：工具耗时
    checkpoint BOOLEAN DEFAULT false,          -- 模块 3：是否有检查点
    cost_estimate_usd DECIMAL(10,6),
    success BOOLEAN NOT NULL,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_agent_logs_agent ON agent_logs(agent_name, created_at DESC);
CREATE INDEX idx_agent_logs_tool ON agent_logs(tool_name, created_at DESC);
```

-- 情节记忆：AI 草稿被创作者编辑的记录
CREATE TABLE reply_edit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    comment_id UUID REFERENCES comments(id),
    original_draft TEXT NOT NULL,
    edited_content TEXT NOT NULL,
    classification VARCHAR(32),
    intent VARCHAR(32),
    diff_summary TEXT,                         -- 轻量模型总结编辑模式
    diff_embedding vector(1536),               -- pgvector 索引，用于相似检索
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_edit_log_intent_time ON reply_edit_log(intent, created_at DESC);
CREATE INDEX idx_edit_log_embedding ON reply_edit_log USING ivfflat(diff_embedding vector_cosine_ops);

-- 回复效果追踪（MVP 第三刀，表结构预留）
CREATE TABLE reply_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_id UUID REFERENCES reply_drafts(id),
    likes_before INT,
    likes_after INT,
    replies_before INT,
    replies_after INT,
    checked_at TIMESTAMPTZ DEFAULT now()
);

### 1.3 为什么这样设计

- **comment 和 agent_tasks 分离**：一条评论可能触发多次 Agent 处理（失败重试、重新分类），用任务表解耦
- **content_embedding 放在 comments 表上**：避免 JOIN，pgvector 直接索引
- **reply_drafts 独立成表**：用户可以一次生成、多次查看、事后编辑，需要持久化
- **agent_logs 和 agent_tasks 分开**：logs 是时序数据（会很多），tasks 是状态机，读写模式不同
- **platform_comment_id + platform 联合唯一**：去重的关键

### 1.4 Milvus Collection 设计

**Collection 1：comment_embeddings**

用途：模块 1 相似回复检索。

```
Fields:
  comment_id    VARCHAR(36)        PK，对应 MySQL comments.id
  embedding     FLOAT_VECTOR(1536)
  platform      VARCHAR(32)        index
  post_id       VARCHAR(36)        index
  status        VARCHAR(32)        index  ← 只搜已回复的

Index: IVF_FLAT + COSINE (nlist=128)

查询：当前评论向量 → filter='status=="replied" && post_id=="..."' → top 5
```

**Collection 2：edit_log_embeddings**

用途：模块 4 情节记忆检索。

```
Fields:
  edit_log_id   VARCHAR(36)        PK，对应 MySQL reply_edit_log.id
  embedding     FLOAT_VECTOR(1536)
  intent        VARCHAR(32)        index  ← 按意图过滤
  created_at    INT64              timestamp  ← 时间衰减加权

Index: IVF_FLAT + COSINE

查询：当前评论向量 → filter='intent=="purchase_intent"' → top 3
```

**Collection 3：user_identity_embeddings（后期）**

用途：CrossPlatformLinkAgent 跨平台用户匹配。MVP 不做，Collection 预留。

### 1.5 Redis 数据结构

| Key | Type | 用途 | TTL |
|---|---|---|---|
| `rate:{agent}:{minute}` | string | RateLimitHook 计数器 | 60s |
| `ctx:{user_id}:{platform}:static` | hash | 上下文缓存（System Prompt + 人设 + 平台规则） | 1h |
| `jwt_bl:{token_jti}` | string | JWT 黑名单 | token 过期时间 |
| `dedup:{platform}:{batch}` | set | 扩展上报去重缓冲 | 5min |
| `cb:{agent}:window` | hash | CircuitBreaker 状态（success/failure/state） | 5min |
| `stats:{user_id}:dashboard` | hash | 仪表盘指标缓存 | 5min |

---

## 二、评论全生命周期（核心链路）

### 2.1 完整状态机

```
[平台评论区]
     │
     ▼
① DISCOVERY ─── PlatformMonitorAgent 或浏览器扩展发现新评论
     │
     ▼
② FETCH ─────── 通过 API 或 DOM 抓取评论原始数据
     │
     ▼
③ NORMALIZE ─── PlatformAdapter 将平台特定格式 → 标准化 Comment 对象
     │
     ▼
④ DEDUP ─────── 按 (platform, platform_comment_id) 去重，已存在的跳过
     │
     ▼
⑤ STORE ─────── INSERT INTO comments，status = 'pending'
     │             同时生成 embedding（调用 embedding API）
     │
     ▼
⑥ ENQUEUE ───── INSERT INTO agent_tasks (task_type='classify', priority=0)
     │
     ▼
⑦ CLASSIFY ──── ClassifyRouterAgent
     │            ├── observe: 读评论 + 帖子上下文 + 父评论
     │            ├── plan: 信息不够 → 调 get_post_context 工具
     │            ├── act: LLM 分类（轻量模型，15s 超时）
     │            ├── verify: JSON 校验 + category/intent 枚举 + 置信度检查
     │            ├── 置信度高 → 更新 comment + 创建下游任务
     │            ├── 置信度中 → 更新 comment + 低优先级任务 + 标记
     │            ├── 置信度低 → pending_manual_review，不创建下游
     │            └── 挂了 → 降级到规则引擎
     │
     ▼
⑧ REPLY GEN ─── ReplyGenerateAgent
     │            ├── observe: 读评论 + 帖子 + 同帖子回复 + 用户历史
     │            ├── plan: 判断该不该回（引战/敏感 → needs_human）
     │            ├── act: LLM 生成 3 种风格草稿（强推理模型，30s 超时）
     │            ├── verify: SafetyCheckHook（禁止词/长度）+ SchemaValidationHook
     │            ├── 通过 → 写 reply_drafts
     │            ├── 有警告 → 写 reply_drafts + risk_warning
     │            ├── 判断不该回 → needs_human
     │            └── 挂了 → 重试 3 次 → pending_manual
     │
     ▼
⑨ REVIEW ────── 前端展示评论 + 草稿，创作者选择/编辑/忽略
     │
     ▼
⑩ SEND ──────── 创作者点击发送 → API/扩展发回复到平台 → reply_drafts.sent_at 更新
     │             comment.status = 'replied'
     │
     ▼
⑪ TRACK ─────── 定时回查评论互动数据（回复后的点赞/回复数），形成闭环数据
```

### 2.2 关键设计决策

**为什么 classify 和 reply 是两个独立 Agent？**
- 分类是轻量任务，用便宜的模型就能做（如 DeepSeek-V3），后期可微调 0.5B 小模型替代 API
- 回复生成是重量任务，需要更强的推理能力（如 DeepSeek-R1），后期可微调 7B 模型替代大部分调用
- 分开后可独立扩容、独立计费、独立调 Prompt
- 如果分类结果是不需要回复（spam/praise），直接省掉一次 LLM 调用的费用
- **ModelProvider 抽象**：Agent 不直接绑定具体模型，通过 Provider 接口调用，改配置切换模型

**为什么先从 classify 开始而不是直接生成回复？**
- 先分类才能决定优先级 → 负面评论优先处理
- 先分类才能决定是否需要回复 → spam 直接跳过
- 先分类才能给 Reply Agent 提供上下文 → "这是一条产品咨询，用专业风格回复"

---

## 三、平台适配器设计

### 3.1 双通道数据获取策略

```
平台评论获取
    │
    ├── 通道 A: 官方 API（首选）
    │     优势：稳定、合规、可后台运行
    │     劣势：小红书/抖音 API 权限难申请，数据字段有限
    │     适用：B 站（API 开放度较好）
    │
    └── 通道 B: 浏览器扩展 + Playwright（兜底）
          优势：抓取完整 DOM 数据（包括官方 API 不给的字段）
          劣势：需要浏览器环境，Cookie 敏感
          适用：小红书（主力）、抖音（辅助）
```

### 3.2 PlatformAdapter 接口

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

@dataclass
class RawComment:
    """平台原始评论，字段因平台而异"""
    platform: str
    platform_comment_id: str
    platform_post_id: str
    platform_user_id: str
    platform_username: str
    platform_avatar_url: str
    content: str
    image_urls: list[str]
    like_count: int
    reply_count: int
    parent_platform_comment_id: str | None
    is_from_creator: bool
    is_pinned: bool
    platform_created_at: datetime

@dataclass
class NormalizedComment:
    """标准化后的评论，所有平台统一"""
    # 与 RawComment 相同字段 + 我们自己的字段
    raw: RawComment
    post_id: str | None           # 我们的 posts.id（需要先解析帖子）
    status: str = 'pending'

class PlatformAdapter(ABC):
    """平台适配器接口 — 加新平台 = 实现这个接口"""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        ...

    @abstractmethod
    async def fetch_comments(
        self, post_url: str, cookie_data: dict | None = None
    ) -> list[RawComment]:
        """抓取指定帖子的评论列表"""
        ...

    @abstractmethod
    async def fetch_posts(
        self, cookie_data: dict | None = None
    ) -> list[dict]:
        """获取创作者的内容列表"""
        ...

    @abstractmethod
    async def send_reply(
        self, comment_id: str, content: str, cookie_data: dict
    ) -> bool:
        """发送回复"""
        ...

    @abstractmethod
    def normalize(self, raw: RawComment) -> NormalizedComment:
        """平台特定 → 标准化"""
        ...

    @abstractmethod
    def identify(self) -> dict:
        """返回平台能力描述，供前端自适应展示"""
        ...
```

### 3.3 小红书适配器的具体实现策略

三个平台按优先级逐平台覆盖：小红书（Week 1-2）→ 抖音（Week 2-3）→ B站（Week 3）。MVP 阶段先打穿小红书全链路，再依次加入抖音和 B 站。PlatformAdapter 接口统一，后两个平台只需实现接口。

小红书的 DOM 结构最复杂（虚拟滚动 + 动态加载），先攻克最难的后两个自然快。

**数据获取路径（按优先级）：**

1. **浏览器扩展 content script**（实时场景）
   - 注入 `xiaohongshu.com` 页面
   - 监听创作者打开自己笔记 → 自动捕获评论区 DOM
   - 每 3 秒增量扫描新增评论（MutationObserver）
   - 批量 POST 到后端 API

2. **Playwright headless 定时任务**（后台场景，**MVP 不做**，后期补兜底通道）
   - 每 15 分钟跑一次
   - 用创作者同步的 Cookie 登录
   - 遍历最近 N 篇笔记的评论区

3. **小红书开放平台 API**（如果申请成功）
   - 仅限企业号/小程序开发者
   - 如果你们能搞到权限，这是最稳的方案
   - 但不能依赖它作为 MVP 的唯一通道

**扩展需要解决的难点：**

| 难点 | 方案 |
|---|---|
| 小红书 Web 版评论区是虚拟滚动，DOM 动态加载 | 用 `IntersectionObserver` 触发滚动，`MutationObserver` 捕获新增节点 |
| 登录态 Cookie 有效期短 | 扩展检测到 401/重定向到登录页时，通知用户重新扫码 |
| 反爬/频率限制 | 评论抓取是 GET 行为，模拟正常用户滚动速度（间隔 1-2 秒），不比人工快太多 |
| 评论带图/表情 | 保留原始 HTML → 标准化时转为 `[图片]` 占位符 + image_urls 数组 |

### 3.4 浏览器扩展消息流

```
XHS 页面
    │
    ├── content script (注入到页面)
    │     ├── MutationObserver → 监测评论区 DOM 变化
    │     ├── 解析评论节点 → 提取 RawComment
    │     └── 发送到 background service worker
    │
    ├── background service worker
    │     ├── 接收 content script 消息
    │     ├── 去重（内存 Map，最近 500 条）
    │     ├── 批量聚合（1 秒缓冲期）
    │     └── HTTP POST → 后端 /api/internal/comments/batch
    │
    └── popup (扩展弹窗)
          ├── 显示同步状态
          ├── 今日已捕获评论数
          └── Cookie 状态指示
```

---

## 四、Agent System Prompt 设计（核心 IP）

### 4.1 ClassifyRouterAgent

**模型选择：** 轻量模型（分类任务不需要强推理，用小模型即可）。后期微调 0.5B 小模型替代 API，几乎免费。
**目标：** 给每条评论打标签，决定后续处理路径

```
You are a comment classification engine for a Chinese social media creator.
Your ONLY job is to analyze ONE comment and output a JSON classification.

## Context about the creator
- Platform: {platform}
- Creator bio: {creator_bio}
- Post title: {post_title}

## Input comment
Username: {username}
Content: {content}
Is reply to another comment: {is_reply}

## Output format (strict JSON, no markdown wrapping)
{
  "category": "question|complaint|praise|spam|neutral|ugc_gold|collab_inquiry",
  "sentiment": "positive|negative|neutral",
  "urgency": "high|medium|low",
  "needs_reply": true|false,
  "suggested_tone": "professional|casual|warm|humorous|no_reply",
  "key_points": ["3-5 key points from the comment"],
  "reasoning": "one short sentence"
}

## Classification rules
- question: asking about product, price, tutorial, source, availability
- complaint: dissatisfaction, bug report, bad experience, anger
- praise: compliment, support, appreciation (needs_reply=true if detailed, false if just "great!")
- spam: ads, irrelevant links, repetitive bot comments, "互关互赞"
- neutral: general chat, off-topic, not needing action
- ugc_gold: detailed personal experience, insightful addition, funny reply worth highlighting
- collab_inquiry: asking for collaboration, business inquiry

## Urgency rules
- HIGH: complaints, urgent questions about orders/products, potential PR risks, safety issues
- MEDIUM: product questions, collaboration inquiries, detailed praise worth acknowledging
- LOW: general praise, neutral chat, ugc_gold (nice to have but not urgent)

## Edge cases
- Comments that are just emoji → neutral, needs_reply=false
- Comments in dialect/Internet slang → classify by overall sentiment
- Comments tagging other users (not the creator) → may be neutral
- "蹲" / "等" / "求" without specific ask → low urgency question
```

### 4.2 ReplyGenerateAgent

**模型选择：** 强推理模型（回复质量直接影响创作者体验）。后期微调 7B 模型学习创作者风格，简单评论本地生成，复杂场景才调 API。
**目标：** 生成 3 种风格的回复草稿

```
You are a reply assistant for a Chinese content creator. Your job is to draft replies
that sound like the creator wrote them personally.

## Creator's persona (IMPORTANT — match this voice)
- Tone: {creator_tone}               # e.g. "casual and friendly with occasional humor"
- Common phrases: {creator_phrases}   # e.g. "哈哈哈", "姐妹", "安排上了"
- Bio: {creator_bio}

## Platform context
- Platform: {platform}               # affects emoji usage and reply norms
- 小红书 replies should feel personal and community-like
- 抖音 replies can be shorter and punchier
- B站 replies can include platform memes

## Comment to reply to
- Username: {username}
- Content: {content}
- Classification: {category} (urgency: {urgency})
- Key points: {key_points}

## Generate 3 reply drafts, each in a different style:

1. **warm** — 亲切温暖，适合粉丝互动
   - Use 姐妹/宝子 where natural
   - Sound like talking to a friend
   
2. **casual** — 轻松自然，适合日常交流
   - Brief, natural, conversational
   - Can use light humor

3. **professional** — 专业可信，适合产品咨询/商务
   - Clear, helpful, trustworthy
   - No slang, but not robotic

## Rules for ALL styles
- Address the commenter: use @{username} or their name
- Keep under 150 characters (XHS limit awareness, but not hard enforcement)
- Include emoji only if it fits naturally (1-2 max)
- NEVER make promises: no "保证", no "一定", no price commitments
- NEVER pretend to be the creator: use phrases like "感谢喜欢" not "我爱你"
- NEVER acknowledge complaints with specific compensation amounts
- For complaints: acknowledge, express care, suggest DM for details
- For questions: answer if info is in the context, otherwise suggest where to find it
- For praise: thank genuinely, add a personal touch

## Output format (strict JSON)
{
  "drafts": [
    {"style": "warm", "content": "回复内容"},
    {"style": "casual", "content": "回复内容"},
    {"style": "professional", "content": "回复内容"}
  ],
  "recommended": "casual",
  "reasoning": "why this style works best for this specific comment",
  "risk_warning": null  // or "此回复涉及价格承诺，建议创作者自行编辑"
}
```

### 4.3 InsightMiningAgent

**模型选择：** 强推理模型（综合分析需要聚合大量评论），可定时批量处理降低成本
**运行频率：** 每 6 小时或手动触发
**输入：** 一批评论（最近 N 条或某个帖子的全部评论）

```
You are a content insight analyst for a Chinese social media creator.
Your job is to mine the comment section for actionable insights.

## Context
- Platform: {platform}
- Time range of comments: {time_range}
- Number of comments analyzed: {count}

## Comments data (JSON array)
{comments_json}

## Output format (strict JSON)
{
  "overall_sentiment": {
    "score": 0.0-1.0,                # 1.0 = all positive
    "trend": "improving|stable|declining",
    "summary": "one line"
  },
  "top_topics": [
    {"topic": "话题名", "mention_count": N, "avg_sentiment": 0.0-1.0, "example_comment": "..."}
  ],                                # top 5 topics
  "emerging_trends": [
    {"trend": "趋势描述", "evidence": "supporting comments"}
  ],                                # 正在形成的新话题/梗
  "fan_concerns": [
    {"concern": "粉丝关切点", "severity": "high|medium|low", "affected_users_count": N}
  ],
  "ugc_gold": [
    {"comment_id": "...", "username": "...", "content_preview": "...", "why_valuable": "why this is good UGC"}
  ],                                # top 3 UGC gems
  "core_fans": [
    {"username": "...", "engagement_score": 0-100, "comment_count": N, "avg_comment_length": N, "top_trait": "loyal|insightful|supportive"}
  ],                                # top 5 core fans
  "content_suggestions": [
    {"suggestion": "...", "based_on": "which insight this comes from", "priority": "high|medium|low"}
  ],
  "unreplied_priority": [
    {"comment_id": "...", "username": "...", "content_preview": "...", "urgency": "high"}
  ],                                # comments that NEED replies but haven't gotten one
  "executive_summary": "3 sentence summary for the creator to read in 30 seconds"
}
```

### 4.4 CrossPlatformLinkAgent（MVP 不做）

**用途：** 识别同一用户在不同平台的账号。设计保留，后期启用。
**触发：** 定时任务，或新评论入库时异步触发
**技术：** pgvector 余弦相似度初筛 + LLM 精判

分两步走：
1. **粗筛**：pgvector 对 content_embedding 做余弦相似度搜索，找到潜在匹配对
2. **精判**：LLM 对比用户名、头像、评论内容风格

```
You are a user identity matching specialist. Determine if two social media profiles
from DIFFERENT platforms likely belong to the same person.

## Profile A
- Platform: {platform_a}
- Username: {username_a}
- Recent comments (sample): {comments_a}

## Profile B
- Platform: {platform_b}
- Username: {username_b}
- Recent comments (sample): {comments_b}

## Output (strict JSON)
{
  "match_probability": 0.0-1.0,
  "confidence": "high|medium|low",
  "matching_factors": ["list what matched"],
  "mismatching_factors": ["list what didn't match"],
  "reasoning": "one sentence"
}

## Matching signals (weighted):
1. Username similarity (especially if identical) — STRONG
2. Writing style (sentence length, punctuation habits, emoji usage) — MEDIUM
3. Comment topics (same interests/products discussed) — MEDIUM
4. Avatar visual similarity — WEAK (often different across platforms)
```

---

## 五、Harness 模块 1：上下文管理设计

### 5.1 三层上下文架构

每个 Agent 的上下文分为三层，按优先级和变化频率组织：

```
[System Prompt] — 固定，角色核心定义 + 输出格式 + 安全规则
     │
[Static Context] — 变化频率低，可缓存
  ├── 创作者人设（tone, phrases, bio）
  ├── 平台规范（当前平台的回复风格要求）
  └── 禁止规则（不承诺、不议价、不假装创作者）
     │
[Dynamic Context] — 每次调用都不同，按优先级检索+注入
  ├── 优先级 0：帖子内容摘要 + 当前评论全文 + Classify 结果（不可压缩）
  ├── 优先级 1：同帖子相似回复 + 该用户互动历史（先压缩再传入）
  └── 优先级 2：历史高采纳率回复模板（摘要化后传入）
```

### 5.2 各 Agent 的上下文注入清单

**ClassifyRouterAgent：**

| 字段 | 来源 | 用途 |
|---|---|---|
| platform | 评论数据 | 平台差异影响分类标准 |
| post_title | posts 表 | 理解帖子主题，区分同一评论在不同帖子下的不同含义 |
| post_content_summary | posts 表（新增） | 深层帖子理解 |
| username | 评论数据 | — |
| content | 评论数据 | 主分析对象 |
| parent_comment_content | comments 表（新增） | 回复链上下文，"同问"这种短回复需要知道父评论内容 |
| is_reply | 评论数据 | — |

**ReplyGenerateAgent：**

| 字段 | 优先级 | 用途 |
|---|---|---|
| 人设配置 | 静态（缓存） | 匹配创作者语气 |
| 平台规范 | 静态（缓存） | 平台回复风格差异 |
| 帖子内容摘要 | 0（不可压缩） | 知道帖子讲了什么，回复才有针对性 |
| 当前评论全文 | 0（不可压缩） | 要回复的对象 |
| Classify 结果（category + intent + key_points） | 0（不可压缩） | 指导回复策略 |
| 父评论内容 | 1（可压缩） | 回复链上下文 |
| 同帖子已回复列表（最相关 5 条） | 1（可压缩） | 避免生成重复回复 |
| 该评论者与创作者的历史互动（最近 3 次） | 1（可压缩） | 区分老粉丝/新路人 |
| 高采纳率回复模板 | 2（摘要化） | 历史最佳实践参考 |

**InsightMiningAgent：**

不走全量注入。两步聚合策略：
```
第一步 — 聚合层（规则引擎，零 LLM 成本）：
  ├── 评论按分类/情感/紧急度分组统计
  ├── 高频关键词提取（本地 TF-IDF）
  ├── Top 20 高互动评论全文（按点赞数排序）
  └── 剩余评论只传统计摘要

第二步 — 传给 LLM：
  ├── 总体统计数据
  ├── Top 20 高互动评论全文（~3000 tokens）
  └── 低互动评论统计摘要（~200 tokens）
```

### 5.3 上下文预算与分级压缩

总预算硬上限：4000 tokens（含 System Prompt）。

```
检查流程：
  当前上下文 < 3000 tokens → 全部保留
  当前上下文 > 3000 tokens → 触发第一级压缩（优先级 2 内容摘要化）
  当前上下文 > 3500 tokens → 触发第二级压缩（优先级 1 内容摘要化）
  当前上下文 > 4000 tokens → 硬截断优先级 0 的内容部分
```

压缩方法不是规则截断，而是用一次轻量模型调用做语义摘要：

| 场景 | 方法 | 原因 |
|---|---|---|
| 短文本 <200 tokens | 直接保留 | 不需要 |
| 中文本 200-800 tokens | 本地规则：提取关键词 + 类目 | 零额外成本 |
| 长文本 >800 tokens | 小模型摘要化 | 规则搞不定语义 |
| 多条记录的聚合 | 小模型摘要化 | 需要跨记录推理 |

**为什么不用规则截断？** 规则截断会丢掉语义。比如"该用户上次问了产品 A 的价格，创作者回复说等双十一" — 截断可能切掉"双十一"，这个关键信息就丢了。摘要化保留语义，只丢细节。

### 5.4 上下文缓存

```
静态上下文按 user_id + platform 缓存：
  ├── System Prompt → 代码发布时刷新
  ├── 创作者人设 → DB 更新时清缓存
  └── 平台规则 → 代码发布时刷新

每次 Agent 调用只需拼动态部分，节省 CPU 和调试时间。
```

### 5.5 意图识别

ClassifyRouterAgent 的输出增加 `intent` 和 `intent_detail` 字段。不在 Agent 系统外新增单独的意图识别步骤，而是在同一次分类调用中一并输出。

完整分类体系：

```
question:
  ├── purchase_intent       → 想买，给链接/引导下单
  ├── how_to_intent         → 想学，分享经验/教程
  ├── comparison_intent     → 在比货，客观分析
  ├── availability_intent   → 问库存/补货时间
  └── casual_question       → 闲聊式提问，轻松回

complaint:
  ├── product_issue         → 产品有问题，需严肃处理
  ├── service_complaint     → 服务/物流不满，表达歉意+引导私信
  ├── price_complaint       → 嫌贵，解释价值不降价
  └── platform_issue        → 平台问题（链接失效等），告知解决方案

praise:
  ├── genuine_praise        → 真心认可，真诚感谢
  ├── social_praise         → 社交式互夸，轻松回
  ├── fan_crush             → 粉丝喜爱表达，热情回应
  └── low_effort_praise     → "好看""棒"，简短回或批量回

spam:
  ├── ad_spam               → 广告，直接过滤
  ├── follow_bait           → 互关互赞，直接过滤
  └── bot_repetition        → 机器人刷屏，直接过滤

neutral:
  ├── off_topic             → 与本帖无关
  ├── tag_others            → 在 @ 别人，不是跟创作者说话
  └── emoji_only            → 纯表情

ugc_gold:
  ├── detailed_experience   → 详细个人经验分享
  ├── insightful_comment    → 深度观点/补充
  └── funny_highlight       → 幽默评论值得展示

collab_inquiry:
  ├── brand_collab          → 品牌合作意向
  ├── pr_inquiry            → 公关/媒体联系
  └── platform_invite       → 其他平台入驻邀请
```

意图识别之所以能做到这个颗粒度，依赖于帖子内容的注入。同样的"这个多少钱"，在产品测评帖是 purchase_intent，在书桌布置帖是 casual_question。**没有帖子上下文，意图识别就是在猜。**

### 5.6 平台差异化的上下文策略

| 平台 | 评论特征 | 上下文影响 |
|---|---|---|
| 小红书 | 评论长（100-300字），社区感强，emoji 多 | 单条评论 token 占比大，预算更容易满 |
| 抖音 | 评论短（5-30字），刷得快 | 评论本身信息少，帖子上下文更重要 |
| B站 | 楼层式盖楼，回复链可嵌套 3-4 层 | `parent_comment_content` 特别关键 |

帖子摘要的获取方式也不同：小红书爬正文文本，抖音需视频描述（MVP 不做语音转文字），B站取标题+简介。

### 5.7 需要补齐的数据字段

```sql
-- posts 表：帖子内容摘要
ALTER TABLE posts ADD COLUMN content_summary TEXT;

-- comments 表：父评论内容（用于回复链上下文）
ALTER TABLE comments ADD COLUMN parent_comment_content TEXT;
```

### 5.8 pgvector 用于相似回复检索

comments 表已有的 `content_embedding` 字段可用于检索与当前评论语义最相似的已回复评论，注入 Reply Agent 上下文：

```
当前评论 → embedding API → 向量 → pgvector 余弦相似度搜索
  WHERE post_id = :current_post_id AND status = 'replied'
  ORDER BY content_embedding <=> :query_vector LIMIT 5
```

不需要额外基础设施，pgvector 已在。

---

## 五-二、Harness 模块 2：工具系统设计

### 5-2.1 各 Agent 的工具清单

Agent 目前是纯文生文系统（读 DB → 写 DB），没有主动查询外部信息的能力。需要补齐只读工具：

**ClassifyRouterAgent — 1 个只读工具：**

| 工具 | 用途 | 超时 |
|---|---|---|
| `get_post_context` | 返回帖子标题 + 内容摘要 + 统计 | 3s |

意图识别依赖帖子上下文。没有这个工具，分类就是在猜。

**ReplyGenerateAgent — 3 个只读工具：**

| 工具 | 用途 | 超时 |
|---|---|---|
| `get_post_context` | 同上 | 3s |
| `search_creator_replies` | 查创作者对该用户的已有回复 + 同帖子下分类相同的已回复评论。两个维度：避免重复回复 + 识别老粉丝 | 5s |
| `search_similar_replies` | pgvector 语义搜索最相似的已回复评论。比分类匹配更准，直接命中措辞差异大的语义相似评论 | 5s |

**InsightMiningAgent — 2 个只读工具：**

| 工具 | 用途 | 超时 |
|---|---|---|
| `get_post_context` | 同上 | 3s |
| `get_comment_batch` | 批量取评论，返回统计摘要 + Top N 高互动评论 + 剩余聚合统计。不直接传全量全文 | 5s |

**CrossPlatformLinkAgent（MVP 不做，设计保留）— 1 个只读工具：**

| 工具 | 用途 | 超时 |
|---|---|---|
| `search_similar_users` | pgvector 跨平台相似用户搜索 | 5s |

### 5-2.2 send_reply 的定位

Agent 不直接调 send_reply。发送是人机协作的边界，人的权限，不是 Agent 的权限。

```
MVP：send_reply 是前端调用的 API，Agent 只写到 reply_drafts
未来：创作者可开"低风险自动发送"，Agent 调 send_reply 仍要创作者的提前授权
```

### 5-2.3 工具失败与降级

核心原则：**工具调用失败 ≠ 任务失败。** 工具提供的是"锦上添花"的上下文，不是主线输入。

```
每个工具的 fallback 行为：

get_post_context 失败 → 任务继续（评论内容还在，粗略分类也能跑）
                      但分类质量下降 → 标记 low_confidence

search_creator_replies 失败 → 跳过该上下文，用"该用户无历史记录"兜底

search_similar_replies 失败 → 跳过该上下文，只用 classification 匹配兜底

get_comment_batch 失败 → InsightMining 整体降级：
                        只用统计摘要（规则引擎算的不依赖 LLM）→ 不上报错
```

每个工具设超时上限：
- DB 查询类：3 秒
- embedding API 调用：10 秒
- 超时视为工具不可用，走 fallback

### 5-2.4 发送操作的原子性（未来自动发送场景）

```
不是：调 send_reply API → 成功 → 写 DB

而是：先写 DB（sent_at=NULL, status='sending'）
      → 调 send_reply API
      → 成功 → 更新 sent_at
      → 失败 → 更新 status='failed'，不自动重试，让创作者手动补发

定时任务 5 分钟后查平台确认回复是否已发出 → 补写 DB。
```

原则：**不在失败时自动重试发送操作。** 宁可让创作者手动补发，也不要自动重发导致重复回复。

### 5-2.5 工具注册机制

```
全局工具注册表 TOOL_REGISTRY：
  ├── get_post_context
  ├── search_creator_replies
  ├── search_similar_replies
  ├── get_comment_batch
  └── search_similar_users

Agent 配置 AGENT_TOOLS：
  ClassifyRouterAgent    → [get_post_context]
  ReplyGenerateAgent     → [get_post_context, search_creator_replies, search_similar_replies]
  InsightMiningAgent     → [get_post_context, get_comment_batch]
  CrossPlatformLinkAgent → [search_similar_users]  (MVP 不做，设计保留)
```

Agent 初始化时从配置表取工具列表，不改 Agent 代码就能加减工具。

### 5-2.6 工具描述格式（为后期 ReAct 模式预留）

MVP 阶段工具是后台代码固定调用，不是模型自主选工具。但描述格式先定好，后期切 ReAct 直接复用：

```json
{
  "name": "search_creator_replies",
  "description": "搜索创作者对特定用户的历史回复。用于判断该用户是新粉丝还是老粉丝，以及避免生成重复回复。",
  "parameters": {
    "post_id": "当前帖子ID",
    "platform_user_id": "评论者的平台用户ID",
    "limit": "返回最多多少条（默认 5）"
  },
  "readonly": true,
  "timeout_seconds": 5,
  "max_retries": 2
}
```

### 5-2.7 工具调用可观测性

每次工具调用记录到 `agent_logs`：
- 工具名、耗时、成功/失败、重试次数
- 如果 30% 的 `search_creator_replies` 调用在超时 → 应该能查到

---

## 五-三、Harness 模块 3：执行编排设计

### 5-3.1 Agent Loop 模板方法

每个 Agent 遵循统一的 Agent Loop，由 BaseAgent 模板方法驱动：

```
observe → plan → act → verify → output
```

```python
class BaseAgent:
    async def run(self, task: AgentTask):
        context = await self.observe(task)         # 子类实现 → 收集上下文
        plan    = await self.plan(context)          # 子类实现 → 决定策略
        result  = await self.act(plan)              # 子类实现 → LLM 调用
        verified = await self.verify(result)        # 子类实现 → 校验结果
        return await self.output(verified, task)    # BaseAgent 实现 → 写 DB

    async def output(self, result, task):
        task.result = result
        task.status = 'done'
        await self.db.save(task)
        await self.create_downstream_tasks(task, result)
```

各子类覆写 observe/plan/act/verify，output 由 BaseAgent 统一处理。

### 5-3.2 各 Agent 的 Loop 详述

**ClassifyRouterAgent：**

```
observe → 读评论 + 帖子上下文 + 父评论内容
plan    → 信息够 → 直接分类；信息不够 → 调 get_post_context
act     → LLM 分类（轻量模型，15s 超时）
verify  → JSON 合法 + category 在枚举内 + intent 在枚举内 + 置信度 > 阈值
output  → 三种路径：
            ├── 置信度高 → 更新 comment + 创建下游任务
            ├── 置信度中 → 更新 comment + 低优先级任务 + 标记
            └── 置信度低 → pending_manual_review + 不创建下游
出错    → JSON 非法 → 重试 2 次 → 都失败 → 降级规则引擎
```

**ReplyGenerateAgent：**

```
observe → 读评论 + 帖子 + 同帖子回复 + 用户历史
plan    → 正常评论 → 生成；引战/敏感 → needs_human；纯表情 → 跳过
act     → LLM 生成（强推理模型，30s 超时）
verify  → 第一层规则引擎（禁止词/长度/空内容）
          第二层 LLM 自检（可选，风格匹配度）
output  → 三种路径：
            ├── 全部通过 → 写 reply_drafts
            ├── 有警告 → 写 reply_drafts + risk_warning
            └── 规则失败 → 重试 1 次 → 仍失败 → needs_human
```

**InsightMiningAgent：**

```
observe → 评论批次 + 统计摘要
plan    → <20 条传全文；>20 条用摘要 + Top 20 高互动全文
act     → LLM 综合分析（强推理模型，60s 超时）
verify  → JSON 格式 + insight 各项非空
output  → 写 agent_tasks.result → 前端拉取
```

### 5-3.3 三个关键决策

**"不回复"是有效决策：** ReplyGenerateAgent 不应无条件生成草稿。评论虽被分类为"需回复"，但实际内容缺乏具体信息、引战或涉及敏感话题时，Agent 应标记 `needs_human`，不生成草稿。

**模型路由集中配置：**

```json
{
  "agent_routing": {
    "classify_router": {
      "primary":  {"provider": "...", "model": "lightweight"},
      "fallback": {"provider": "...", "model": "strong"},
      "timeout_seconds": 15, "max_retries": 2
    },
    "reply_generate": {
      "primary":  {"provider": "...", "model": "strong"},
      "fallback": {"provider": "...", "model": "lightweight"},
      "timeout_seconds": 30, "max_retries": 1
    },
    "insight_mining": {
      "primary":  {"provider": "...", "model": "strong"},
      "fallback": {"provider": "...", "model": "strong"},
      "timeout_seconds": 60, "max_retries": 1
    }
  }
}
```

fallback 方向因 Agent 而异：classify 用强模型兜底（保证分类准确），reply 用轻量模型兜底（至少有一版草稿）。

**任务取消级联：** 创作者手动标 spam → 取消该评论所有 pending 的 reply/insight 任务，避免浪费 LLM 调用。

### 5-3.4 并发与优先级防饥饿

单 Worker 轮询时防止低优先级任务无限等待：

```
每次 poll：80% 按优先级排序、20% 按等待时间排序
  → 等待超过 10 分钟的 low priority 任务也会被取到
```

### 5-3.5 检查点机制

Worker 崩溃后避免重复花钱跑 LLM：

```
act 完成后先写临时结果到 agent_tasks.result（status 仍为 processing）
Worker 重启后发现 result 非空 → 从 verify 继续，不再调 LLM
```

### 5-3.6 超时与熔断

| 层级 | 超时 | 处理 |
|---|---|---|
| 单次 LLM 调用 | 15-60s（按 Agent） | 重试 |
| 单个 Agent 总执行 | 90s | 标记 failed，创建重试 |
| 同任务最大重试 | 3 次 | 标记 pending_manual |
| 同 Agent 连续失败 | 10 次 | 暂停 Agent，报警 |

---

## 五-四、Harness 模块 4：状态与记忆设计

### 5-4.1 四层记忆体系

记忆不止是 `comments.status`（那只是流程状态机）。完整记忆分四层：

| 记忆类型 | 生命周期 | 存什么 | 现有 |
|---|---|---|---|
| 工作记忆 | 单次 Agent 执行内 | 中间步骤、思考链 | ❌ |
| 情节记忆 | 跨评论、跨会话 | 具体事件：某次回复、创作者怎么改的 | ❌ |
| 语义记忆 | 长期累积 | 创作者人设演化、粉丝群体认知 | ⚠️ 静态配置 |
| 程序记忆 | 长期累积 | 哪种回复策略在什么场景下效果最好 | ⚠️ Prompt 里硬编码规则 |

### 5-4.2 工作记忆：Agent 执行链

每次 Agent 执行的中间步骤存入 `agent_tasks.payload.trace`：

```json
{
  "trace": [
    {"step": "observe", "context_sources": ["post_summary", "comment", "user_history_3"]},
    {"step": "plan", "decision": "generate_3_styles", "reasoning": "信息充足"},
    {"step": "act", "model": "deepseek-v4-pro", "tokens": 850, "duration_ms": 1200},
    {"step": "verify", "checks_passed": true, "warnings": []},
    {"step": "output", "draft_ids": ["uuid-1", "uuid-2", "uuid-3"]}
  ]
}
```

实际价值：
- Worker 崩溃后重启 → 读到 trace 非空 → 从 verify 继续，不重复调 LLM
- 调试时能追溯每一步的决策链

### 5-4.3 情节记忆：reply_edit_log 表

情节记忆是**最有价值的记忆层**。核心问题：创作者上次怎么改 AI 回复的？这次能不能一样？

```sql
CREATE TABLE reply_edit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    comment_id UUID REFERENCES comments(id),
    original_draft TEXT NOT NULL,       -- AI 生成的
    edited_content TEXT NOT NULL,       -- 创作者改后的
    classification VARCHAR(32),         -- 评论类型
    intent VARCHAR(32),                 -- 评论意图
    diff_summary TEXT,                  -- 轻量模型总结编辑模式
    diff_embedding vector(1536),        -- pgvector 索引，用于相似检索
    created_at TIMESTAMPTZ DEFAULT now()
);
```

**写入时机：** 创作者编辑草稿 + 点发送 → 异步写一条 edit_log + 轻量模型做 diff 摘要。

**检索时机（Reply Agent 生成前）：**

```sql
-- 同类意图的编辑记录，混合排序
SELECT *, (
  0.7 * cosine_similarity(diff_embedding, :query_embedding) +
  0.3 * recency_weight(created_at)
) AS score
FROM reply_edit_log
WHERE intent = :current_intent
ORDER BY score DESC
LIMIT 3;
```

混合排序防止两个问题：
- 纯时间排序 → 前期不成熟的编辑记录权重过高
- 纯相似度排序 → 3 个月前过时的模式不会被衰减

**注入上下文：**

```
## 创作者历史编辑记录（参考模式）
1. 同类咨询："质量很好" → 改为 "穿了三个月没变形，放心冲！"
   → 学到的模式：提供具体的时间/数据，不是笼统描述
2. 对老粉丝："感谢关注" → 改为 "宝子又来啦！"
   → 学到的模式：识别到熟客时用更亲近称呼
```

### 5-4.4 记忆衰减

创作者的回复习惯会变。超过 60 天的编辑记录不应该等同对待：

```
时间衰减权重：
  0-30 天：1.0
  30-60 天：0.5
  60 天以上：0.2
```

### 5-4.5 语义记忆：人设数据聚合

创作者填的人设是初始值。系统跑起来后应该自动聚合实际行为，辅助创作者调整人设：

```
Dashboard 设置页展示（2 周后）：
  ├── "你选择的风格分布：warm 60%、casual 35%、professional 5%"
  ├── "高频用词：姐妹(40次)、宝子(15次)、安排(8次)"
  └── "建议：你的默认风格可能是 warm，当前设置是 casual"
```

**只展示不自动改。** 修改权留给创作者。

### 5-4.6 程序记忆：三层策略

| 层次 | 做法 | 状态 |
|---|---|---|
| 编码规则 | Prompt 里的硬编码规则（"不承诺、不议价、不假装创作者"） | ✅ 一直在做 |
| 人工提炼 | 从 reply_edit_log 分析规律 → 手动更新 Prompt | ✅ 模块 9 做 |
| 自动学习 | 系统自动发现+自动更新 Prompt+自动 A/B 测试 | ❌ 不做（太危险） |

### 5-4.7 与模块 9 的衔接

reply_edit_log 同时服务于模块 4 和模块 9：
- **模块 4**：Agent 生成前检索 → 注入上下文（在线、实时）
- **模块 9**：离线分析编辑记录 → 发现规律 → 改 Prompt（离线、每周）

---

## 五-五、Harness 模块 5：Hooks/Middleware 设计

### 5-5.1 Hooks 管道

每个 Agent 执行流程有 5 个注入点 + 1 个异常点：

```
pre_model → model_call → post_model → pre_tool → tool_exec → post_tool
                                                              ↑
                                                         on_error（异常时）
```

所有横切逻辑（日志、限流、校验、安全、重试）通过 hook 统一注入，Agent 代码不变。

### 5-5.2 HookContext：Hook 间的共享数据对象

```python
class HookContext:
    task: AgentTask
    compressed: bool = False       # ContextBudgetHook 设置
    warnings: list[str] = []       # SafetyCheckHook 追加
    budget_remaining: int = 0      # RateLimitHook 设置
```

每个 hook 读/写同一个 HookContext，下一个 hook 能看到上一个的修改。没有共享上下文，hook 就是孤立的。

### 5-5.3 MVP 6 个内置 Hook

**pre_model 阶段：**

| Hook | 顺序 | 做什么 | 超时 | 失败 |
|---|---|---|---|---|
| RateLimitHook | 第 1 | 检查 API 调用频率，超限则等待或拒绝 | 500ms（Redis） | 阻塞 |
| ContextBudgetHook | 第 2 | 数 token，超预算时触发分级压缩 | 2s（可能调小模型摘要） | 阻塞 |

**post_model 阶段：**

| Hook | 顺序 | 做什么 | 超时 | 失败 |
|---|---|---|---|---|
| SchemaValidationHook | 第 1 | JSON 格式/必填字段/枚举值校验 | 100ms（纯 CPU） | 触发重试 |
| SafetyCheckHook | 第 2 | 禁止词/长度/空内容检查（仅 Reply Agent） | 100ms（纯 CPU 正则） | **不阻塞**，加 warning |
| LoggingHook | 第 3 | 写 agent_logs：模型名/tokens/耗时/cost | 500ms（DB 写） | 吞异常 |

**on_error 阶段：**

| Hook | 做什么 | 失败 |
|---|---|---|
| RetryHook | 分级重试（超时→指数退避 / 非法JSON→重试2次 / 限流→等待backoff）。重试耗尽→failed。同Agent连续10次失败→熔断 | 标记 pending_manual |

### 5-5.4 配置驱动

每个 Agent 独立配置 hooks，只比别的 Agent 多一个 safety_check：

```json
{
  "agent_hooks": {
    "classify_router": {
      "pre_model":  ["rate_limit", "context_budget"],
      "post_model": ["schema_validation", "logging"],
      "on_error":   ["retry"]
    },
    "reply_generate": {
      "pre_model":  ["rate_limit", "context_budget"],
      "post_model": ["schema_validation", "safety_check", "logging"],
      "on_error":   ["retry"]
    },
    "insight_mining": {
      "pre_model":  ["rate_limit", "context_budget"],
      "post_model": ["schema_validation", "logging"],
      "on_error":   ["retry"]
    }
  }
}
```

### 5-5.5 Hook 设计原则

**Hook vs Agent 内部逻辑的边界：**
- Hook 管"怎么跑"（日志、限流、校验、安全、重试）
- Agent 管"跑什么"（分类逻辑、人设匹配、回复策略）

**Hook 可独立测试：** 输入 HookContext → 检查输出 HookContext，不依赖 Agent、不依赖 LLM、不依赖 DB（可 mock）。

**SafetyCheckHook 失败不阻塞：** 宁可让创作者看到带警告的草稿，也不要什么都没有。警告标记在 reply_drafts 上，前端标红展示。

---

## 五-六、Harness 模块 6：评估与观测设计

### 5-6.1 三类评估体系

| 类型 | 数据来源 | 回答什么 | 频率 |
|---|---|---|---|
| 离线评估 | 人工标注 eval set | "改 Prompt 后变好了吗？" | 每次改 Prompt |
| 在线评估 | 生产行为数据 | "创作者对 AI 满意吗？" | 持续自动 |
| 决策追溯 | agent_tasks.trace | "当时为什么这样决定？" | 每次 Agent 执行 |

### 5-6.2 离线评估

**分类 eval set：** 人工标注 100 条真实评论（category + intent + sentiment + urgency）。

- 初始标注：团队成员手动标，cold start
- 持续更新：每两周从生产数据取 20 条新评论，对比 AI 分类 vs 创作者实际操作，不一致的加入 eval set
- 过期策略：超过 3 个月的样本权重减半

每次改 ClassifyRouter Prompt → 跑 eval set → 按类别出分：
- 总体准确率、每类准确率、混淆矩阵
- 上线条件：准确率 ≥ 85%，spam 误判率 ≤ 5%

**回复 eval set：** 50 条评论的"好回复标准"，硬指标 + 人工打分（1-5），上线条件 ≥ 3.5/5。先做分类，回复的后期补。

### 5-6.3 在线评估

**分类质量指标：**

| 指标 | 计算 | 含义 |
|---|---|---|
| 广告拦截准确率 | 创作者标 spam 中 AI 已标 spam 的比例 | AI 不能误杀 |
| 漏网率 | 创作者标 spam 中 AI 判为"需回复"的比例 | 越低越好 |
| reclassify 率 | 创作者手动改过分类的评论占比 | AI 一次到位率 |

**回复质量指标：**

| 指标 | 计算 | 污染修正 |
|---|---|---|
| 采纳率 | is_adopted / 总草稿数 | 表面指标，可能被"懒得改"污染 |
| 编辑率 | is_edited / is_adopted | 被采纳但被改过 |
| 真实满意采纳率 | 采纳率 × (1 - 高编辑量占比) | 编辑距离 > 10 字符的算"不满意" |
| 无操作率 | 三条都没被采纳 / 总评论 | 一个都看不上 |
| 各风格采纳分布 | warm/casual/professional 各自采纳率 | 反映真实人设偏好 |

**核心经济指标：**

```
单次有效回复成本 = 总 API 费用 ÷ 被采纳且未编辑的草稿数

不是"生成一条草稿多少钱"，是"生成一条创作者直接用的草稿多少钱"。
采纳率 30% → 实际成本 = 生成成本 × 3.3
```

### 5-6.4 指标分拆

**按平台分拆：** 同一 Prompt 在小红书采纳率高、抖音低 → 不是 Prompt 问题，可能是平台评论风格差异。各平台指标独立追踪。

**按 Prompt 版本分拆：** 每次改 Prompt 记录版本号到 agent_tasks，对比各版本下的采纳率/编辑率。改 complaint 回复变好了但搞差了 question → 回退。

### 5-6.5 决策追溯

三个月后查"为什么这条被判 spam？"→ agent_tasks.trace 有完整决策链：

```json
{
  "decision_path": [
    {"step": "classify", "confidence": 0.78,
     "reasoning": "评论仅'排队等链接'且多次重复，判定为 bot repetition spam"},
    {"step": "routing", "action": "mark_spam"}
  ]
}
```

### 5-6.6 Dashboard

**创作者面板（前端）：** 今日新增、待回复（含紧急标注）、回复率、AI 采纳率、各平台分布。

**内部监控（后期接 Sentry/Grafana）：** Agent 队列长度、各类错误率、日均费用、响应时间 P50/P95、Hook 失败次数。

---

## 五-七、Harness 模块 7：约束与恢复设计

### 5-7.1 三层约束体系

```
第一层 ─ 软约束（Prompt）：模型尽力遵守，但可能忽略
     │    "NEVER make promises: no 保证, no 一定, no price commitments"
     │    ↓ 模型不听话 ↓
第二层 ─ 硬约束（Hook）：代码强制执行，不可绕过
     │    SafetyCheckHook 正则扫输出 → 命中禁止词 → 加 warning
     │    SchemaValidationHook → JSON 格式不对 → 触发重试
     │    ↓ 重试耗尽 ↓
第三层 ─ 人约束（最终防线）：创作者手动确认发送
          Agent 没有 sent_at 写入权限
```

### 5-7.2 逐 Agent 降级策略

**ClassifyRouter 挂了 → 规则引擎接管：**

```
规则引擎分类（零成本、毫秒级）：
  ├── content 包含 "链接""怎么买""多少钱" → question
  ├── content 包含 "垃圾""骗子""烂" → complaint
  ├── 长度 < 5 且纯表情 → neutral
  ├── content 包含 "互关""互赞" → spam
  └── 其他 → neutral（低置信度标记）

原则：宁可漏过一条广告，不要误判一条正常评论为 spam。
```

**ReplyGenerate 挂了 → 不生成固定模板：**

重试 3 次后 → 标记 pending_manual。不自动发模板 — 创作者看到明显的模板回复会失去信任。**宁可不生成，不要生成垃圾。**

**LLM API 全挂（极少见）→ 系统整体降级：**

Dashboard 横幅提示 + 评论继续抓取入库 + 积压任务等 API 恢复后批量创建。

### 5-7.3 熔断机制

```
熔断窗口：5 分钟
触发条件：窗口内失败率 > 50%
动作：停止为该 Agent 创建新任务
自动恢复：5 分钟后试跑 1 个任务
  成功 → 恢复
  失败 → 重新熔断，暂停时间翻倍（10min → 20min → 40min）
```

### 5-7.4 四级错误恢复

| 层级 | 触发条件 | 动作 | 自动 |
|---|---|---|---|
| L1 重试 | LLM 超时/格式非法/限流 | 指数退避，最多 3 次 | ✅ |
| L2 降级 | 重试耗尽 | Classify→规则引擎，Reply→pending_manual | ✅ |
| L3 熔断 | 窗口内失败率 > 50% | 暂停该 Agent | ✅ |
| L4 人工 | L1-L3 全部耗尽 | 标记 pending_manual，Dashboard 展示 | ❌ |

### 5-7.5 核心原则

**宁可不回，不要回错。** 回复质量比回复速度重要。

**规则引擎在分类场景可行。** 90% 的明显 spam + 紧急 complaint 能被规则抓住，10% 边缘情况交给人工。

**硬约束比软约束可靠。** 禁止词的检测不应该依赖"模型听话"。

---

## 五-八、Harness 模块 8：安全沙箱设计

### 5-8.1 Agent World vs Real World

```
Agent World（自由操作，所有操作在沙箱内）：
  ├── 读 comments / posts / users / agent_tasks
  ├── 写 agent_tasks.result
  ├── 写 reply_drafts
  ├── 写 agent_logs
  └── 写 reply_edit_log

Real World（不能碰，跨过去的东西必须经过人）：
  ├── 回复发送到平台（人点"发送"触发）
  ├── 读取 Cookie 明文（API 服务专属，Agent 无解密密钥）
  ├── 修改创作者人设（人手动改）
  ├── 删除数据（Agent 无 DELETE 权限）
  └── 调用平台 API（send_reply 不暴露给 Agent）
```

### 5-8.2 Prompt Injection 防御（三层）

**第一层 — 输入清洗：** 在 ClassifyRouter 和 ReplyGenerate 之前跑，移除 `[系统指令...]` 标记和 `{{ }}` 模板注入，截断超长内容。

**第二层 — XML 标签隔离：** 用户评论内容用 `<user_comment>` 标签包裹，明示模型这是不可信数据，与系统指令分界。

**第三层 — 输出不比输入更危险：** SafetyCheckHook 扫禁止词 + 创作者手动确认发送。注入攻击最坏结果 = AI 生成一条离谱草稿，发不出去。

分类阶段注入比回复阶段更隐蔽 → 输入清洗在所有 Agent 前跑，不只 Reply Agent。

### 5-8.3 Cookie 安全（三层加密）

```
传输层：浏览器扩展 crypto.subtle.encrypt() 加密后发 HTTP，密钥安装时生成
存储层：后端 AES-256-GCM 加密后写 cookie_data，密钥仅 API 服务持有
使用层：仅 send_reply 时解密，用完丢弃。Agent Worker 无解密密钥
```

即使 DB 被拖库，攻击者拿到的是加密 blob。

### 5-8.4 DB 权限隔离

```
Agent Worker 独立 DB 用户：
  GRANT SELECT ON comments, posts, users, platform_accounts, agent_tasks, reply_edit_log
  GRANT INSERT, UPDATE ON agent_tasks, reply_drafts, agent_logs, reply_edit_log
  无 DELETE / DROP / ALTER
  cookie_data 列可读但不可解密（加密存储，Worker 无解密密钥）

API 服务独立 DB 用户：
  有 cookie_data 读写权限 + 解密密钥
```

### 5-8.5 其他边界

**输入校验（API 层）：** 平台枚举值/长度/类型，单批上限 100 条。

**扩展权限最小化：** host_permissions 仅限三个平台 HTTPS，不请求 cookies/tabs/webRequest 全局权限。

**API Key 管理：** 环境变量注入，不进 Git，每月轮换。

**多用户隔离预埋：** 所有 DB 查询带 user_id 过滤，MVP 单用户时不触发但代码已在。

**安全事件审计表：** 独立于 agent_logs，记录 Cookie 同步/回复发送/输入清洗触发等安全边界事件。

### 5-8.6 Worker 容器隔离

| 维度 | 做法 |
|---|---|
| 网络 | 出站白名单（仅 DB + LLM API），无入站端口 |
| 文件 | 只读，仅 logs 可写 |
| 内存 | Docker memory limit（2GB） |
| 健康检查 | /health endpoint，不健康自动重启 |

---

## 五-九、Harness 模块 9：反馈闭环设计

### 5-9.1 六阶段闭环

```
阶段 1（采集）：  生产行为自动记录到 reply_drafts + reply_edit_log
     ↓
阶段 2（分析）：  每周离线跑脚本，找出编辑模式
     ↓
阶段 3（洞察）：  人工审阅分析结果，决定改什么
     ↓
阶段 4（改 Prompt）：手动更新 Prompt 模板，记录版本号
     ↓
阶段 5（验证）：  新 Prompt 跑 eval set + 上线跟踪采纳率
     ↓
阶段 6（回退）：  指标下降 → 回滚到上一版本
```

### 5-9.2 信号质量权重

不是所有采纳都等价。按 intent 和编辑深度区分信号质量：

```
高信号（编辑反映真实回复策略）：
  complaint → 怎么道歉、怎么引导私信、什么语气
  purchase_intent → 怎么给链接、怎么介绍产品
  comparison_intent → 怎么比货

低信号（只是个人风格偏好）：
  praise/low_effort → "谢谢" vs "谢谢宝子"，差异小

深度编辑率 = 编辑距离 > 原长度 50% 的采纳 / 总采纳
  → 这些"采纳"其实是创作者重写了，不算真正的采纳信号
```

### 5-9.3 沉默信号

沉默率 = 创作者看到评论但未做任何操作的评论数 / 总展示数。靠前端埋点检测（评论卡片进视口但未点击）。沉默率高 = 创作者在放弃使用工具，比低采纳率更危险。MVP 先不做埋点，但设计上要知道。

### 5-9.4 每周分析脚本

```
输出周报：
  ┌── 本周采纳率/编辑率/深度编辑率/无操作率（按 intent 分拆）
  ├── 高频编辑模式 Top 3（轻量模型从 diff_summary 归纳）
  ├── 无操作率最高的 2 个 intent（可能系统搞不定）
  ├── Prompt 版本对比（本周 vs 上周指标）
  └── 跨时间反馈（回复后的点赞/互动数据，后期接入）
```

### 5-9.5 冷启动策略

```
Week 1：数据不够，不做分析
Week 2：初步观察（20-50 条 log），不据此改 Prompt
Week 3+：模式可靠（>5 次且方向一致），进入正常迭代节奏
```

前两周不据零星数据改 Prompt，乱改比不改更糟。

### 5-9.6 噪音处理

**一致性检验：** 同一 intent 下 80% 的编辑往同方向改 → 高置信度，可改 Prompt。方向矛盾 → 不改 Prompt，展示给创作者确认偏好。

**个人 vs 通用分流：** 只有一个创作者在改 → 改他的人设配置。多个创作者同一方向 → 改全局 Prompt。MVP 单用户不触发此分流，设计保留。

### 5-9.7 自动化边界

| 环节 | 自动化 | 原因 |
|---|---|---|
| 采集数据 | ✅ 自动 | 已自动 |
| 每周分析 | ✅ 自动 | 离线脚本 |
| 发现模式 | ⚠️ 半自动 | 轻量模型归纳 + 人工判断 |
| 改 Prompt | ❌ 不自动 | 太危险，一条错的修改影响几千条回复 |
| 验证 | ✅ eval set 自动 + 人工上线判断 | |
| 回退 | ✅ 配置切版本号 | 改配置即可 |

### 5-9.8 与模型训练的衔接

模块 9 是人工反馈闭环（改 Prompt），跑 2-3 个月积累的数据同时服务于：
- **SFT：** is_adopted 高质量回复 → 微调训练数据
- **DPO：** is_edited 的 before/after → 偏好对齐数据

反馈闭环先跑（改 Prompt 见效快），SFT/DPO 后面做（见效慢但更根本）。

---

## 五-十、Harness 模块 10：人机协作设计

### 5-10.1 每个决策点的人机分工

| 决策点 | Agent | 人 | 协作模式 |
|---|---|---|---|
| 评论分类 | 自动标注 category + intent | 看标签，不对可改 | Agent 先做，人可覆写 |
| 垃圾过滤 | 自动标 spam | 漏网手工补标 | Agent 为主，人纠错 |
| 优先级排序 | 自动按 urgency 排 | 看到排序确认 | Agent 排，人确认 |
| 回复草稿 | 自动生成 3 风格 | 选一条 + 编辑 + 发送 | Agent 起草，人定稿 |
| "不回复"决策 | Agent 可标 needs_human | 决定回还是不回 | Agent 建议，人决定 |
| 人设配置 | 语义记忆聚合的数据建议 | 手动改 | Agent 建议，人决定 |

Agent 做排序和建议，人做决策和确认。

### 5-10.2 置信度驱动分流

```
高置信度（>0.85）→ 标绿色，推荐一键确认
  └── praise/low_effort 类，AI 很确定怎么回

中置信度（0.7-0.85）→ 正常流程

低置信度（<0.7）→ 标黄色，"建议仔细编辑后发送"
  └── 默认不推荐直接采纳

极低/无法处理 → needs_human，标红色，"需要你手动回复"
```

### 5-10.3 创作者可配置项

| 配置项 | 默认值 | 说明 |
|---|---|---|
| 默认回复风格 | casual | warm / casual / professional |
| 自动过滤垃圾 | 开 | 关掉后所有评论进 Dashboard |
| 批量确认模式 | 关 | 开后可对绿标评论一键批量发送 |
| 草稿数量 | 3 | 1-3，减少选择负担 |
| 紧急提醒阈值 | high | 哪些级别标记为紧急 |

自动发送不可配置 — 这是安全约束，不是偏好设置。

### 5-10.4 信任建立机制

**首次使用：** 全程用最强模型保证第一印象。首批回复隐藏 risk_warning（创作者还没建立判断力）。

**渐进式信任：** 系统主动提建议（"praise 采纳率 90%，要开批量发送吗？"），但**不自动升级**。信任是创作者主动给出来的。

### 5-10.5 批量模式安全限制

批量模式仅适用于高置信度 + 低风险评论（praise/low_effort）。每条额外检查 SafetyCheckHook。不适用于 confidence < 0.85 的评论。

### 5-10.6 发送确认机制

```
第一层：前端确认弹窗 + 3 秒延迟（防手滑）
第二层：后端校验（comment 归属 + draft 归属 + 防重复发送）
第三层：send_reply 先写 DB 后调 API，失败不自动重试
```

---

## 六、用户产品流程

### 5.1 首次使用流程

```
① 进入 landing page → 看到产品介绍
② 邮箱注册登录（最简注册流程）
③ 安装浏览器扩展（引导页 + 一键跳转 Chrome 商店）
④ 登录小红书网页版 → 扩展自动检测登录态
⑤ 扩展同步 Cookie → 后端存储（加密）
⑥ 首次同步：后端拉取创作者最近 20 篇笔记的评论
⑦ 进入 Dashboard → 看到评论流
⑧ 选择一条评论 → 看到 3 个 AI 回复草稿
⑨ 选择一个草稿 → 编辑或直接发送
⑩ 回复成功 → 评论状态变为"已回复"
```

### 5.2 Dashboard 主界面布局

```
┌──────────────────────────────────────────────────────────┐
│  Logo    📊 Dashboard  📈 数据看板  ⚙ 设置    👤 头像   │
├──────────┬──────────────────────────────────┬────────────┤
│ 筛选     │                                  │            │
│          │  [评论卡片 1]                    │            │
│ ☐ 待回复 │  ┌──────────────────────────┐   │  选中评论  │
│ ☐ 已回复 │  │ 小红书 · @小王爱穿搭      │   │  的详情    │
│ ☐ 垃圾   │  │ 2 分钟前                  │   │            │
│          │  │ "请问这个外套有链接吗？"    │   │  用户历史  │
│ 分类     │  │ 👍 12                      │   │  评论记录  │
│ ☐ 咨询   │  │ [urgent] [question]       │   │            │
│ ☐ 投诉   │  └──────────────────────────┘   │  AI 草稿   │
│ ☐ 好评   │                                  │  ┌───────┐ │
│          │  [评论卡片 2]                    │  │ warm  │ │
│ 紧急度   │  ...                             │  │ ...   │ │
│ ☐ 紧急   │                                  │  ├───────┤ │
│ ☐ 普通   │  [评论卡片 3]                    │  │ casual│ │
│          │  ...                             │  │ ...   │ │
│          │                                  │  ├───────┤ │
│          │                                  │  │ prof. │ │
│          │                                  │  │ ...   │ │
│          │                                  │  └───────┘ │
│          │                                  │            │
│          │                                  │  编辑框    │
│          │                                  │  [发送]    │
└──────────┴──────────────────────────────────┴────────────┘
```

### 5.3 关键交互

| 操作 | 体验设计 |
|---|---|
| 查看评论 | 左侧评论流，类似邮件收件箱。未处理的有颜色标记（红=紧急，黄=咨询） |
| 查看 AI 草稿 | 点击评论 → 右侧展开详情 + 3 个草稿 tab，默认推荐最佳风格 |
| 采用草稿 | 点击"采用"→ 草稿进入编辑框，可直接修改 → 点击"发送" |
| 忽略 | 点击"忽略"→ 评论标记为已读但未回复，24 小时后可再次提醒 |
| 标记垃圾 | 点击"垃圾"→ comment.status='spam'，未来同类评论自动过滤 |
| 批量操作 | 勾选多条 → "全部标记已读" / "批量生成回复" |

---

## 七、单人开发策略

按**依赖关系**而非"多人并行"来决定开发顺序。

### 开发顺序（依赖从底向上）

```
Phase 1 — 基础设施（先跑通底层）
  ├── Docker Compose 启动 MySQL + Redis + Milvus
  ├── DB migration（9 张表）+ Alembic 初始化
  ├── Milvus Collection 创建
  └── .env 配置 + 环境变量注入

Phase 2 — 后端核心（API + Agent 引擎）
  ├── FastAPI 项目启动 + JWT auth
  ├── 9 个 API route 模块逐个实现
  ├── Harness 组件（HookPipeline / ModelProvider / CircuitBreaker 等）
  ├── PlatformAdapter 接口 + XhsAdapter 实现（先只做小红书）
  ├── ClassifyRouterAgent（第一个 Agent，跑通全链路）
  └── ReplyGenerateAgent（第二个 Agent）

Phase 3 — 前端 Dashboard
  ├── Next.js 项目启动 + Tailwind + TanStack Query
  ├── CommentFeed + CommentCard（含虚拟滚动）
  ├── ReplyDraftPanel（草稿查看/编辑/发送）
  ├── FilterSidebar + 搜索
  └── Dashboard 数据概览

Phase 4 — 浏览器扩展
  ├── Plasmo 骨架 + content script 注入
  ├── 小红书 DOM 解析器
  └── 批量上报 + Cookie 同步

Phase 5 — 第二/三平台
  ├── DouyinAdapter + 抖音 DOM 解析器
  └── BilibiliAdapter + B站 DOM 解析器

Phase 6 — 差异化功能
  ├── InsightMiningAgent + 数据看板页面
  ├── 批量操作 + 回复效果追踪
  └── 部署上线（VPS + Docker Compose）
```

### 所有交付物清单（合并 Person A/B/C/D 全部职责）

| 层 | 交付物 |
|---|---|
| Agent 引擎 | BaseAgent + 7 个 Harness 组件 + 3 个 Agent（Classify/Reply/Insight）+ 3 套 System Prompt + Worker 主循环 + eval 脚本 |
| 平台接入 | PlatformAdapter 接口 + 3 个 Adapter + 浏览器扩展（3 平台 DOM 解析）+ Cookie 加密传输 + 去重逻辑 |
| 后端 | FastAPI 项目 + 9 个 route 模块 + MySQL/Redis/Milvus 连接层 + JWT auth + Alembic migration |
| 前端 | Next.js 项目 + 5 页面 + 6 核心组件 + TanStack Query 轮询层 + 响应式适配 |
| 基础设施 | Docker Compose（6 service）+ GitHub Actions CI/CD + Caddy 反向代理 + Sentry 监控 |

---

## 八、接口边界约定

虽然是一人开发，保持接口边界可以让各层独立开发、独立测试。

### Agent ↔ 后端

Agent Worker 直连 MySQL/Redis/Milvus，不通过 HTTP API。Worker 是独立进程，Docker Compose 里单独一个 service。

### 浏览器扩展 ↔ 后端

```
扩展 → POST /api/internal/comments/batch
  Headers: Authorization: Bearer {extension_api_key}
  Body: { "platform": "xhs", "comments": [RawComment, ...] }
  Response: { "received": 15, "new": 12, "duplicates": 3 }

Cookie 同步 → POST /api/internal/cookie
  扩展端 crypto.subtle 加密传输，后端 AES-256-GCM 加密存储
```

### 前端 ↔ 后端

标准 REST。FastAPI 自动生成 `/docs`（OpenAPI），前端对文档开发。先定义 Pydantic Schema → 前端立即开始写页面（可先 mock 数据）。

### Agent ↔ 前端

没有直接通信。Agent 写 reply_drafts 表 → 后端 API 提供数据 → 前端轮询展示。

---

## 九、API Schema（27 个端点）

### 9.1 认证

```
POST /api/auth/register       → { email, password, display_name } → { user_id, access_token, refresh_token }
POST /api/auth/login          → { email, password } → { user_id, access_token, refresh_token }
POST /api/auth/refresh        → { refresh_token } → { access_token, refresh_token }
POST /api/auth/logout         → 204
```

### 9.2 评论

```
GET    /api/comments          → ?platform=&status=&classification=&urgency=&keyword=&page=&sort= → { items, total, urgent_count }
GET    /api/comments/:id      → { comment, post, drafts, user_history, similar_replies }
PATCH  /api/comments/:id      → { classification?, intent?, status? } → CommentDetail
POST   /api/comments/:id/ignore  → { status: "ignored", remind_at }
POST   /api/comments/:id/spam    → 204（级联取消下游任务）
```

### 9.3 草稿

```
GET    /api/comments/:id/drafts       → [DraftCard, ...]
POST   /api/comments/:id/drafts/generate  → { task_id }（异步，前端轮询）
PATCH  /api/drafts/:id                → { content } → DraftCard
POST   /api/drafts/:id/adopt          → DraftCard（is_adopted=true）
POST   /api/drafts/:id/send           → { content } → { sent_at }（3s延迟+防重）
```

### 9.4 批量操作

```
POST   /api/batch/generate-drafts  → { comment_ids[], max=30 } → { tasks[] }
POST   /api/batch/send             → { drafts[{draft_id,content}] } → { results[] }
```

### 9.5 帖子

```
GET    /api/posts       → ?platform=&page= → { items, total }
GET    /api/posts/:id   → PostDetail
```

### 9.6 设置

```
GET    /api/settings/profile       → { tone, phrases, bio, display_name }
PUT    /api/settings/profile       → 更新后 profile
GET    /api/settings/platforms     → [{ platform, username, is_active }, ...]
POST   /api/settings/platforms     → { platform, cookie_data }
DELETE /api/settings/platforms/:id → 204
```

### 9.7 数据看板

```
GET    /api/analytics/overview   → { today_new, pending, urgent, replied, reply_rate, adoption_rate, by_platform }
GET    /api/analytics/insights   → ?period=7d&platform= → InsightReport（InsightMiningAgent 输出）
```

### 9.8 内部接口

```
POST   /api/internal/comments/batch  → { platform, post_url, comments[] } → { received, new, duplicates }
POST   /api/internal/cookie          → { platform, cookie_data }（加密传输）
```

### 9.9 Agent 状态

```
GET    /api/agents/status                  → { classify_router: {status, queue, error_rate}, ... }
POST   /api/agents/:agent_name/resume      → 200（手动恢复熔断）
```

### 9.10 公共数据模型

```
CommentCard：      id, platform, username, content(截断), classification, intent, urgency, status, confidence
CommentDetail：    CommentCard + parent_content, key_points, reasoning, image_urls, reply_count, is_pinned
DraftCard：        id, style, content, is_adopted, is_edited, risk_warning, recommended
PostCard：         id, platform, title, url, thumbnail, published_at, comment_count
PostDetail：       PostCard + content_summary, recent_comments(top5)
```

### 9.11 前端轮询策略

```
Dashboard：GET /api/comments + GET /api/analytics/overview，30s 间隔
草稿生成中：GET /api/comments/:id/drafts，5s 间隔，最多 30s
生成完成 → 停止轮询
```

---

## 十、MVP 开发计划（单人，按 Phase 推进）

不设硬死线，按依赖关系推进。每 Phase 有明确检验标准。

### Phase 1：基础设施 + 后端骨架（预计 1-2 周）

```
□ Docker Compose 一键启动 MySQL + Redis + Milvus
□ DB migration 执行通过（9 张表创建）
□ Milvus 3 个 Collection 创建通过
□ FastAPI 项目启动 + /docs 可访问
□ JWT auth（register/login/refresh/logout）4 个接口可用
□ GET /api/comments + GET /api/comments/:id 接口可用（返回 mock/空数据）
□ POST /api/internal/comments/batch 可用（扩展上报入口）
```

**检验：** curl 调 `/api/auth/register` → 拿 token → 调 `/api/comments` → 返回 200

### Phase 2：Agent 引擎（预计 2-3 周）

```
□ ModelProvider 实现（DeepSeek API 适配）
□ HookPipeline + 2 个 Hook（SafetyCheck + SchemaValidation）
□ ContextBuilder 基础版（暂不做压缩）
□ AgentRunner 模板方法 + Worker 主循环
□ CircuitBreaker + TraceRecorder
□ ClassifyRouterAgent 跑通（含 eval set 100 条验证）
□ ReplyGenerateAgent 跑通（含 intent 驱动回复策略）
□ Classify → Reply 任务串联
□ agent_tasks 表轮询 + 状态流转正常
```

**检验：** 手动插一条评论 → Worker 自动拉取 → 分类完成 → 草稿生成 → reply_drafts 表有 3 条记录

### Phase 3：前端 Dashboard（预计 2 周）

```
□ Next.js 项目启动 + Tailwind + TanStack Query
□ CommentFeed（虚拟滚动） + CommentCard
□ ReplyDraftPanel（查看/编辑/发送）
□ FilterSidebar（平台/状态/分类/紧急度筛选项）
□ 评论搜索（关键词）
□ Dashboard 数据概览（今日新增/待回复/回复率/采纳率）
□ 轮询策略（30s Dashboard / 5s 草稿生成中）
```

**检验：** 打开 Dashboard → 看到评论列表 → 点开一条 → 看到 3 个 AI 草稿 → 选一个编辑 → 点发送

### Phase 4：浏览器扩展（预计 2 周）

```
□ Plasmo 骨架搭建
□ Content script 注入小红书 + MutationObserver 监听
□ 小红书评论区 DOM 解析 → RawComment
□ Background service worker 消息转发
□ 批量聚合（1 秒缓冲）+ 去重（内存 Map 500 条）
□ POST /api/internal/comments/batch 对接
□ Cookie 检测 + 加密同步
□ Popup 展示同步状态 + 今日评论数
```

**检验：** 打开小红书帖子 → 扩展自动抓取评论 → 后端入库 → Dashboard 看到新评论

### Phase 5：第二/三平台（预计 1-2 周）

```
□ DouyinAdapter + 抖音 DOM 解析器
□ BilibiliAdapter + B站 DOM 解析器
□ 扩展补充抖音/B站 content script
□ 平台适配回归测试（三个平台各自拉 20 条评论验证）
```

### Phase 6：差异化功能 + 部署（预计 2-3 周）

```
□ InsightMiningAgent + 数据看板页面
□ 批量操作（生成/发送）
□ 回复效果追踪（reply_performance 定时任务）
□ VPS 部署（Docker Compose + Caddy + Sentry）
□ GitHub Actions CI/CD
□ 同学内测 + 反馈收集
```

**总计预估：** 10-14 周（日均 3-4 小时），不设硬死线。

---

## 十一、模型演进策略（AI 学习路线 Phase 3-4 对应的实践）

### 三阶段路径

```
阶段 1（MVP）: 全 API 调用
  DeepSeek V4 Pro 统一驱动所有 Agent
          │
          ▼  系统积累 is_adopted / is_edited 训练数据
          │
阶段 2（SFT）: 微调替代部分 API
  分类：Qwen2.5-0.5B 微调替代 → 几乎免费
  回复：Qwen2.5-7B 微调学人设 → 替代 70% 调用
  复杂场景仍走 DeepSeek API
          │
          ▼  系统积累 chosen/rejected 偏好对数据
          │
阶段 3（DPO）: 偏好对齐优化回复质量
  DPO 训练 → 回复更精准匹配创作者风格
```

### 数据飞轮

系统 **天然产生训练数据**，不需要额外标注：

| 数据来源 | SFT 用途 | DPO 用途 |
|---|---|---|
| `reply_drafts.is_adopted=true` | 高质量回复正样本 | preferred |
| `reply_drafts.is_edited=true` + `edited_content` | 改进后的回复样本 | chosen (edited) vs rejected (original) |
| `reply_drafts.is_adopted=false` | — | rejected |
| `comments.classification` | 分类标注数据 | — |

### RLHF
不做。PPO 训练不稳定，算力门槛高，只适用于 OpenAI/Anthropic 量级。理解原理即可。

---

## 十二、测试策略

### 10.1 单元测试（不依赖 Agent 上下文，可独立跑）

| 测试对象 | 测试内容 | 依赖 |
|---|---|---|
| HookPipeline | 每个 hook 独立：输入 HookContext → 检查输出 | — |
| ContextBuilder | 预算检查正确性、压缩触发阈值 | — |
| SafetyCheckHook | 所有禁止词（保证/一定/最低价/绝对）+ 边界 case | — |
| SchemaValidationHook | 合法/非法 JSON、缺字段、枚举值非法 | — |
| ModelProvider | mock LLM 响应，验证重试/超时/降级路径 | mock API |
| CircuitBreaker | 模拟连续失败 → 验证熔断触发 + 指数退避恢复 | — |

### 10.2 集成测试

| 测试对象 | 测试内容 |
|---|---|
| AgentRunner + mock ModelProvider | 完整 Agent Loop 走一遍，验证 verify → retry → output 路径 |
| ClassifyRouterAgent | 100 条真实评论 → 检查输出格式 + 置信度分布 + 每类准确率 |
| ReplyGenerateAgent | 50 条 → 人工评估回复质量 + SafetyCheckHook 触发率 |
| ToolRegistry + Agent 配置 | 验证配置切换工具列表生效 |
| HookPipeline + Agent 串联 | 验证 hook 失败不阻塞（SafetyCheckHook）/ 阻塞（RateLimitHook）的差异 |

### 10.3 端到端测试

| 测试场景 | 验证点 |
|---|---|
| 扩展上报 → API → DB → Agent → 草稿 → 前端展示 | 全链路数据一致性 |
| 评论标 spam → 级联取消 → 队列中 reply 任务消失 | 任务取消传播 |
| LLM API 超时 → 重试 3 次 → 降级 → pending_manual | 降级链路完整性 |
| Worker 崩溃 → 重启 → checkpoint 恢复 | 不重复调用 LLM（关键：不能重复烧钱） |

---

## 十三、风险与应对

| 风险 | 概率 | 应对 |
|---|---|---|
| 小红书 Web 版大改版，DOM 结构全变 | 中 | 扩展有版本号，每次改版只影响特定版本；Playwright 定期回归测试 |
| LLM API 费用超预期 | 中 | 分类任务优先用小模型/微调模型替代 API；设置每日 token 预算上限；ModelProvider 支持随时切换更便宜的模型 |
| 小红书封号（Cookie 复用被判异常） | 低 | 操作频率模拟人类（间隔≥2s）；不批量操作；合规声明 |
| 官方不给 API 权限 | 高 | 默认方案就是扩展+Playwright，API 只是加分项 |
| 团队方向分歧 | 中 | 每周日晚上 30 分钟 sync；用接口边界隔离每个人的工作 |

---

## 十四、成本与盈利

**月成本：**
| 项目 | 费用 |
|---|---|
| VPS（2C4G）| ~¥50/月 |
| LLM API（分类用小模型 + 生成用强模型）| ¥150-300/月 |
| 域名 | ¥5/月 |
| Cloudflare R2 | 免费额度内 |
| **合计** | **¥200-350/月** |

**盈利模型：**
- 免费版：1 个平台、100 条评论/月、每天 10 条 AI 回复
- Pro 版 ¥29/月：3 个平台、无限评论、无限 AI 回复、数据看板
- 10 个付费用户 = ¥290/月 = 盈亏平衡
- 50 个付费用户 = ¥1450/月 = 正现金流
