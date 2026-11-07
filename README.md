# CreatorOS · 爆款实验室

让每一次创作都有数据依据。面向 AI 工具、编程教育和知识科普创作者的本地研究工作台，以及用于验收第一单的老板后台。

## Windows 启动

在 PowerShell 中运行。需要 Node.js 20.9+ 和 Python 3.11+。安装脚本也能使用本机已有的 Codex Python 3.12 运行时。

```powershell
Set-Location 'D:\JUNCTION2026\CreatorOS'
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup.ps1
.\scripts\start.ps1
```

默认打开 [首页](http://127.0.0.1:3000)、[登录](http://127.0.0.1:3000/login) 或 [OpenAPI](http://127.0.0.1:8000/docs)。端口被占用时以启动输出为准。脚本只监听 `127.0.0.1`，停止请运行 `.\scripts\stop.ps1`。已安装依赖后可用 `.\scripts\setup.ps1 -SkipInstall` 重新运行迁移和初始化。

首次初始化生成随机管理员密码。仅在本机查看 `data\admin-credentials.txt`，使用同一个登录页登录，进入 `/admin`。普通客户从 `/register` 建立隔离工作区。若需自行指定密码，在全新数据库上先执行迁移，再在 `services\api` 执行 `..\..\.venv\Scripts\python.exe -m app.cli init-admin --email <email>`，按终端提示输入。

## 功能与数据

- **内容研究**：上传 MP4/MOV、图集、图文与 SRT/VTT。单次总计 100 MB，最多 12 个文件，视频不超过 10 分钟、4K。上传后可以预览、查看关键帧、跑本地基础分析，保存编辑版本并导出 Markdown 或 JSON。
- **对标和指标**：从作品库手动录入或导入 CSV，标题、作者、真实来源、采集时间应来自可使用资料。明确点击添加 Demo 才导入示例。指标页支持 CSV/XLSX，`title` 或 `content_id` 必填；可使用 `observed_at,views,likes,comments,shares,favorites`，通过预览映射自定义表头。空指标保留空值。测试样例见 `fixtures`。
- **MiMo**：在项目根目录的 `.env` 配置 `MIMO_API_KEY`，重启服务。默认使用官方按量端点与 Flash/Pro 模型。Token Plan 需配置对应官方地址和凭证。状态检查查询模型列表。用户勾选数据传输和估算预算、点击开始后，才发送所需素材。未配置时可使用本地研究、推荐、数据导入和商业 Demo。
- **老板后台**：留资、报价草案、人工审批、Demo 订单、模拟支付、报告交付、客户验收、工单和周报。Demo 收入独立核算。真实支付、退款、公开发布及数据删除需要人工操作。

## 开发与验收

`apps/web` 是 Next.js 工作台，`services/api` 是 FastAPI、SQLAlchemy 和 Alembic，`data` 保存数据库、私有素材和运行日志，`scripts` 提供 Windows 启停和测试。`.\scripts\test.ps1` 执行 API、前端单测、lint、类型检查和构建。服务运行时可执行 `.\scripts\test.ps1 -Browser`，运行相同检查并以 Edge 验收当前构建。该模式跳过重新构建，避免影响运行中的服务。用于验收的视频可用 `.\.venv\Scripts\python.exe scripts\generate_fixtures.py` 生成。

浏览器验收优先使用本机 Codex 自带的 Playwright。在没有该运行时的机器上，从项目根目录执行 `npm install --no-save --prefix scripts playwright@1.62.1`。可用 `CREATOROS_EDGE` 和 `CREATOROS_CHROME` 指定浏览器 exe，通过 `CREATOROS_BROWSER` 切换浏览器。默认测试只跑本地分析。

需要关闭进程再复制 `data/creatoros.db` 与 `data/uploads`，或使用 SQLite 一致性备份。恢复前先备份当前副本。`.env` 和本地随机账号凭证应单独保管。上传文件经过签名和解码校验，本地版本没有集成防病毒扫描。切换 PostgreSQL 时使用 `postgresql+psycopg://…` 并重新执行 Alembic，现有 SQLite 数据迁移需另行完成。

公开部署前按 [OWNER_ACTIONS.md](docs/OWNER_ACTIONS.md) 配置 TLS、Cookie、备份、访问控制、平台授权及支付提供商。Windows 无法启动时，先检查 `data/logs`，网络问题请核对 npm/PyPI 可达性，Python 可用 `setup.ps1 -PythonPath <绝对路径>` 指定。详细验收见 [TEST_REPORT.md](docs/TEST_REPORT.md)。
