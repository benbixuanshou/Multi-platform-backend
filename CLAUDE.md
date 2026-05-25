# 多 Agent 评论管理平台

## 一句话概述
面向**个人创作者**的 AI-native 跨平台评论管理工具。覆盖**小红书 → 抖音 → B站**三个平台。Agent 引擎驱动（非规则引擎），竞品不做洞察挖掘和人设学习，我们做。

---

## 产品定位

| 维度 | 决定 |
|---|---|
| 目标用户 | 个人创作者（非团队），日均评论 30-200 条，有商业化意愿 |
| 平台覆盖 | 小红书（优先）> 抖音 > B站 |
| 核心差异化 | AI-native 架构、评论洞察挖掘、创作者人设学习、跨平台粉丝识别（MVP不做） |
| 发送模式 | 不自动发送，人在回路确认 |
| 终端 | 仅 Web Dashboard，桌面优先，响应式可用 |
| 用户管理 | 单用户，架构完整（注册/登录/平台绑定） |
| 付费 | MVP 不收费，先内测 |
| 部署 | 本地开发 → 功能完成后租云服务器上线 → 同学内测 |

---

## 竞品格局

### 浏览器扩展类（言灵、Wisecho、秒填 SmartFill、CHAiT）
纯前端插件，无后端、无持久化、无分析能力。本质是"帮你在输入框里打字"。

### 统一管理平台类（SocialEcho、青豆云、易媒、米多客AI、语聚AI）
偏企业客服/销售场景，关键词+规则引擎为主，AI 是后面贴上去的，非原生设计。不服务个人创作者。

### 海外产品（Replient、RepliBee、Aitoearn）
不覆盖中文平台或覆盖很差。

### 市场空白
**没有面向个人创作者的 AI-native 评论管理平台。** ¥29/月区间是真空地带。

---

## MVP 功能清单

### 第一刀：核心闭环（10 项，缺一个产品不成立）
1. 注册/登录 — 邮箱注册
2. 平台账号绑定 — 绑定小红书/抖音/B站 + Cookie
3. 创作者人设配置 — 语气风格（casual/professional/warm）、口头禅、个人简介
4. 评论抓取 — 浏览器扩展捕获 DOM → 标准化 → 批量上报后端
5. 评论去重入库 — 按 platform + platform_comment_id 去重
6. AI 自动分类 — ClassifyRouterAgent 打标签（咨询/投诉/好评/垃圾/中立/UGC金矿）
7. AI 生成回复草稿 — ReplyGenerateAgent 生成 3 种风格草稿
8. 评论流 Dashboard — 列表 + 按平台/状态/分类筛选 + 紧急度排序
9. 草稿查看/编辑/发送 — 选草稿 → 可编辑 → 确认发送 → 回复到平台
10. 评论状态管理 — pending → classified → replied / ignored / spam

### 第二刀：体验必备（5 项）
11. 评论详情页 — 用户历史评论记录、AI 分类理由
12. 基础数据概览 — 今日新增、待回复、回复率、各平台分布
13. 忽略/标记垃圾 — 手动忽略（24h 提醒）或标记垃圾（同类过滤）
14. 评论搜索 — 关键词搜索
15. 批量操作 — 多选 → 批量生成回复 → 一键发送

### 第三刀：差异化（2 项）
16. 评论洞察报告 — InsightMiningAgent：热点话题、粉丝关切、优质UGC、情感趋势
17. 回复效果追踪 — 发完后追踪点赞/回复数变化

### MVP 明确不做
跨平台粉丝识别、自动发送、移动端 App / 小程序、多人协作/权限、付费系统、SSE 实时推送、Playwright 定时任务

---

## 平台覆盖节奏

| 阶段 | 平台 | 检验标准 |
|---|---|---|
| Week 1-2 | 小红书 | 完整闭环跑通（抓取→分类→生成草稿→发送） |
| Week 2-3 | 抖音 | 适配器 + 扩展支持 |
| Week 3 | B站 | 适配器 + 扩展支持 |

---

## Harness Engineering 框架

核心公式：**Agent = Model + Harness**。Model 只提供推理和生成，Harness 把状态、工具、反馈、执行环境和安全边界串起来。

### 十个模块（用于审视系统设计）

| # | 模块 | 核心问题 |
|---|---|---|
| 1 | 上下文管理 | 模型能看到什么？什么时候丢、怎么压缩？ |
| 2 | 工具系统 | 模型能干什么？干错了能不能回滚？ |
| 3 | 执行编排 | 每一步做什么、下一步做什么、用什么模型？ |
| 4 | 状态与记忆 | 跨步骤、跨会话怎么保持连续性？（工作/情节/语义/程序） |
| 5 | Hooks/Middleware | 横切逻辑怎么统一注入？不改 Agent 代码就能加能力？ |
| 6 | 评估与观测 | 系统做得好不好？决策能不能追溯？ |
| 7 | 约束与恢复 | 怎么防跑偏？跑偏了怎么拉回来？（熔断/降级/重试） |
| 8 | 安全沙箱 | Agent 的"牢笼"在哪？真实操作和模拟的边界？ |
| 9 | 反馈闭环 | 好/不好的信号怎么回流驱动改进？ |
| 10 | 人机协作 | 人在回路的哪个位置？哪些步骤可配置？ |

---

## 当前讨论状态

**已对齐的：**
- 产品定位、目标用户、竞品分析、差异化策略
- MVP 功能清单（17 项，三刀）
- 平台覆盖节奏
- Harness Engineering 十个模块框架
- 技术方案文档：[golden-seeking-lobster.md](golden-seeking-lobster.md)

**当前状态：设计阶段完成。** 技术方案文档 [golden-seeking-lobster.md](golden-seeking-lobster.md) 已包含：
- 完整数据模型 + MySQL/Redis/Milvus 三层架构
- 评论全生命周期状态机（含 verify 步骤和降级路径）
- 三个平台的 PlatformAdapter 设计
- 5 个 Agent 的 System Prompt
- 10 个 Harness 模块深度设计（上下文管理 → 人机协作）
- API Schema（27 个端点）
- 技术选型（FastAPI / Next.js / MySQL / Redis / Milvus / 无 LangChain）
- 单人开发策略 + 6 Phase 开发计划
- 模型演进策略（SFT → DPO）
- 测试策略 + 风险应对 + 成本估算

**下一步：开始写代码。**

### 配套文档
- [golden-seeking-lobster.md](golden-seeking-lobster.md) — 完整技术方案（十四章节）
- [ARCHITECTURE.md](ARCHITECTURE.md) — 系统架构全景图
- [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) — 分阶段开发计划（Phase 0-8，每 Phase 独立测试）

---

## 模型训练策略（AI 学习路线 Phase 3-4 对应的项目实践）

### 三种训练方式的定位

| | SFT | DPO | RLHF |
|---|---|---|---|
| 难度 | 低 | 中 | 高 |
| 算力 | 单张 3090 | 单张 3090 | 4×A100 起步 |
| 项目中状态 | **MVP 后期就做** | 攒数据，以后做 | 只了解原理 |
| 面试讲法 | "我用真实采纳数据微调了分类模型替代 API" | "我用用户偏好做对齐优化回复质量" | "我理解 RLHF→DPO 的演进逻辑" |

### SFT 的具体切入路径

系统天然产生训练数据：
- `reply_drafts.is_adopted=true` → 高质量回复样本
- `reply_drafts.is_edited=true` + `edited_content` → 改进后的回复样本
- `comments.classification` → 分类标注数据

微调目标：
1. 分类模型：用积累的 classification 数据微调小模型（Qwen2.5-0.5B）替代 Haiku API → 几乎免费
2. 回复模型：用 is_adopted 的高质量回复微调 7B 模型学习创作者风格 → 只在复杂场景调 Sonnet

### DPO 的数据积累

`reply_drafts` 表自动采集偏好信号：
- is_adopted=true vs is_adopted=false → preferred vs rejected
- is_edited=true 且 edited_content → original vs improved（天然 DPO 偏好对）

等系统跑 1-2 个月攒够数据后做。

### RLHF

不做。PPO 训练极不稳定，算力门槛高，只适用于 OpenAI/Anthropic 量级的公司。理解 SFT→RM→PPO→DPO 的演进逻辑即可，面试能讲清楚就行。

---

## 关键设计决策（来自 golden-seeking-lobster.md）

- **Agent 间通过 agent_tasks 表解耦** — 不直接调用，用数据库表做消息队列
- **Classify 和 Reply 分离** — 分类用轻量模型（便宜），回复用强模型（需推理能力）
- **ModelProvider 抽象** — Agent 不直接绑模型，通过 ModelProvider 接口调用。改配置切换模型，不改代码。当前用 DeepSeek V4 Pro，后续可切 Claude / 本地微调模型
- **PlatformAdapter 接口** — 加新平台只实现接口
- **双通道数据获取** — 浏览器扩展（实时）+ Playwright 定时任务（兜底，MVP 不做）
- **Worker 直连数据库** — 不通过 HTTP API
- **浏览器扩展 ↔ 后端** — 通过内部 API（POST /api/internal/comments/batch）
- **前端 ↔ 后端** — 标准 REST，FastAPI 自动生成 OpenAPI 文档
