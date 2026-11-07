# AI 与工作流实现说明

核查日期：2026-11-07。模块测试未向付费推理接口发送请求。真实服务连通性与付费验收由主工程的实际浏览器流程单独记录。

## 官方接口

- [首次调用](https://mimo.mi.com/docs/zh-CN/quick-start/summary/first-api-call)：默认 `https://api.xiaomimimo.com/v1`；允许 `MIMO_BASE_URL` 覆盖以使用合法 Token Plan 地址。
- [模型列表](https://mimo.mi.com/docs/zh-CN/quick-start/summary/model)：默认轻量模型 `mimo-v2.6-flash`，复杂策略使用 `mimo-v2.6-pro`。
- [Chat Completions](https://mimo.mi.com/docs/zh-CN/api/chat/openai-api-post)：REST `POST /chat/completions`，Bearer 鉴权，`max_completion_tokens=4096`、JSON object 输出和 `thinking.type=disabled`。
- [视频理解](https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/multimodal-understanding/video-understanding)：私有视频编码为含 MIME 的 Base64 数据 URL；`fps=2` 和 `media_resolution=default` 放在视频内容部件层级。图片使用 `image_url` 数据 URL。程序不将 Windows 文件路径当成公开 URL，也不上传至公开对象存储。

## 运行语义

`POST /api/analyses` 的 local 模式会自动创建后台任务；ai 模式只创建待开始分析。只有 `/analyses/{id}/start` 的 `confirm_paid=true`、有效预算、已配置 Key 同时满足才会产生付费调用。后台重试沿用该任务的原始确认和剩余预算。

COO、内容理解、数据分析、本地检索、创作策略、报告质检、商务运营共七个持久化节点；每个节点均有独立 Pydantic 输入与输出。内容和策略在 AI 模式下调用模型，其他节点执行确定性操作。没有足够证据时写明缺失，地方检索不伪造来源。商务节点生成报价范围草案与跟进建议，不发消息、不变更报价、不执行支付。

任务状态包括 QUEUED、RUNNING、WAITING_APPROVAL、SUCCEEDED、FAILED、CANCELED。成功节点的输出保存在数据库中；失败重试跳过成功节点。启动恢复将中断任务标为 FAILED，并要求用户点击重试，不会静默恢复付费请求。任务原始输入快照、分析证据、审计与用户保存的脚本版本均持久化。

模型发现重大合规问题时，质检节点建立 `COMPLIANCE_REVIEW` 审批并暂停。管理员批准后从商务交接继续，不重复前序模型调用；拒绝则取消报告交付。输出检查会移除不在本地来源白名单中的外部链接。模型输出仅作为文本使用，无法执行工具或任意指令。

## 成本与故障处理

- 每次网络请求之前持久化保守费用预留；完成后按返回 Token 用量结算估算。即使响应不是合法 JSON，也保留费用。若进程在请求途中退出，预留仍保留。
- 429 最多三次尝试，等待 1、2 秒指数退避；被明确限流的请求记录为零估算费用。超时不自动重发，以免未知状态的请求重复收费；保守记录并允许人工重试。
- 结构化输出最多两次自动修复（总共三次响应），每次结构失败写入审计。成功分析按工作区、素材/指标/资料库快照、模式和模型配置缓存。
- `MIMO_INPUT_PRICE_PER_MILLION` 与 `MIMO_OUTPUT_PRICE_PER_MILLION` 是管理员可配置的 CNY 估算单价；默认值只是工程预算参数，不代表已核对的实时官方报价。以供应商账单为实际支付依据。
- 预算在每次请求前检查；视频按默认分辨率的官方 Token 估算规则加余量，图片采用保守预留。该预算是估算控制，不是供应商侧硬性扣款封顶。缓存优惠、不同模态/模型单价与服务端计费变化可能使实际账单不同。
- `GET /system/ai-status` 只调用 `GET /models`，结果缓存 60 秒；不发送付费测试提示，不返回 Key。

## 已验证

命令：`.\.venv\Scripts\python.exe -m pytest --noconftest services\api\tests\test_ai.py -q`

离线测试覆盖官方请求形状、429 退避、JSON 修复上限、费用记录、预算阻断、无密钥、取消检查与完成竞态、状态接口只读探测、本地报告真实缺失说明、七节点重试、启动恢复、组织隔离、缓存、确认付费门槛、进程中断的费用预留、合规批准后续跑、链接质检以及私有视频 Base64 格式。离线提供商响应使用 MockTransport。真实接口和有效测试视频的验收见主测试报告。

策略模型只生成标题、开头、脚本、改进清单与实验草案。报告由服务端组合，证据沿用内容拆解，指标沿用数据库统计。模型结构错误记录失败字段和错误类型，日志省略原始响应和用户材料。

测试运行有一个 Starlette 关于 httpx 测试客户端的依赖弃用提示，不影响通过。Windows 受限沙箱可能阻止 TestClient 使用本地套接字；在授权的普通本机进程中执行可通过。

## 当前限制

- 单机开发工作线程，依赖数据库持久化与手动恢复；不应直接启用多个独立 Uvicorn worker 作为分布式队列。
- 取消会停止后续阶段；已经送达供应商的请求无法撤回，可能计费。
- 本地模式不会理解画面、识别语音或判定知识准确性；脚本和结构是明确标记的可编辑建议。
- 视频原始文件上限 35 MiB（编码后留出 50 MB 限制余量），图片单个上限 12 MiB，单次最多 8 个媒体，总编码内容额外限制。超限媒体跳过并写入局限；整个请求超限则提示压缩/裁剪。本版本不自动分段理解长视频，不做音频转录。
- 检索节点只查询本工作区最多 200 个非 Demo 资料，采用词项相似度召回，不声称拥有联网搜索或向量语义模型。
- 模型事实与画面判断仍需用户检查；结构校验、来源约束和合规标记不能构成事实正确性的保证。人工审批只是交付控制，不替代专业合规审查。
