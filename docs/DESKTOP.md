# CreatorOS v1 · Windows 桌面版

Electron 桌面窗口复用本项目 Web/API 和本机数据库。流程为加载页 → 检查项目服务 → 必要时隐藏启动服务 → 进入工作台。单实例、原生窗口、品牌图标、缩放菜单与隔离渲染均已实现。

## 安装与打开

先运行 `scripts/setup.ps1` 完成基础环境，再执行：

```powershell
.\scripts\install-desktop.ps1
```

脚本安装桌面所需依赖和 Electron 运行时、生成运行包，并创建桌面与开始菜单中的“CreatorOS 爆款实验室”入口。缺少网络依赖时按安装输出检查下载源。

双击图标打开。备用入口为项目根目录 `CreatorOS.cmd`，需先生成运行包。当前运行包位于 `data/desktop/CreatorOS-0.1.1`，`data/desktop/current.json` 记录入口，均不上传到源码仓库。仅恢复已存在包的快捷方式可使用 `install-desktop.ps1 -SkipBuild`。

## 登录与关闭

默认勾选“记住登录（30天）”，正常关闭重开恢复会话。首次启用需本人登录一次；主动退出或到期后重新登录。桌面使用原有固定配置目录，登录及退出 Cookie 即时保存，并在正常退出前等待最后一次保存，程序不保存明文密码。

关闭窗口后，后台分析服务继续运行。完全停止后台请执行 `scripts/stop.ps1`；存在运行任务时应先取消或等待完成。菜单“帮助 → 重新连接本地服务”可重新连接本机项目。

## 边界

当前包复用本机工程、Node.js、Python 虚拟环境和前端依赖，不是可脱离项目目录的跨电脑安装器。移动目录后重新执行安装脚本。跨电脑安装和代码签名尚未交付。

窗口只加载项目回环地址；外部链接由系统浏览器打开。renderer 不开放 Node，启用 sandbox、contextIsolation 和 webSecurity，权限请求默认拒绝。

## 验证记录

早期隔离桌面验收覆盖自动服务连接、单实例和 renderer 隔离；本阶段增加 Cookie 保存及退出生命周期离线测试。实际记录和历史截图见 TEST_REPORT.md，不把离线模拟测试标成真实账号关闭重开验收。

参考：[Electron 分发](https://www.electronjs.org/docs/latest/tutorial/application-distribution)、[安全](https://www.electronjs.org/docs/latest/tutorial/security)、[Cookie 写盘](https://www.electronjs.org/docs/latest/api/cookies#cookiesflushstore)。
