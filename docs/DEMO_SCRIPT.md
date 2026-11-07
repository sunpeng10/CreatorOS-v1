# CreatorOS 三分钟演示

**0:00–0:30，官网和工作区。** 从首页打开注册，创建一个 TEST 客户工作区。说明免费本地分析与 MiMo 深度分析的区别，切到素材分析页。首页截图见 `screenshots/edge-01-home.png`。

**0:30–1:20，研究一份作品。** 上传 `data/test-fixtures/TEST-creatoros.mp4` 和 `fixtures/TEST_字幕.srt`，标题填 `TEST Python 函数入门`。选择本地基础分析，查看镜头时间区间和关键帧、报告证据、改进脚本与步骤记录。需要 AI 时先核对设置，选择预算并明确确认。报告截图见 `screenshots/edge-02-report.png`。

**1:20–2:00，对标、指标和实验。** 在作品库显式添加 Demo 样本，以“Python 编程函数教学”检索并勾选 Demo。解释相似度与相对表现各自口径。导入 `fixtures/TEST_指标.csv`，展示缺失指标与趋势，回到报告创建关联实验。截图见 `screenshots/edge-03-analytics.png`。

**2:00–3:00，拿下第一单。** 客户登录状态下提交留资。用独立浏览器登录老板账号，打开线索，新建报价并审批，创建 DEMO 订单，点击模拟支付，用客户报告 ID 交付。切回客户确认验收，在老板后台查看审计记录和周报。截图见 `screenshots/edge-04-orders.png` 和 `screenshots/edge-05-finance.png`。

可用 `.\.venv\Scripts\python.exe scripts\generate_fixtures.py` 重新生成视频。浏览器验收脚本会自动生成明确标记的客户、作品、实验、线索、报价和 Demo 订单记录。
