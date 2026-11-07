# CreatorOS 架构

```mermaid
flowchart LR
  Browser[Edge / Chrome] --> Web[Next.js 中文工作台]
  Web -->|同源 API / HttpOnly Cookie| API[FastAPI / RBAC / 组织隔离]
  API --> DB[(SQLite / Alembic)]
  API --> Media[私有素材目录 / FFmpeg / PySceneDetect / Pillow]
  API --> Worker[持久化 AgentRun / AgentStep]
  Worker --> DB
  Worker -->|明确确认和预算| MiMo[官方 MiMo REST]
  API --> Gate[老板审批 / Demo 订单]
  Gate --> DB
```

会话令牌随机生成，数据库仅存 SHA-256 摘要，密码使用 Argon2。API 查询通过用户工作区限定。客户线索由登录会话绑定身份，老板审批后创建跨角色可见订单，客户只可验收关联订单。素材文件通过授权 API 读取，数据库保留原文件名和随机私有存储路径。对标链接仅保存与显示，服务端不抓取任意 URL。

```mermaid
erDiagram
  ORGANIZATION ||--o{ MEMBERSHIP : owns
  USER ||--o{ MEMBERSHIP : joins
  ORGANIZATION ||--o{ CREATOR_ACCOUNT : owns
  CREATOR_ACCOUNT ||--o{ CONTENT_ITEM : publishes
  CONTENT_ITEM ||--o{ CONTENT_ASSET : has
  CONTENT_ITEM ||--o{ CONTENT_ANALYSIS : yields
  CONTENT_ITEM ||--o{ METRIC_SNAPSHOT : observed
  CONTENT_ITEM ||--o{ CONTENT_VERSION : revises
  CONTENT_ANALYSIS ||--o{ ANALYSIS_EVIDENCE : cites
  CONTENT_ANALYSIS ||--o{ AGENT_RUN : starts
  AGENT_RUN ||--o{ AGENT_STEP : executes
  AGENT_RUN ||--o{ COST_EVENT : estimates
  BENCHMARK_ITEM ||--o{ RECOMMENDATION : appears
  CONTENT_ANALYSIS ||--o{ EXPERIMENT : motivates
  LEAD ||--o{ QUOTE : receives
  SERVICE_PLAN ||--o{ QUOTE : prices
  QUOTE ||--o| ORDER : authorizes
  ORDER ||--o| PAYMENT_RECORD : records
  ORDER ||--o{ DELIVERY : fulfils
  CONTENT_ANALYSIS ||--o{ DELIVERY : attaches
  ORDER ||--o{ TICKET : supports
```

`Approval` 记录审批种类、目标 ID、审查意见及状态。`AuditLog` 保存操作者、动作和时间。报价、订单和支付有独立实体及状态。模拟金额只进入 Demo 统计。

```mermaid
stateDiagram-v2
  [*] --> QUEUED
  QUEUED --> RUNNING
  RUNNING --> SUCCEEDED
  RUNNING --> FAILED
  RUNNING --> CANCELED
  QUEUED --> CANCELED
  RUNNING --> WAITING_APPROVAL
  WAITING_APPROVAL --> QUEUED
  WAITING_APPROVAL --> CANCELED
  FAILED --> QUEUED
  CANCELED --> QUEUED
```

COO 建立任务和预算，依次交接给内容拆解、数据分析、对标检索、创作策略、报告质检和商务运营。步骤使用结构化输入输出。历史步骤和结果按工作区持久化，重试从失败步骤继续。后台任务为单机实现，服务重启会标记中断，需重新发起。外部调用取消是协作式，已发送的请求仍可能产生费用。
