# CreatorOS v1 · MiMo 与工作流

实现：`services/api/app/mimo.py`、`workflow.py`、`schemas_ai.py`、`fact_check.py`。主流程使用官方 MiMo REST，不把开发工具所用模型或账号当作产品凭证。

## 七阶段交接

- COO：保存输入快照、预算与用户确认。
- content：本地结构检查，或在 AI 模式调用轻量模型理解实际素材。
- data：读取指标快照并计算可支持的结论。
- retrieval：本地作品召回；用户授权后调用内置联网搜索核查公开事实。
- strategy：调用策略模型生成标题、三个开头、完整脚本和修改建议。
- quality：校验报告结构、引用来源和交付条件，重大问题进入人工审批。
- business：形成交付与跟进草案，不自动发布或收付款。

不是每个阶段都请求一次大模型。阶段输入、输出、重试、用量和错误保存在数据库中。

## 接入与素材

默认按量端点 `https://api.xiaomimimo.com/v1`，通过 `.env` 配置 Key、端点与模型。默认 `mimo-v2.6-flash` 用于理解与核查，`mimo-v2.6-pro` 用于策略。Token Plan 需使用相应官方配置。

图片以 `image_url` Base64 输入，视频以 `video_url` Base64 输入；本地 Windows 文件路径不作为远程 URL。小视频使用视频内容层级的 fps=2 和默认分辨率。为适配编码体积限制，较大视频改用实际关键帧及时间码；较大图片只在请求内缩放，不改原文件。口播分析可补充字幕或文稿，当前未启用自动 ASR。

MiMo 内置联网搜索需在控制台开通插件；每次核查限制搜索次数并纳入预算。事实来源取服务返回的引用，模型自行给出的未返回链接不能标为已查证。插件不可用或无来源时，报告保留待核对状态。策略使用画面观察和核查结果，而非仅文件名与元数据。

历史报告保留，通过“重新识别与核查”重新生成。联网未完成的报告不会被已完成缓存挡住。报告界面只展示必要说明和待审阅事项，不评估作者身份真实性。

## 费用与恢复

AI 创建分析记录不等于开始收费；显式确认、有效预算和服务端配置齐备后才开始。用户预算最高 10 元，调用前预留估算费用，收到响应后记录返回用量。搜索单价同样可配置，实际以供应商账单为准。

429 有界退避；网络超时保留保守费用，不盲目重发未知结果的请求。JSON 输出最多两次结构修复，失败响应也记录费用。取消阻止后续调用，不能撤回已发送请求。服务重启将中断任务标记失败，等待用户重试，已成功阶段继续复用。

模型输入与输出均作为不可信数据处理。模型无法直接执行程序、修改付款状态或调用任意外部网站。`/system/ai-status` 只读模型列表并缓存，不发付费测试提示、不返回 Key。

## 参考与验证

- [MiMo 首次调用](https://mimo.mi.com/docs/zh-CN/quick-start/summary/first-api-call)
- [视频理解](https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/multimodal-understanding/video-understanding)
- [图片理解](https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/multimodal-understanding/image-understanding)
- [联网搜索](https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/text-generation/tool-calling/web-search)

离线测试使用模拟传输，不消耗真实推理额度；此前实际 MiMo 理解与策略验收和本轮检查见 TEST_REPORT.md。配置、账号权限和真实支付类操作由所有者完成。
