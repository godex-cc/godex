# Godex 桌面端使用指南

二次开发的独立桌面客户端,与官方 Codex/ChatGPT 应用**数据与登录完全隔离**。

## 快速开始

```
1. 双击「启动 Godex.cmd」……之前, 请先完成一次登录引导(见下)
```

### 首次登录(必做一次)

> ⚠️ 重要:应用的"未登录引导页"需要直连 chatgpt.com 的特性服务,
> 该域名在本机网络下不可达会导致窗口长时间空白。
> 因此**先登录、后启动**:

```bash
cd D:\Odyssey\GodexDesktop
python godex-byok.py
```

选 **5(OpenAI 订阅 OAuth 登录)** → 浏览器打开授权页 → 确认 → 完成。
Free / Plus / Pro 均可,登录后即可使用会员对应的全部模型。

### BYOK:自带 API Key 用任意厂商模型(自由输入模式)

同一工具内,模型服务是**你可以随时增删改切的持久化配置**(借鉴 MSZB 自定义供应商
设计),预设只是可选的填空模板:

| 命令 | 说明 |
|---|---|
| `python godex-byok.py` | 交互菜单 |
| `… add` | **自由添加**:名称 / Base URL / 密钥 / 模型逐项输入,任意 OpenAI 兼容端点 |
| `… list` | 列出全部已配置服务与当前选择 |
| `… use [序号或id]` | 一键切换当前服务(自动恢复上次模型) |
| `… edit [序号或id]` | 改地址 / 改名 / 换密钥 |
| `… del [序号或id]` | 删除(若删的是当前服务,指针自动回落) |
| `… key <ENV名>` | 单独更换某把密钥,不动服务配置 |
| `… status` | 隔离与登录状态 |

可以同时配置任意多家服务互相切换;每家的模型选择会被记住,切回去时自动恢复。

实现要点(借鉴 MSZB 项目 provider-api-key 设计并经其实跑验证):

- **密钥不落 config**:config.toml 只写 `env_key` 引用,明文仅存
  `data\godex-keys.env`,由启动器注入进程环境——避免引擎重写配置时带走密钥;
- **URL 拼接头防御**:引擎请求 URL = `base_url` + 固定后缀。若用户把
  `/chat/completions` 等尾巴写进了 base_url(双重拼接会产生 404),写入前自动剥离;
- **托管区块写入**:服务记录用 `# >>> godex-managed` 标记对累积存放,幂等重写、
  多家并存,引擎自写的 `[desktop]`/`[windows]` 等节永远不会被动到;
- **写后即校验**:每次写入后严格 TOML 解析,坏文件当场暴露;当前指针悬空自动回落;
- **切换不丢模型**:每个服务上次的模型存于 `data\byok-state.json`,切换时恢复,
  绝不把 `model` 写成空串。
- **模型选择器目录**:应用内选择器的列表来自引擎 `model/list`。每次写配置时
  自动生成 `data\godex-model-catalog.json`(只含各服务配置的模型,不出现任何
  未配置的内置模型),并在 config.toml 托管头部写入 `model_catalog_json`
  指向它;两个写入方(应用内设置 UI 与 `godex-byok.py`)行为一致。
- **目录键自愈**:引擎在运行中重写 config.toml(保存 `[desktop]`/`[projects]`
  等节)时会丢掉 `model_catalog_json` 键。应用主进程常驻监视该文件,发现键被
  引擎删掉立即补回,重启后选择器不会回落到内置目录。
- **供应商启用/禁用**:所有配置好的服务默认启用(设置页绿灯常亮);只有用户
  在设置页点「禁用」才变灰,状态存于 `byok-state.json` 的 `enabled` 表。
  禁用服务的模型即时从目录文件中剔除,最后一个已启用的服务不允许禁用;
  禁用当前服务时自动回落到剩余的启用服务。
  CLI 对应命令:`python godex-byok.py enable|disable [id]`。
- **左下角只留用户头像**:侧边栏底部的个人资料按钮只显示一个人形头像占位
  图标,不再出现服务名(如 DeepSeek)或任何文字;点击弹出的菜单头部也显示
  「用户」。实现为渲染端补丁:注入 CSS 在每次 React 渲染时隐藏按钮内的
  label 与原齿轮图标,`fixFooter` 清空文本节点,`fixMenuHeader` 改写弹层
  头部,MutationObserver 在重渲染后自动重放;头像 svg(`data-ody-user-icon`)
  与旁边的齿轮设置按钮(`data-ody-byok-gear`)不受影响。
- **选模型自动跟供应商**:在输入框模型选择器里选中另一家的模型时,引擎只会
  改写 `model`,不会改 `model_provider`(会出现"模型归 A 家、请求发到 B 家"
  的错配)。主进程的配置监视器会按 slug→供应商映射(来自 `models_meta`/
  `providers.models`/`last_model`)自动改写 `model_provider` 并记住该模型。
- **目录/列表刷新时机**:引擎只在启动时读取 `model_catalog_json`,因此
  启用/禁用后模型选择器的列表要**重启应用**才会刷新;设置页的灯与按钮
  则是即时生效、重启后保持。
- **改代码必须打回 app.asar**:应用运行时加载的是 `app\resources\app.asar`
  (旁路 loose 目录 `app\resources\app` 不生效)。补丁流程:改 loose 主包/
  渲染包 → 跑 `work\patch_asar_enabled.py` 生成新 asar(保留原 header 结构、
  重算 offset/size、自带自检)→ 关闭应用后替换。
- **品牌图标统一(终端小脸)**:启动/加载 splash、窗口/任务栏/托盘图标、
  exe 内嵌图标、桌面与开始菜单快捷方式全部换成本项目自绘的终端小脸
  (`assets\godex_terminal_face.svg`)。要点:
  - splash 两处来源:渲染端 React 组件(qF,JSX)与原始 SVG 字符串(O3i)
    均改为该 SVG(`work\patch_usersvg.py`,墨色 `#000000`→`currentColor`
    保持主题跟随);
  - `app\resources\*.ico`(godex-app/tray/icon-*)与 `default_app\icon.png`
    均为按该 SVG 生成的多尺寸 ico;
  - exe 图标除了 rcedit 新增图标组,还必须用 `UpdateResourceW` 重写
    IDR_MAINFRAME 等 5 个命名图标组(shell 只认命名组);
  - **任务栏图标与名称来自开始菜单快捷方式**:应用 AUMID 固定为
    `com.openai.codex`,任务栏按钮显示的是携带该 AUMID 的快捷方式的
    名称与图标。`开始菜单\Programs\Odyssey.lnk` 已重定向到
    「启动 Godex.cmd」+ exe 图标并改名 `Godex.lnk`(AUMID 属性保留);
  - 注意:任务栏上还有一个花朵图标的「Codex 已固定」,那是微软商店版
    官方 OpenAI Codex 应用的固定项(签名 MSIX,图标在包资源里),
    与本项目无关、也未改动。

- **全平台打包 kit(packaging/)**:版本 0.0.1 起以 `packaging/VERSION` 为单一
  版本来源。Windows 便携 zip(`packaging\win\build-win.cmd` 一键:图标 →
  暂存(排除开发备份/多余 asar 副本)→ zip + sha256 manifest + 关键载荷校验)
  已实跑产出;NSIS 安装器脚本、mac/linux"官方发行版宿主 + 补丁叠加"脚本与
  GitHub Actions 骨架就绪。注意:运行时是 owl-Electron(Chromium 自研运行
  时),mac/linux 无法在本机凭空重建,必须用官方 Codex 对应平台发行包作宿主
  替换 asar/图标/版本元数据,引擎等平台原生件保留宿主的;`app\resources`
  里的 `Godex.exe`(=引擎 godex.exe)、`godex`、`godex-code-mode-host.exe`、
  `godex-command-runner.exe`、`rg.exe` 都是必需载荷,缺一不可。详见
  `packaging/README.md`。

## 数据隔离架构

| 数据 | 位置 | 官方应用的位置 |
|---|---|---|
| 引擎凭据(auth.json) | `GodexDesktop\data\godex-home` | `%USERPROFILE%\.codex` |
| 会话/记忆/sqlite | `GodexDesktop\data\godex-home` | 同上 |
| WebView 配置档案 | `%APPDATA%\Codex\web\Godex` | `%APPDATA%\Codex`(同构,目录名不同) |
| BYOK 密钥 | `GodexDesktop\data\godex-keys.env` | — |

两个应用可以同时安装、各自登录不同的 OpenAI 账号,互不干扰。

## 常用命令

```bash
python godex-byok.py          # 交互式设置(OAuth / API Key / BYOK)
python godex-byok.py status   # 查看隔离与登录状态
启动 Godex.cmd                 # 启动桌面端
```

## 当前已知限制

- 应用内"未登录引导页"在本机网络下会空白(见上,先 CLI 登录规避);
  这是后续二开要自研替换的第一个页面(替换为自有登录/BYOK 选择页)。
- 界面左上角与全站文案已是 "Godex" 字样(webview React 文案已深替换)。
- 窗口标题与进程名均已为 Godex(主程序 Godex.exe,引擎 godex.exe)。
