# CreatorOS v1 · 接口与数据约定

完整参数、校验和返回结构以运行中的 `/docs` 和后端代码为准。本文件记录模块边界，使用 snake_case JSON，业务接口统一以 `/api` 开头。

## 公共约定

列表通常返回 `{items, total}`。ID 为字符串。错误返回 `error.code`、`error.message`，验证错误省略原始敏感输入。业务数据以 organization_id 以及显式客户关联控制权限；管理员端还验证 OWNER_ADMIN。

密码使用 Argon2，Session 保存 token_hash 与 expires_at，原始令牌只存 HttpOnly Cookie。实体的 data JSON 保存可选元数据，不能替代归属校验。外来实体 ID 在操作前经 owned 或对应业务访问函数验证。

## 认证与基础资料

- `POST /auth/register`、`POST /auth/login`：email、password、可选 name、remember_me；默认记住登录 30 天，false 使用非持久 Cookie。
- `GET /auth/me`、`POST /auth/logout`：读取当前身份、撤销当前会话。
- `GET /dashboard`：工作区统计及相同口径的明细。
- `GET/POST /contents`、`GET /contents/{id}`：作品与背景。
- `POST /assets/upload`：multipart files、title、text 和可选作品背景，创建作品及私有素材。
- `GET /assets/{id}`：经授权的文件预览或下载。
- `GET /settings/export`、`POST /settings/deletion-request`：用户范围的数据导出与删除申请。

同一工作区的新建／改名作品标题不能重复；原文件名和私有随机路径保留，界面、下载和审批使用可读作品标题。

## 分析与实验

- `POST /analyses`：content_id、mode=local 或 ai。创建 AI 分析不触发付费调用。
- `POST /analyses/{id}/start`：confirm_paid、budget、allow_web_search；预算最高 10 元，外部调用须授权并配置服务。
- `GET /analyses`、`GET /analyses/{id}`：分页历史、报告和步骤。
- `PATCH /analyses/{id}`：备注；`DELETE /analyses/{id}`：受保护的历史隐藏，非素材物理删除。
- `GET /tasks/{id}`、`POST /tasks/{id}/cancel`、`POST /tasks/{id}/retry`：状态与恢复。
- `GET /analyses/{id}/export?format=markdown|json`、`POST /analyses/{id}/versions`、`GET /contents/{id}/versions`：导出和版本。
- `POST /analyses/{id}/experiments`：task_index，按所选报告建议幂等创建关联实验。
- `GET/POST /experiments`、`PATCH /experiments/{id}`：研究实验管理。
- `GET /system/ai-status`：只读配置与模型列表，不返回 Key，不发付费测试提示。

七阶段：COO、content、data、retrieval、strategy、quality、business。报告保留 summary、findings、titles、hooks、script、tasks、source 及结构化 fact_checks、sources、search_status、media_received 等字段。旧 limitations 为兼容／导出保留，界面改用精简必要说明。

## 研究与数据

- `GET/POST /accounts`、`GET/PATCH /accounts/{id}`、`POST/GET /accounts/{id}/avatar`：创作者档案及头像。
- `GET/POST /library`、`POST /library/import`：手工和 multipart CSV/XLSX、可选 covers 导入。
- `GET/DELETE /library/{id}`、`GET /library/{id}/cover`、`POST /library/{id}/favorite`：资料和封面。
- `POST /library/demo`：显式导入 Demo 样例。
- `POST /recommendations/search`：query、可选 content_id、limit、include_demo。
- `POST /metrics/preview`、`POST /metrics/import`：表格和映射预览／导入。
- `DELETE /metrics/imports/{file_sha256}`：删除本人工作区对应指标批次。
- `GET /analytics/overview`：趋势、排行、比较、来源和口径。

指标缺失保持空值；外部链接仅保存与显示，不由后端任意抓取。引用及封面操作均遵循工作区权限。

## 客户、订单与老板后台

- `GET /services`：当前可用服务，按价格升序；`POST /leads` 需要登录客户身份。
- `GET/POST /orders`、`POST /orders/{id}/confirm`、`POST /orders/{id}/accept`：客户下单、确认报价订单、确认验收。
- `GET/POST /tickets`、`PATCH /tickets/{id}`：客户关联的咨询、回复和处理状态。
- `GET /admin/overview`、`GET/PATCH /admin/leads` 及详情：公司与线索。
- `/admin/services`、`/admin/quotes`：服务配置、报价及审批。
- `/admin/orders` 与 `/admin/orders/{id}/accept|complete|deliver`：报价订单、接单、完成服务或交付报告。
- `GET /admin/tickets`、`GET /admin/finance`、`GET /admin/weekly-report`、`GET /admin/agents`、`GET /admin/data`：工单、经营与审计。
- `GET /approvals`、`POST /approvals/requests`、`POST /approvals/{id}/decision`：人工决策，reason 必填。

定制报价订单先 AWAITING_CUSTOMER，客户确认后 REQUESTED；直接确认的服务订单进入 REQUESTED。老板接单后 IN_PROGRESS，交付后 DELIVERED，客户二次确认后 COMPLETED。接单及确认保持幂等。

当前按已接单金额记账，未接资金支付。旧 simulate-payment 入口停用，旧 Demo 退出当前统计。客户回复与内部备注分开；工单本身不生成订单。退款、发布、真实付款与删除等审批批准不代表外部操作已执行。
