# CreatorOS v1

**CreatorOS · 爆款实验室 — 让每一次创作都有数据依据。**

面向创作者的内容研究工作台，配套一人公司运营后台。支持 Windows 桌面入口与本地 Web：从作品上传、MiMo 画面识别与创作建议，到关联实验、客户咨询、报价、接单、交付与验收，记录完整过程。

本仓库是第一阶段源码交付。完整产品、使用和工程说明见 **[项目说明书](docs/PROJECT_GUIDE.md)**，版本变化见 [CHANGELOG](CHANGELOG.md)。

## 已实现

- **内容研究**：图片、视频、图集、文稿与字幕上传；真实素材预览及弹窗放大；作品标题唯一校验；本地基础分析与 MiMo 深度分析。
- **AI 协作**：七阶段持久化工作流、运行动画、失败节点重试、取消、预算预留、报告版本及导出。图片和小视频送模型识别，较大视频使用真实关键帧。
- **事实核查**：按用户确认调用 MiMo 联网搜索，将有来源的事实偏差和未能查证的事项交给用户审阅，结合结果生成标题、开头和脚本草案。
- **研究积累**：对标资料库、CSV/XLSX 与封面导入、检索筛选、收藏、指标快照、趋势和排行、创作者档案与头像、由修改建议直接创建实验。
- **客户服务**：注册客户咨询、客户与老板同步的需求状态和回复、客服工单、订单交付与确认验收。
- **经营后台**：服务与报价管理、人工审批、接单金额统计、模型成本估算、审计和经营周报。历史模拟业务不进入当前经营统计。
- **桌面体验**：双击图标启动、本地服务自动连接、单实例、隔离渲染、默认记住登录 30 天；主动退出撤销会话。

**当前经营金额表示已确认并接单的订单金额，尚未接入真实收付款。** 本地模式不调用付费模型；AI 模式需配置凭证并确认预算。项目不提供图像或视频生成。

## 环境

- Windows 10/11、PowerShell。
- Node.js **24 LTS**，或 22.12+ 的 Node 22；Python **3.11+**，推荐 3.12。
- Git；首次安装需可访问 npm、PyPI 和 Electron 下载源。
- 默认 SQLite，无需 Docker。FFmpeg 使用项目依赖提供的运行程序。

## 快速开始

在新目录中克隆。私有仓库需要 GitHub 账号具有访问权限。

```powershell
git clone https://github.com/sunpeng10/CreatorOS-v1.git
Set-Location .\CreatorOS-v1
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup.ps1
.\scripts\start.ps1
```

默认访问：

- 首页：<http://127.0.0.1:3000>
- 登录：<http://127.0.0.1:3000/login>
- API 文档：<http://127.0.0.1:8000/docs>

端口被占用时以脚本输出为准。初次初始化的随机管理员凭证只写入本机 `data/admin-credentials.txt`，不会进入 Git。普通用户从 `/register` 注册独立工作区。

停止项目服务：

```powershell
.\scripts\stop.ps1
```

### Windows 桌面图标

先完成上面的初始化，再运行：

```powershell
.\scripts\install-desktop.ps1
```

双击桌面上的 **CreatorOS 爆款实验室** 即可进入。`CreatorOS.cmd` 是本机运行包的备用入口。关闭桌面窗口后，本地服务继续运行；移动项目目录后重新建立入口。详见 [桌面说明](docs/DESKTOP.md)。

### 启用 MiMo

`setup.ps1` 在缺少配置时复制 `.env.example` 为 `.env`。在本机 `.env` 中填写自己的 `MIMO_API_KEY`，按需调整官方端点与模型，然后重启服务。

- 默认模型：`mimo-v2.6-flash` 与 `mimo-v2.6-pro`。
- 联网核查需要 MiMo 控制台开通联网服务插件。
- 单任务预算由用户设置，最高 10 元；所有费用均为估算，以供应商实际账单为准。
- 首次使用或升级登录记忆后，勾选“记住登录（30天）”登录一次。

无 Key 时可正常使用本地分析、资料库、数据导入和其他本地业务功能。凭证配置及尚待外部接入的事项见 [OWNER_ACTIONS](docs/OWNER_ACTIONS.md)。

## 工程结构

```text
apps/web/         Next.js + React + TypeScript 中文界面与同源 API 代理
apps/desktop/     Electron 桌面外壳、打包及会话持久化
services/api/     FastAPI、SQLAlchemy、Alembic、AI/研究/商务逻辑
fixtures/         明确标注 TEST / DEMO 的测试样例
scripts/          Windows 安装、启停、检查与维护脚本
docs/             项目说明、架构、模块说明、验收记录
```

`data/`、`web_data/`、`.env`、账号凭证、客户上传、数据库、日志、依赖目录及桌面运行包均留在本机。仓库保留源码、锁定依赖、迁移脚本和项目静态资源，新机器通过安装脚本重建环境。

## 检查

```powershell
# 后端测试
.\.venv\Scripts\python.exe -m pytest services/api/tests -q

# 前端测试与构建
npm.cmd --prefix apps/web test
npm.cmd --prefix apps/web run build

# 桌面逻辑测试，不启动桌面窗口
npm.cmd --prefix apps/desktop test
```

完整工程检查入口是 `.\scripts\test.ps1`；浏览器验收是显式可选项，见 [验收记录](docs/TEST_REPORT.md)。测试模型响应采用模拟传输，不需要真实付费调用。

## 文档导航

- [项目说明书：使用、配置、业务与维护](docs/PROJECT_GUIDE.md)
- [架构与数据关系](docs/ARCHITECTURE.md)
- [MiMo 与工作流](docs/AI_NOTES.md)
- [研究、订单与经营口径](docs/BUSINESS_NOTES.md)
- [Windows 桌面版](docs/DESKTOP.md)
- [操作演示](docs/DEMO_SCRIPT.md)
- [版本交付说明](docs/FINAL_REPORT.md)
- [验收记录](docs/TEST_REPORT.md)
- [所有者操作](docs/OWNER_ACTIONS.md)

GitHub 保存项目源码，不会自动启动服务或发布网站。公网访问、真实资金、外部发布、自动语音转录及生产部署仍需后续配置或开发。
