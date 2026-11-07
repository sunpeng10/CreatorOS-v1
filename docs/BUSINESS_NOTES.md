# 研究与商务模块说明

实现位于 `services/api/app/business.py`、`business_common.py`、`business_research.py` 与 `business_commerce.py`。主应用将 router 挂到 `/api`。

## 数据与权限

- 默认查询按已登录用户的组织隔离。管理员入口使用服务端 OWNER_ADMIN 校验；所有引用 ID 在写入前校验归属。
- 公开留资始终分配给初始化后的首个老板组织，不接受请求体指定组织。用户已登录时，从服务端会话记录客户用户/组织；该关联由 Lead 复制到 Quote 和 Order，不能由报价请求自行指定。
- 客户可查看、验收分配给其组织的订单；报告必须属于关联客户组织，或无客户关联时属于老板自有工作区。陌生组织无法通过改 ID 访问。
- 公开服务只提供老板组织启用的试运营方案。没有初始化管理员时，留资返回 503，服务列表为空。
- 操作写 AuditLog；管理员数据页面可查看本组织最近 200 条审计及导入批次。备份/恢复保持人工本机操作，不接收任意文件路径。

## 对标与推荐

- 手工录入、CSV/XLSX 导入；按规范化来源 URL 去重，无 URL 则按平台、作者、标题去重。去重在当前组织内进行，Demo 与用户真实资料分开。
- 不抓取来源 URL。仅接受 http/https 且不含用户名密码的链接；渲染时由前端按文本处理。
- `/library/demo` 是显式操作，导入 5 条虚构示例。`fixtures/DEMO-benchmarks.csv` 另提供可导入样例，`is_demo=true` 将完整保留。
- 推荐默认排除 Demo。只有 `include_demo=true` 时才返回示例；标题、来源及 `is_demo` 均标识演示性质。
- `local-tfidf-zh-v1` 使用英文单词、中文单字/双字的 TF-IDF 与余弦相似度；标题、类别、文稿、标签、受众、结构参与特征。排序可复现，不调用模型、网络或下载嵌入模型。
- 相似度 `similarity` 与 `relative_performance` 独立展示。后者为本作品播放量 / 同平台同作者最近最多 30 条可用播放量中位数，至少 3 条样本且中位数大于零才计算。采样不足返回 null，不把绝对播放量叫作爆款。
- 返回共同特征、来源、采样时间、指标完备度和借鉴边界。请求数量 3–10；库中不足时返回实际数量，不补造样本。

## 指标导入与分析

- `POST /metrics/preview` 与 `/metrics/import` 接收 multipart `file`、可选 `account_id`、可选 `mapping` JSON 文本。
- 推荐映射方向为 `{"views":"播放量列名","title":"标题列名"}`，也兼容反向映射。内置常见中文列名识别。
- 支持 CSV（UTF-8/UTF-8 BOM/GB18030）与 XLSX。文件限 5 MB、最多 5000 行/100 列，Excel 解压后限 50 MB；空表、重复表头、损坏文件、负数/非整数/非有限值均有明确错误。
- 字段：title 或 content_id 必填；views、likes、comments、shares、favorites、impressions、followers 可空；observed_at 为 ISO 日期/时间；category、platform、published_url 与 is_demo 可选。
- 空白/null/N/A 保留 null；显式 0 保留 0。任意校验失败时整批不写入。相同账号、作品、观测时间和指标内容去重；重命名同一文件不重复入库。
- 保留源文件名、SHA-256、原始行号、是否自动补观测时间。原始上传表格不长期保存，减小个人信息保留范围；快照保存可追溯来源标识。
- `fixtures/DEMO-metrics.csv` 全为虚构演示统计，含缺失字段与两次时间快照；导入后 `is_demo`、`source_kind=demo_fixture` 保留。
- 分析接口 `items`/`rankings` 使用每个作品最新快照；`trends` 返回各次观测；`category_comparison` 返回类别样本数、可用播放样本数与中位数。
- 互动率为 `(likes + comments + shares + favorites) / denominator`，分母支持 views/impressions/followers。任一必要项缺失或分母为零时为 null。累计快照不自动视为新增量。
- 实验保存原作品文本/版本快照、假设、修改计划、观测窗口、后续作品与前后指标快照。结果输出绝对/相对变化及“不足以证明因果”的限制。

## 商务状态与审批

- 报价：PENDING_APPROVAL → APPROVED / REJECTED。修改待审或拒绝的报价会作废旧审批并创建新的审批；已批准报价不可原地修改。
- 订单仅从 APPROVED 报价创建，同一报价只能产生一个订单；金额来自报价，客户端不能改写订单金额。
- 当前只允许 `is_demo=true`。状态：AWAITING_PAYMENT → PAID → DELIVERED → COMPLETED。模拟支付有唯一订单约束与幂等响应；交付要求 SUCCEEDED 且非空报告；验收只允许已交付状态。
- 已登录客户的留资→报价→订单→自有报告交付→客户验收链路可完整持久化。老板自有工作区也可完成比赛 Demo。
- 工单类型 QUESTION、REVISION、COMPLAINT、REFUND。退款工单创建人工审批，不能直接绕过 WAITING_APPROVAL 改为已处理。
- 人工批准 Demo 退款后，付款记录标为 DEMO_REFUNDED，订单 REFUNDED。真实退款、公开发布、真实付款及数据删除仅记录审批和待人工执行状态，没有任何外部资金/发布/删除调用。
- 审批 `reason` 必填；相同决定可重放，已处理审批不能反向修改。报价审批比对金额快照防止过期授权。
- COMPLIANCE_REVIEW 审批与暂停的 AgentRun/ContentAnalysis 联动：驳回取消任务；批准保留已完成节点，并在审批事务提交后排队恢复执行。
- `POST /approvals/requests` 供管理员准备 PUBLISH_CONTENT / REAL_PAYMENT 请求，字段为 kind、target_id、reason。前者只能引用本组织已成功的分析；后者只能引用本组织已批准报价或待付款订单。重复待审批请求幂等；批准后仍为 MANUAL_ACTION_REQUIRED，不发布、不产生真实收付款记录。

## 财务口径与验证

- `/admin/finance` 分列 demo_revenue、demo_refunds、real_revenue、model_cost_estimate、estimated_real_margin。Demo 收入不与真实收入合并。
- 金额总和用 Decimal；模型费用依已记录 CostEvent 估算；真实毛利未包含人工、税费及其他成本。当前未配置真实支付供应商，因此接口不能制造真实收款。
- 模型费用也包含通过本组织 Delivery 和订单客户组织明确关联的报告费用；未交付、未关联的客户分析费用不可见。跨组织费用只返回模型、用量、费用等必要标量，不返回客户 Agent 输入输出。
- 老板 Agent 监控仅查看本组织；快照中的 credential 字段、Bearer 值与密钥格式文本会脱敏，保留正常 token 用量。
- 周报统计 UTC 最近 7 天、创建时间位于窗口内的记录，由确定性数据库计算生成 Markdown，未调用付费模型。
- `services/api/tests/test_business.py` 已覆盖 16 个用例：缺失指标、中文推荐/作者中位数、组织隔离、CSV 去重、订单审批/支付/交付/验收、公开线索组织安全、实验归属、Demo 排除、XLSX 映射/损坏、报价变更审批、空表/URL 校验、客户链路与退款、Demo 指标标识、合规审批驳回/批准与提交后调度。
- 验证命令：`.\.venv\Scripts\python.exe -m pytest services/api/tests/test_business.py -q`（设置 `PYTHONPATH=services/api`）。2026-11-07 运行结果 16 passed。Windows 受限沙盒会阻止 asyncio 的本机 socketpair，需允许本机回环；测试本身不访问外网。
- 当前依赖输出一条 Starlette/httpx 测试客户端弃用警告，不影响上述结果。端到端浏览器与全工程集成结果见主测试报告。
- 最后追加了人工发布/真实支付请求、明确关联客户交付费用及 Agent 快照脱敏测试（总计 19 个），最终完整 API 套件已通过。见主工程测试报告。
