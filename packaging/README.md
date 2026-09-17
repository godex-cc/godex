# Godex 打包(全平台)kit

版本号统一取自 [`VERSION`](VERSION)(当前 `0.0.1`),所有产物名都带版本号。

## 产物矩阵

| 平台 | 产物 | 构建机器 | 状态 |
|---|---|---|---|
| Windows x64 | `dist/Godex-0.0.1-win32-x64.zip`(便携版) | Windows 本机 | ✅ 已实跑校验 |
| Windows x64 | `dist/Godex-0.0.1-win32-x64-setup.exe`(NSIS 安装器) | Windows 本机 | ✅ 已实跑校验(静默装/静默卸自测通过,见下) |
| macOS arm64/x64 | `dist/Godex-0.0.1-macos.dmg` | macOS | 叠加脚本就绪(需官方 Codex.app 作宿主) |
| Linux x64 | `dist/Godex-0.0.1-linux-x64.tar.gz`(+`.deb`) | Linux | 叠加脚本就绪(需官方 Codex linux 发行包作宿主) |

## 为什么 mac/linux 用"官方发行版宿主 + 补丁叠加"

Godex 的运行时是 OpenAI 的 owl-Electron(Chromium 152 自研运行时,见
`app/owl-shell-runtime.json` 的 `runtimeName: "owl"`)。本仓库只有 win32-x64
一份运行时,**没有** mac/linux 的 owl 运行时与其平台原生模块,无法凭空重建。
因此 mac/linux 的打包方式是:以官方 Codex 对应平台发行包为宿主,替换

- `app.asar` → 我们打过补丁的 asar(JS 平台无关;`app.asar.unpacked` 的平台
  原生模块和引擎**保留宿主自己的**,不复制 Windows 的),
- 图标/身份元数据(Info.plist / .desktop)→ Godex + 0.0.1,
- 版本戳(owl-app.ini 等)。

宿主布局探测都写进了脚本,不匹配会直接报错退出。

## 目录

```
packaging/
  VERSION                 版本号(单一来源)
  common/make-icons.py    品牌图标 → win ico / mac icns / linux png 组(纯 Pillow)
  common/make-zip.py      Windows 便携 zip:排除开发备份/多余 asar,硬链接暂存,
                          校验关键载荷(app/Godex.exe、chrome.dll、app.asar、
                          引擎 godex[.exe]、code-mode-host、command-runner、
                          rg.exe、native 模块),testzip 完整性 + sha256 manifest
  win/启动 Godex.cmd      便携版启动器(相对路径,data\ 就地隔离)
  win/README.txt          随包首跑说明(先 OAuth 登录再启动)
  win/godex.nsi           NSIS 安装器(快捷方式/卸载/版本元数据)
  win/build-win.cmd       Windows 一键构建入口
  macos/build-macos.sh    macOS 叠加打包(宿主 Codex.app → Godex.app + dmg)
  linux/build-linux.sh    Linux 叠加打包(tar.gz + 可选 deb 重打)
  ci/release.yml          GitHub Actions(win 全自动;mac/linux 需手动提供宿主包)
  icons/                  生成产物(勿手改)
  dist/                   构建产物 + *.manifest.json(sha256)
  stage/                  暂存目录(构建中间产物,可随时删)
```

## Windows 本机出包

```
packaging\win\build-win.cmd
```
或分步:`python packaging\common\make-icons.py` → `python packaging\common\make-zip.py`。

**NSIS 安装器**(本机已装 NSIS 3.12 via winget):

```
python packaging\common\make-zip.py                  # 先出 stage
python -c "..."                                      # 硬链接 stage → D:\gs(短根,绕 MAX_PATH)
"C:\Program Files (x86)\NSIS\makensis.exe" /DSTAGE='D:\gs' packaging\win\godex.nsi
```

编译要点(踩过的坑):脚本必须 UTF-8 BOM;`File /r` 扫描受 MAX_PATH~260 限制,
stage 根要短(本仓库最深文件 252 字符,`packaging\stage` 根太长,需硬链接到
`D:\gs` 这类短根,`/DSTAGE='D:\gs'` 单引号防 bash 吃反斜杠);2.2GB 载荷
**必须非 solid 压缩**(`SetCompressor lzma`,solid 会触发 makensis
"Internal compiler error #12345" 的 2GB 块上限);`/D=安装目录` 必须是最后一个
参数且目录需当前用户可写。

安装器行为:默认装到 `%LOCALAPPDATA%\Godex`(无需管理员),`RequestExecutionLevel
user`;建桌面 + 开始菜单快捷方式(指向 `启动 Godex.cmd`,图标取
`app\Godex.exe`);写 HKCU 卸载项(控制面板可见);已通过静默安装
(`/S /D=<用户可写目录>`)与静默卸载(`/S`)自测,14,534 个文件、
深路径与大文件哈希逐一比对一致,卸载后目录/注册表/开始菜单全清。

**asar 补丁集合**(经 `work\patch_asar_enabled.py` 重打,所有平台产物共享):
BYOK RPC/catalog、品牌 SVG 双位替换、0.0.1 版本戳、**版本日落开关关闭**
——渲染层根组件的 Statsig 开关 `2929582856`(appSunset 屏)按上报 appVersion
判定"低于最低支持版本即整页替换为要求更新",0.0.1 必命中;补丁把
`vx(\`2929582856\`)` 判定改为 `!1`(备份后缀 `.pre-sunsetfix`)。换官方发行包
作宿主时,叠加我们的 asar 会自动带上此关闭逻辑。

**引擎说明**:`app\resources\Godex.exe`(297MB,应用按 `godex.exe` 名字拉起的
引擎)、`godex`(262MB)、`godex-code-mode-host.exe`、`godex-command-runner.exe`
都是必需载荷,zip 校验会强制检查它们存在;缺任何一个说明 app\ 目录不完整。

## 版本号升级流程

1. 改 `packaging/VERSION`;
2. `app\resources\app\package.json` 的 `version` 字段(loose + 重打 asar,
   `work\patch_asar_enabled.py` 已内置版本戳步骤);
3. `app\resources\owl-app.ini` 的 `AppVersion=`;
4. exe 版本资源:`work\rcedit-tool\node_modules\rcedit\bin\rcedit-x64.exe
   app\Godex.exe --set-version-string FileVersion <v> --set-version-string
   ProductVersion <v>`(需先关应用);
5. 重打 asar → 关应用换入 → 重启验证;
6. 跑 `packaging\win\build-win.cmd`。
