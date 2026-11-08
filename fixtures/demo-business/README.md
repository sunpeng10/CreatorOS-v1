# 脱敏业务演示数据

本目录是本机业务数据库（`data/creatoros.db`）的**脱敏导出快照**，用于让评审和新环境了解 CreatorOS 业务闭环中已产生的记录：作品与分析、对标资料、指标、创作实验、客户线索、服务报价、订单交付、收款记账、工单与审批。

## 脱敏规则

- 邮箱统一替换为 `userNN@example.test`（跨表一致，同一对象在不同表中保持可关联）；`@example.test`、`@creatoros.local` 的测试账号保留原值。
- 手机号替换为 `1380000NNNN` 形式的占位号。
- 密码哈希、会话令牌、`data` 中的内部字段不出现在导出中；`admin-credentials.txt` 等本机凭证文件从不导出。
- UUID 与业务字段原样保留，导出脚本会先保护 UUID 再脱敏，避免误改。

## 内容

| 文件 | 说明 |
| --- | --- |
| `users.csv` / `organizations.csv` / `memberships.csv` | 账号与工作区 |
| `creator_accounts.csv` / `content_items.csv` / `content_analyses.csv` / `content_versions.csv` | 创作者档案、作品、分析与版本 |
| `experiments.csv` / `recommendations.csv` | 创作实验与建议 |
| `benchmark_items.csv` / `metric_snapshots.csv` | 对标资料库与指标快照 |
| `leads.csv` / `service_plans.csv` / `quotes.csv` / `orders.csv` / `deliveries.csv` / `payment_records.csv` | 客户线索、服务报价、订单交付与接单记账 |
| `tickets.csv` / `approvals.csv` / `cost_events.csv` | 工单、人工审批与模型费用估算 |

编码为 UTF-8 BOM，Excel 可直接打开。

## 重新生成

```powershell
.\.venv\Scripts\python.exe scripts\export_demo_business.py
```

需要本机 `data/creatoros.db` 存在。本目录是某一时点的快照，不随本机业务数据自动更新。
