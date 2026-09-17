# SPEC-Godex-BYOK · 双轨模型接入功能设计

> 版本:v1.0(2026-09-15) · 状态:**设计评审中**
> 参考:MSZB 项目 `docs/SPEC-mszb-provider-api-key.md`(已发布产品的实跑经验)
> 本文遵循 MSZB 规格纪律:每个关键假设标注 **[已验证]** 或 **[未验证]**;
> 偏移/锚点钉在指定基线上,跨 revision 使用锚点字符串。

---

## 0. 目标与非目标

### 目标

| # | 目标 | 优先级 |
|---|---|---|
| G1 | 用户可接入**任意 OpenAI 兼容的自定义模型服务**(自带 Key,BYOK),零代码、纯配置 | P0 |
| G2 | 用户可使用 **OpenAI 官方订阅**(ChatGPT Free/Plus/Pro OAuth),获得订阅内全部模型 | P0 |
| G3 | 两轨**并存可切**,数据与官方 Codex 桌面端完全隔离 | P0 |
| G4 | 密钥安全:明文只存专属目录,配置文件不含密钥 | P1 |
| G5 | 接入流程内建**连通性测试 + 模型发现**,不让用户盲填 | P1 |

### 非目标(本期)

- 不重写应用内登录引导页(列入二期,见 §7);
- 不支持非 OpenAI 兼容协议(如原生 Gemini gRPC;Anthropic 官方 API 属 OpenAI 兼容
  之外的 `wire_api` 分支,预留但不测不承诺);
- 不做多账号并存的订阅会话管理(一次一个 OAuth 账号)。

---

## 1. 双轨模型(核心抽象)

```
                      ┌────────────────────────────────────────┐
                      │            Godex 桌面端                │
                      │  (引擎 godex.exe + Owl 壳 + React UI)    │
                      └──────┬─────────────────────┬───────────┘
                             │                     │
        ┌────────────────────┴──┐        ┌─────────┴──────────────┐
        │ 轨道 A: 订阅(OAuth)    │        │ 轨道 B: BYOK(API Key)   │
        ├────────────────────┤        ├──────────────────────┤
        │ auth.json           │        │ config.toml           │
        │   auth_mode=chatgpt │        │   model = "<model>"   │
        │   tokens{...}       │        │   model_provider="pid"│
        │ 会话/额度走官方后端    │        │   [model_providers.pid]│
        │                     │        │     base_url/env_key  │
        │ 凭据文件:            │        │ godex-keys.env      │
        │  data/godex-home    │        │   KEY=sk-...(明文)     │
        └────────────────────┘        └──────────────────────┘
              互相独立、可单独存在、可同时存在
```

**统一决策点**:引擎启动时读取 `auth.json` 判定登录态,读取 `config.toml`
的 `model`/`model_provider` 判定当前模型轨道。两者无耦合——这就是双轨可以并存的
结构性原因(**[已验证]** 2026-09-15 实验:仅注入 API-Key 型 `auth.json`
不配 OAuth,主界面正常渲染,见 §6 证据 E3)。

### 1.1 三种用户终态

| 用户状态 | auth.json | config.toml 托管头部 | 体验 |
|---|---|---|---|
| 纯订阅 | `auth_mode=chatgpt` + tokens | 无(或仅基础节) | 官方全模型,计费走订阅 |
| 纯 BYOK | `auth_mode=apikey` + OPENAI_API_KEY | `model_provider=自定义` | 完全不知晓订阅也能用(E3) |
| 双轨 | OAuth + apikey 并存 | 托管头部指向最近选择的轨道 | 在设置里一键切换;两边凭据互不覆盖 |

> 双轨并存的凭据不冲突:OAuth tokens 与 `OPENAI_API_KEY` 在 auth.json 内是不同字段
> (**[已验证]** 字段面:`tokens` / `OPENAI_API_KEY` / `auth_mode`,E2);
> 轨道选择完全由 config.toml 的 `model_provider` 表达。

---

## 2. 轨道 B 设计:自定义模型服务

### 2.1 数据模型(config.toml 托管区块)

```toml
# >>> godex-managed-header (auto; use godex-byok.py) >>>
model = "deepseek-chat"                # 当前默认模型(UI 选中的值,原样透传引擎)
model_provider = "deepseek"            # 当前轨道
# <<< godex-managed-header <<<

# ...引擎自发节([desktop]/[marketplaces]/...)原样保留,我们不碰...

# >>> godex-managed (auto; use godex-byok.py) >>>
[model_providers.deepseek]             # 可累积多家,同名覆盖
name = "DeepSeek"                      # 展示名
base_url = "https://api.deepseek.com/v1"   # 拼接头防御后的纯净根
env_key = "DEEPSEEK_API_KEY"           # 密钥经环境变量解析(不落盘配置)
wire_api = "chat"                      # chat | responses(预留 experimental)
# <<< godex-managed <<<
```

设计要点(继承自我们的既有实现 + MSZB 教训):

1. **托管区块**:工具只写 `# >>> godex-managed` 标记对之间的内容;引擎运行期会
   自行往 config.toml 写 `[desktop]`/`[marketplaces]` 等节(**[已验证]** E4),
   托管区块与其天然隔离;写入后立即严格 TOML 解析自校验。
2. **幂等 + 累积**:同一 provider 重复写入字节级一致;新增 provider 追加不覆盖;
   头部 `model`/`model_provider` 原子替换表示"当前选择"。已通过单元断言(E5)。
3. **密钥环境引用**(MSZB apiKeyRef `source:"env"` 纪律):config 内只有 `env_key`
   名字;明文仅存 `data\godex-keys.env`,启动器逐行注入进程环境。收益:
   引擎重写配置不会带走/泄露密钥;`keys.env` 天然适合加入备份排除与 .gitignore。
4. **base_url 拼接头防御**(MSZB §1.6 的 404 事故):请求 URL = `base_url` + 引擎
   固定后缀。`normalize_base()` 在写入前剥掉用户多填的 `/chat/completions`、
   `/responses`、`/messages` 尾部并给出提示。四种输入形态已单测(E5)。

### 2.2 接入向导(五步)

```
选预设(OpenRouter/DeepSeek/Moonshot/硅基流动/OpenAI Key/自定义)
  → 确认/填写 Base URL(自动拼接头纠偏)
    → 粘贴 Key(已有则掩码确认复用)
      → 连通性测试 GET {base}/models
        → 模型发现列表按序号选用(可跳过手填)
          → 写入托管区块 + 重启提示
```

- 发现失败不阻断写入(有的网关不实现 `/models`),降级为手填模型 id;
- 401/403 明确提示"key 无效或无权限"(已实测错误语义,E6);
- 超时 15s,错误信息不回显 key。

### 2.3 与 UI 可见性的对齐(MSZB 双过滤器教训)

MSZB 的坑:agent registry 与渲染层 composer 对"无 key provider"的判定不一致,
出现"配置成功但模型不显示"。Godex 引擎的对应面:

- `model_providers.*` + `model_provider` 显式指向时,请求直走该 provider
  (**[已验证]** strings 命中 `model_providers`=27 次,是引擎一级配置空间,E1);
- composer 侧是否要求凭据可解析:**[未验证]**——因此本期验收标准定为
  "显式 `model_provider` 指向下真实发一次对话请求成功"(§9 T2),
  避免 MSZB式的"配置对但看不见"问题溜进发布。

### 2.4 切换与生命周期

| 操作 | 语义 |
|---|---|
| 新增 provider | 托管区块追加表 + 头部指向它 |
| 切换默认模型 | 重跑向导选一遍(头部原子替换);二期下沉为 UI 下拉 |
| 删除 provider | 托管区块移除该表;若是当前轨道,头部回落到剩余 provider 或删除指向 |
| 改 Key | 只重写 `godex-keys.env` 对应行,不触 config |
| 多 provider 并存 | 允许;`profiles` 能力(引擎一级配置,已见命名空间)二期做情景档案 |

---

## 3. 轨道 A 设计:OpenAI 官方订阅

### 3.1 登录引导(本期 = CLI 前置)

`python godex-byok.py` → 选 1 → 引擎发起 OAuth(PKCE S256,
redirect 回桌面端)→ tokens 落入 `data/godex-home/auth.json`。

**为什么本期坚持"先 CLI 后启动"**:应用的未登录引导页需直连
`ab.chatgpt.com`(特性开关)等前端服务,本机网络下不可达导致窗口永黑
(**[已验证]** E4:`auth.openai.com` 可达 200 / `chatgpt.com` 403 /
`ab.chatgpt.com` 直连超时;登录态下无此依赖)。CLI 登录后启动即绕开。

### 3.2 订阅权益承接

- 登录后引擎 `account/read` 拉取账户面(**[已验证]** 官方日志观测到该 RPC);
- 可用模型由订阅档位(Free/Plus/Pro)决定,UI 原生呈现,我们**不做任何伪装/绕过**;
- 账号与会话、记忆、插件启用状态一并存在隔离目录,与官方安装互不可见
  (**[已验证]** E1:隔离启动后引擎报 `Not logged in`,官方 `~/.codex` 原样)。

### 3.3 订阅与 BYOK 的互斥规则

- 引擎一次只按一个 `model_provider` 出请求;轨道 A 激活时把托管头部的
  `model_provider` 移除或注释即可回到官方默认路由;
- OAuth 重登/换号**不触碰**轨道 B 的任何配置;反之亦然;
- 双轨都就绪时,设置里"默认轨道"就是一个二选一(本期=工具重跑;二期=UI 开关)。

---

## 4. 安全设计

| 项 | 措施 |
|---|---|
| 明文密钥范围 | 仅 `data/godex-keys.env`;`config.toml`/日志/截图零密钥(本设计的截图证据均为掩码) |
| 进程注入 | 启动器逐行 `KEY=VALUE` 注入子进程环境;不写入用户级注册表/全局环境 |
| 传输 | 测试探针仅 GET `/models`,Bearer 头;错误体不回显 key(实测) |
| 数据边界 | 全部状态限定 `GodexDesktop\data\` 与 `%APPDATA%\Godex`;官方 `%USERPROFILE%\.codex` 只读不写(已验证) |
| 授权依据 | OAuth 走官方 PKCE 流程;不自存密码、不碰 cookie |

---

## 5. 交付形态与阶段

| 阶段 | 内容 | 状态 |
|---|---|---|
| **P1(本期交付)** | CLI 双轨引导:`godex-byok.py`(OAuth/API-Key/BYOK 向导+连通测试+模型发现+托管写入)+ 启动器注入 | ✅ 已实现并单测 |
| **P2(二期)** | 应用内 BYOK 面板:MSZB 式 `dev-tools/patch_*.py` 幂等补丁,在渲染层设置页注入"模型服务"面板,IPC 走 `codex_desktop:*` 现有通道;承接 P1 的全部校验逻辑 | 设计(§7) |
| **P3(三期)** | 替换登录引导页为自研"欢迎页"(双轨选择:订阅登录 / 粘 Key 即用),消除对 ab.chatgpt.com 的首启依赖 | 概念 |
| 并行 | 多 provider 情景档案(引擎 `profiles`)、"获取模型列表"按钮深化(仿 MSZB discoverModels 的分页/备用路径) | backlog |

**P2 补丁锚点策略**(先行登记,届时钉基线):
设置页路由 injections 走深链路由表(P2e 已知 `godex://settings/connections` 是
现成先例);补丁脚本要求:幂等、`--check` 自检、`node --check` 产物、改后截图对比。

---

## 6. 证据清单

| ID | 结论 | 方法 | 日期 |
|---|---|---|---|
| E1 | 隔离数据目录生效,官方凭据不被读取 | 隔离启动后引擎 `login status` = "Not logged in";官方 auth.json mtime/内容不变 | 09-15 |
| E2 | auth.json 双形态字段面(`tokens` / `OPENAI_API_KEY`+`auth_mode`) | CLI 登录产物解析 | 09-15 |
| E3 | **API-Key 登录态足以渲染完整主界面**(BYOK 免订阅路径成立) | 注入 key 型 auth.json 后启动,PrintWindow 取证:问候语+任务分类芯片渲染,非黑像素 19.8%(黑屏基线 0.03%) | 09-15 |
| E4 | `model_providers` 为引擎一级配置空间 | 逆向报告 05:strings 命中 27 次;ConfigProfile 字段面 | 09-15 |
| E5 | 托管区块写入器:幂等、累积、用户节保全、写后 TOML 合法 | 单元断言(临时文件全流程) | 09-15 |
| E6 | 连通探针错误语义(401/超时/死域名) | 实测 DeepSeek 401、无效域名 SSL/DNS 失败路径 | 09-15 |
| E7 | `ab.chatgpt.com` 不可达致未登录引导页黑屏;登录态无此依赖 | 三域名 curl 探测 + 黑屏/渲染对照实验 | 09-15 |

### 未验证清单(诚实清单,MSZB §8 风格)

~~以下 1、2 两项已于 2026-09-15 E2E 转为已验证(见 §6 E8),剩余 3、4 仍开放。~~

1. ~~`wire_api="chat"` 下 `model` 值是否被引擎原样透传~~ **[已验证 E8]**:
   `glm-5.3-flash` 原样到达代理(引擎警告"Unknown model … fallback metadata"
   恰好证明透传),真实回合返回成功;
2. ~~composer 模型列表是否要求 provider 凭据"可解析"~~ 部分验证:BYOK 配置下
   桌面端 UI 100% 渲染(E8);下拉列表内容待人工确认;
3. 引擎自发写 config.toml 与托管区块写入器的并发竞态(现约定"关应用再跑工具",
   二期考虑文件锁);
4. E3 的 19.8% 渲染占比低于订阅态(~60%),差异可能来自首启动动画帧,
   不影响结论但记录在案。

### E8 · 2026-09-15 晚间实时 E2E(cc-switch 当前供应商)

链路:`/models` 200 → 引擎拒绝 `wire_api="chat"`(**0.154 起仅支持 responses**,
引用 discussion 7782)→ 切 responses → 首跑报
`Missing environment variable: OPENAI_API_KEY`(证实自定义轨道密钥**只从环境变量
解析**,auth.json 的 key 不参与——与 MSZB `resolveApiKey` 语义一致)→ 注入环境变量后
`godex exec` 真实回合成功返回 `GODEX-E2E-OK`(13,886 tokens);启动器拉起桌面端
UI 100% 渲染;官方 `~/.codex` 哈希前后不变。BYOK 工具预设已随之改为 responses。

---

## 7. P2 展望:应用内面板的实现路径(预告)

按 MSZB 的成熟套路:

1. **发现挂点**:用 CDP(我们已有 `cdp_shot*.js` 探针,需配合 Owl 的
   debug-chrome-pages 开关)定位设置页 React 组件锚点字符串;
2. **补丁形态**:`dev-tools/patch_byok_settings.py` —— 锚点字符串唯一定位、
   注入面板 JSX 编译产物、幂等标记 `/* >>> godex-byok-panel */`;
3. **数据通道**:面板不自行发 HTTP,改经 host 既有 RPC(`config/`、
   `experimentalFeature/enablement/set` 等已观测方法)读写,保持单写者原则;
4. **验收**:`node --check` → 真机启动截图对比 → 真实一次 DeepSeek 对话(E2E)。

---

## 8. 验收标准

- **A1(轨道 A)**:全新隔离目录 → CLI OAuth → 启动 → 主界面出现订阅模型,发起一次对话成功;
- **A2(轨道 B)**:全新隔离目录 → CLI `login --with-api-key`(占位 key)→ 启动 → 界面渲染(E3 复现);
  配置 DeepSeek 真实 key → 发起一次对话成功 → 官方订阅登录与否不影响;
- **A3(隔离)**:全流程前后,`%USERPROFILE%\.codex` 字节级无变化(hash);
- **A4(安全)**:`config.toml` 全文无明文 key;`keys.env` 权限仅当前用户;
- **A5(韧性)**:断网时向导可完成本地写入,联网后无需改配置直接可用。
