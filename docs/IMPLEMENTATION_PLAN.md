# CreatorOS Implementation Plan

**Goal:** 交付用户指定目录内可运行、可演示、可验收的研究与一人公司平台。

**Architecture:** Next.js 同源代理 FastAPI。SQLAlchemy 显式表关联、SQLite 默认、Alembic 迁移。工作线程执行持久化 Agent 状态机。

**Tech Stack:** Next.js/TypeScript/Tailwind/Recharts、FastAPI/Pydantic/SQLAlchemy/Alembic、pytest/Vitest/Playwright。

1. 环境与配置：检查 Python/Node/浏览器/端口，创建虚拟环境和锁文件，保护密钥，提供可重复安装脚本。
2. 数据与安全（services/api/app/{models,db,auth,main,content}.py）：先验证注册、会话、越权和上传限制，再实现模型、随机私有存储、媒体解析。
3. AI（services/api/app/{mimo,workflow,analysis}.py）：先测试无 Key、429、JSON、预算和恢复，再实现官方适配、六阶段处理、取消、报告与版本。
4. 研究商务（services/api/app/business.py）：测试缺失指标/去重/来源/状态转移，再实现账号、导入、推荐、实验、CRM、报价审批、Demo 订单、交付工单和周报。
5. Web（apps/web）：实现每个任务书路由，使用实际 API、空状态和表单验证。typecheck、Vitest、build 后执行浏览器流程。
6. 集成：setup/start/stop/test 脚本、管理员随机凭证、安全测试、生成带 TEST 标识的素材、跑一条持久化 Demo 订单。
7. 验收：pytest、前端检查和 build、Edge/Chrome E2E、移动视口、截图、审计日志与最终报告。所有外部限制写 OWNER_ACTIONS。

每个模块先写关键行为测试，记录首次失败，再实现并复测；对接依赖通过下述 CONTRACT.md 固定。
