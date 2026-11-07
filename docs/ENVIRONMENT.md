# 本机环境

- 工作区 `D:\JUNCTION2026\CreatorOS` 初始只有任务书。同级目录包含其他参赛项目，均保持原样。
- Windows 内核版本 10.0.26200，PowerShell 7.6.5，Node.js 24.16.0 / npm 11.13.0。系统 PATH 上 Python 3.10.11，使用已存在的 Codex Python 3.12.14 建立项目 `.venv`。
- 项目安装锁见 `services/api/requirements.lock` 和 `apps/web/package-lock.json`。FFmpeg 由 `imageio-ffmpeg` wheel 提供，PySceneDetect 与 OpenCV 执行切镜头，未依赖系统 ffprobe。
- Edge 与 Chrome 均已安装。本机浏览器验收使用隔离 Playwright 上下文，避免读取用户浏览器档案。
- SQLite 为默认服务，Docker Desktop 可选且启动流程不需要。PostgreSQL 驱动已安装，数据库切换通过 `DATABASE_URL`。
- 默认端口 Web 3000，API 8000。PowerShell 探测空闲端口并只绑定回环。沙箱限制本地代理与 Windows 回环套接字，依赖安装、实际服务与 TestClient 测试使用已授权的网络执行环境。
