# Windows 桌面版

采用 Electron 独立窗口，复用本项目 Web/API 与 SQLite。启动加载页 → 检查本项目健康状态 → 必要时隐藏启动本地服务 → 进入工作台。单实例、独立持久登录目录、系统标题栏、品牌图标与缩放菜单。关闭窗口保留分析服务，后台停止仍通过 scripts/stop.ps1。

桌面入口由 scripts/install-desktop.ps1 创建。运行包在 data/desktop/CreatorOS-0.1.1，源码在 apps/desktop。打包脚本遵循 Electron 官方的预构建二进制分发结构，并重设 exe 图标。桌面和开始菜单中的名称均为 CreatorOS 爆款实验室。

本版用于当前电脑的现有项目环境，运行时需要项目目录、Node.js、Python 虚拟环境与已安装依赖。移动项目后重新执行安装入口脚本。跨电脑全量安装包和代码签名尚未配置。

首轮下载遇到本机系统代理未被 Node 下载器读取的问题。安装脚本使用 Windows 下载工具，通过已配置的代理取得官方发布包，并核对官方 npm 包提供的 SHA256。缓存位于 data/desktop，可离线重新打包。

实现依据 [Electron 打包文档](https://www.electronjs.org/docs/latest/tutorial/application-distribution) 与 [安全指南](https://www.electronjs.org/docs/latest/tutorial/security)。

开发与验证顺序为核心启动规则测试、依赖安装、生成 ICO、打包、创建快捷方式、桌面实际打开验收。服务地址从 data/processes.json 动态读取，窗口只允许本机 HTTP 应用地址，不向网页开放 Node 或 Electron API。

## 实测结果

- 两项 Node 核心规则测试通过。
- 实际桌面运行包验收通过，测试进程退出码 0。验证自动启动本地服务、进入登录页、重复启动仍为单窗口、renderer 的 require 不可用、sandbox 和 contextIsolation 开启。
- 已通过真实桌面快捷方式打开应用，原生窗口标题为 CreatorOS · 爆款实验室，菜单包含工作台、人工审批、缩放与帮助。
- 截图见 screenshots/desktop-login.png，仅使用隔离测试目录。正常桌面登录与测试登录目录分离，当前用户窗口保留。
- 冷启动发现现有 Next.js 依赖不完整，按原锁文件恢复 424 个依赖后通过验收。
- 下载使用镜像分段续传提速，完整运行时已匹配官方 SHA256，保留完整性检查。

一次“关闭所有桌面进程再重建”的自动审核被拒绝。最终使用版本目录保留正在运行的窗口，通过隔离测试目录验收新版。已运行的旧窗口可正常继续使用，下次关闭再打开图标时进入新版。
