#!/usr/bin/env python3
"""Godex BYOK 管理器 v2 (自定义供应商模式, 参考 MSZB provider 设计)

provider 是持久化记录, 用户随时增删改切, 预设只是可选的填空模板:

  config.toml 托管区块  -> 累积存放所有 [model_providers.*] 表
  data/godex-keys.env -> 密钥明文(env_key 引用, 启动器注入进程环境)
  data/byok-state.json  -> 每个 provider 上次使用的模型(切换时恢复)

命令:
  python godex-byok.py                 # 交互式菜单
  python godex-byok.py add             # 自由添加/覆盖一个模型服务
  python godex-byok.py list            # 列出全部服务与当前选择
  python godex-byok.py use [序号|id]    # 切换当前服务(可重选模型)
  python godex-byok.py edit [序号|id]   # 修改 base_url / 名称 / 密钥
  python godex-byok.py del [序号|id]    # 删除服务
  python godex-byok.py enable [序号|id]  # 启用服务(默认状态)
  python godex-byok.py disable [序号|id] # 禁用服务(绿灯变灰, 选择器隐藏其模型)
  python godex-byok.py key <ENV名>      # 单独设置某把密钥
  python godex-byok.py status          # 隔离与登录状态

引擎约束(0.154 实测): wire_api 仅支持 "responses"; 自定义 provider 的密钥
一律从环境变量(env_key)解析, auth.json 中的登录态不参与自定义轨道。
"""
import getpass
import json
import os
import re
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

ROOT = Path(r"D:\Odyssey\GodexDesktop")
HOME = ROOT / "data" / "godex-home"
KEYS_FILE = ROOT / "data" / "godex-keys.env"
STATE_FILE = ROOT / "data" / "byok-state.json"
CONFIG = HOME / "config.toml"
AUTH = HOME / "auth.json"
GODEX_EXE = ROOT / "app" / "resources" / "godex.exe"
CATALOG_FILE = ROOT / "data" / "godex-model-catalog.json"     # 生成物: model_catalog_json 指向这里

HDR_BEGIN = "# >>> godex-managed-header (auto; use godex-byok.py) >>>"
HDR_END = "# <<< godex-managed-header <<<"
BLK_BEGIN = "# >>> godex-managed (auto; use godex-byok.py) >>>"
BLK_END = "# <<< godex-managed <<<"
WIRES = "responses"  # engine 0.154: chat is rejected outright
BYOK_INSTRUCTIONS = ("You are Godex, a coding agent running on a user-provided "
                     "OpenAI-compatible model. Collaborate with the user in the "
                     "shared workspace until their goal is completely handled.")
BYOK_LEVELS = [
    ("low", "Fast responses with lighter reasoning"),
    ("medium", "Balances speed and reasoning depth for everyday tasks"),
    ("high", "Greater reasoning depth for complex problems"),
    ("xhigh", "Extra high reasoning depth for complex problems"),
    ("max", "Maximum reasoning depth for the hardest problems"),
    ("ultra", "Maximum reasoning with automatic task delegation"),
]

# 可选模板: 只是 add 时的预填值, 不构成任何限制
TEMPLATES = {
    "1": ("OpenRouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "2": ("DeepSeek", "https://api.deepseek.com/v1", "DEEPSEEK_API_KEY"),
    "3": ("Moonshot Kimi", "https://api.moonshot.cn/v1", "MOONSHOT_API_KEY"),
    "4": ("SiliconFlow", "https://api.siliconflow.cn/v1", "SILICONFLOW_API_KEY"),
    "5": ("OpenAI (API Key)", "https://api.openai.com/v1", "OPENAI_API_KEY"),
}


def mask(s: str) -> str:
    if not s:
        return "(空)"
    return f"{s[:6]}...{s[-4:]}" if len(s) > 14 else "***"


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def ask(prompt: str, default: str | None = None) -> str:
    tail = f" [{default}]" if default else ""
    v = input(f"{prompt}{tail} > ").strip()
    return v or (default or "")


# ------------------------------------------------------------------ keys env
def load_keys() -> dict:
    keys = {}
    if KEYS_FILE.exists():
        for line in KEYS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                keys[k.strip()] = v.strip()
    return keys


def save_key(key: str, value: str):
    lines = [l.rstrip("\n") for l in KEYS_FILE.read_text(encoding="utf-8").splitlines()] \
        if KEYS_FILE.exists() else []
    lines = [l for l in lines if l.strip() and not l.startswith(f"{key}=")]
    lines.append(f"{key}={value}")
    KEYS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def upsert_key_flow(env_key: str, existing: str | None) -> str | None:
    """确保 env_key 有值: 已存则问是否沿用, 否则现场录入。返回明文 key 或 None。"""
    stored = load_keys().get(env_key) or existing
    if stored:
        if input(f"已有 {env_key}={mask(stored)}, 沿用? [Y/n] > ").strip().lower() in ("", "y", "yes"):
            return stored
    v = getpass.getpass(f"粘贴 {env_key} (输入不回显) > ").strip()
    if v:
        save_key(env_key, v)
        print(f"  ✔ {env_key} -> {mask(v)} (godex-keys.env)")
        return v
    return None


# ------------------------------------------------------------------- state
def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_state(st: dict):
    STATE_FILE.write_text(json.dumps(st, indent=2, ensure_ascii=False), encoding="utf-8")


def is_enabled(st: dict, pid: str) -> bool:
    """供应商默认启用; state.enabled[pid]=False 才算禁用 (与设置 UI 一致)。"""
    en = st.get("enabled")
    return not (isinstance(en, dict) and en.get(pid) is False)


# ----------------------------------------------- config managed read/write
def read_managed() -> tuple[dict, str | None, str | None]:
    """返回 (providers{pid:{name,base_url,env_key,wire_api}}, 当前pid, 当前model)。"""
    providers, cur_pid, cur_model = {}, None, None
    if CONFIG.exists():
        text = CONFIG.read_text(encoding="utf-8")
        if BLK_BEGIN in text:
            inner = text.split(BLK_BEGIN, 1)[1].split(BLK_END, 1)[0]
            try:
                providers = tomllib.loads(inner).get("model_providers", {})
            except Exception:
                providers = {}
        if HDR_BEGIN in text:
            hdr = text.split(HDR_BEGIN, 1)[1].split(HDR_END, 1)[0]
            for line in hdr.splitlines():
                m = re.match(r'\s*model_provider\s*=\s*"([^"]+)"', line)
                if m:
                    cur_pid = m.group(1)
                m = re.match(r'\s*model\s*=\s*"([^"]+)"', line)
                if m:
                    cur_model = m.group(1)
    return providers, cur_pid, cur_model


def _toml_table(pid: str, pv: dict) -> list[str]:
    lines = [f"[model_providers.{pid}]",
             f'name = "{esc(pv["name"])}"',
             f'base_url = "{esc(pv["base_url"])}"',
             f'env_key = "{esc(pv["env_key"])}"',
             f'wire_api = "{pv["wire_api"]}"']
    if pv.get("models"):
        # 设置 UI 写入的模型列表, 重写时保留 (否则目录生成退化为 last_model)
        lines.append("models = [" + ", ".join(f'"{esc(m)}"' for m in pv["models"]) + "]")
    return lines


def _strip_managed_regions(text: str) -> str:
    """切除全部托管区域; 区域内非 model_providers 的顶层表(如引擎自写的
    [windows])原样救回, 保证引擎节永不因重写而丢失。"""
    for begin, end in ((HDR_BEGIN, HDR_END), (BLK_BEGIN, BLK_END)):
        if begin in text:
            pre, rest = text.split(begin, 1)
            inner, _, post = rest.partition(end)
            rescued, cur = [], None
            for line in inner.splitlines():
                s = line.strip()
                if s.startswith("[") and s.endswith("]"):
                    cur = s[1:-1]
                if cur and not cur.startswith("model_providers"):
                    rescued.append(line)
            text = pre + "\n".join(rescued) + post
    return text


def gen_catalog(providers: dict | None = None) -> str | None:
    """生成引擎 model_catalog_json (模型选择器的数据源)。

    只包含各 BYOK 服务配置的模型 —— 产品定位: 选择器不出现任何未配置的
    内置模型。完全失败返回 None (config 头部则不写 model_catalog_json,
    引擎回落到内置目录)。
    """
    try:
        if providers is None:
            providers, _, _ = read_managed()
        st = load_state()
        meta = st.get("models_meta", {})
        last = st.get("last_model", {})
        seen: set[str] = set()
        models = []
        for pid in sorted(providers):
            if not is_enabled(st, pid):
                continue  # 禁用的服务不进目录, 选择器不显示其模型
            pv = providers[pid]
            lst = meta.get(pid) or [{"id": m, "name": m} for m in (pv.get("models") or [])]
            if not lst and last.get(pid):
                lst = [{"id": last[pid], "name": last[pid]}]
            for m in lst:
                if not isinstance(m, dict):
                    m = {"id": str(m)}
                slug = str(m.get("id", "")).strip()
                if not slug or slug in seen:
                    continue
                seen.add(slug)
                name = str(m.get("name") or "").strip() or slug
                entry = {
                    "slug": slug,
                    "display_name": name,
                    "description": f"{name} - {pv.get('name') or pid}",
                    "default_reasoning_level": "medium",
                    "supported_reasoning_levels": [
                        {"effort": e, "description": d} for e, d in BYOK_LEVELS],
                    "input_modalities": ["text"],
                    "visibility": "list",
                    "priority": 1,
                    "shell_type": "unified_exec",
                    "supported_in_api": True,
                    "support_verbosity": False,
                    "truncation_policy": {"mode": "tokens", "limit": 10000},
                    "experimental_supported_tools": [],
                    "base_instructions": BYOK_INSTRUCTIONS,
                }
                if m.get("contextWindow", 0) > 0:
                    entry["context_window"] = m["contextWindow"]
                if m.get("maxOutputTokens", 0) > 0:
                    entry["max_output_tokens"] = m["maxOutputTokens"]
                models.append(entry)
        CATALOG_FILE.write_text(
            json.dumps({"models": models}, ensure_ascii=False), encoding="utf-8")
        return str(CATALOG_FILE)
    except Exception:
        return None


def write_config(providers: dict, cur_pid: str | None, cur_model: str | None):
    """全量重建托管头部与区块; 引擎/用户的其它节一律不碰。写后即校验。

    防御: cur_pid 不在 providers 内(已被删)时自动回落到剩余第一家,
    绝不写悬空指针 —— 引擎遇到未知 model_provider 会拒绝启动。
    """
    st = load_state()
    if cur_pid not in providers:
        cur_pid = sorted(providers)[0] if providers else None
    if cur_pid and not is_enabled(st, cur_pid):
        # 绝不把已禁用的服务写成当前指针
        cur_pid = next((p for p in sorted(providers) if is_enabled(st, p)), cur_pid)
    # 渲染端原生读取 [model_providers.*] 的 models 列表作为选择器条目
    # (customModels 通道), 把状态里的模型列表补写回 config, 双保险。
    meta = st.get("models_meta", {})
    last = st.get("last_model", {})
    for pid, pv in providers.items():
        if not pv.get("models"):
            ids = [m.get("id") for m in (meta.get(pid) or []) if m.get("id")]
            if not ids and last.get(pid):
                ids = [last[pid]]
            if ids:
                pv["models"] = ids
    text = _strip_managed_regions(
        CONFIG.read_text(encoding="utf-8") if CONFIG.exists() else "")
    kept = [l for l in text.splitlines()
            if not l.strip().startswith(("model =", "model_provider =",
                                         "model_catalog_json ="))]
    body = "\n".join(kept).strip()

    if providers and cur_pid:
        cat_path = gen_catalog(providers)
        header_lines = [HDR_BEGIN, f'model = "{esc(cur_model or "")}"',
                        f'model_provider = "{cur_pid}"']
        if cat_path:
            header_lines.append(f'model_catalog_json = "{esc(cat_path)}"')
        header_lines.append(HDR_END)
        header = "\n".join(header_lines)
        lines = [BLK_BEGIN]
        for pid in sorted(providers):
            lines.extend(_toml_table(pid, providers[pid]))
        lines.append(BLK_END)
        text = header + "\n\n" + body + "\n\n" + "\n".join(lines) + "\n"
    else:
        text = body + "\n"

    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(text, encoding="utf-8")
    tomllib.loads(CONFIG.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- HTTP probe
def fetch_models(base: str, key: str, timeout=15):
    url = base.rstrip("/") + "/models"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}",
                                               "Accept": "application/json",
                                               "User-Agent": "Godex-BYOK/2.0"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        ms = data.get("data", data if isinstance(data, list) else [])
        return True, [m.get("id") for m in ms if isinstance(m, dict) and m.get("id")], \
            f"{time.time() - t0:.1f}s"
    except urllib.error.HTTPError as e:
        return False, [], f"HTTP {e.code}" + (" (key 无效或无权限)" if e.code in (401, 403) else "")
    except Exception as e:
        return False, [], f"{type(e).__name__}: {e}"


# ------------------------------------------------------------------- flows
def slugify(name: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-zA-Z0-9_-]", "-", name.strip().lower())).strip("-") \
        or "provider"


def pid_for(name: str, providers: dict) -> str:
    pid = slugify(name)
    n = 2
    while pid in providers:
        pid = f"{slugify(name)}-{n}"
        n += 1
    return pid


def pick_model_interactive(base: str, pid: str, env_key: str = "OPENAI_API_KEY") -> str | None:
    """模型三选: 发现列表序号 / 手填 / 上次记忆。发现用的 key 按 env_key 取。"""
    st = load_state()
    remembered = st.get("last_model", {}).get(pid)
    mode = input("选择模型: [1]在线发现  [2]手填" + (f"  [3]上次({remembered})" if remembered else "") + " > ").strip()
    if mode == "1":
        k = load_keys().get(env_key) or \
            getpass.getpass(f"粘贴 {env_key} (不回显) > ").strip()
        if not k:
            return None
        save_key(env_key, k)
        ok, ids, info = fetch_models(base, k)
        if not ok:
            print(f"  ✘ 发现失败: {info}; 回退手填")
            return input("  模型 id > ").strip() or None
        print(f"  ✔ {len(ids)} 个模型 ({info}): {', '.join(ids[:12])}{' ...' if len(ids) > 12 else ''}")
        pick = input("  模型序号/完整 id > ").strip()
        if pick.isdigit() and 1 <= int(pick) <= len(ids):
            return ids[int(pick) - 1]
        return pick or None
    if mode == "3" and remembered:
        return remembered
    return input("模型 id > ").strip() or None


def flow_add():
    """自由添加/覆盖: 除引擎 wire 约束外一切字段用户说了算。"""
    print("\n[添加模型服务] — 所有字段均可自由输入, 模板只帮你预填")
    print("可选模板(回车跳过 = 纯自由输入):")
    for k, (nm, bu, _) in TEMPLATES.items():
        print(f"  {k}. {nm}  {bu}")
    tid = input("模板序号 > ").strip()
    t_nm, t_bu, t_env = TEMPLATES.get(tid, ("", "", ""))

    name = ask("显示名称", t_nm)
    if not name:
        return print("✘ 需要名称")
    base = _strip_suffix(ask("Base URL (含 /v1)", t_bu))
    if not base:
        return print("✘ 需要 Base URL")

    providers, cur_pid, cur_model = read_managed()
    pid = pid_for(name, providers)

    default_env = t_env or (pid.upper().replace("-", "_") + "_API_KEY")
    env_key = ask("密钥环境变量名", default_env)

    key = upsert_key_flow(env_key, load_keys().get(env_key))

    print(f"  wire_api = {WIRES} (引擎 0.154 仅支持 responses, 自动写入)")
    model = pick_model_interactive(base, pid, env_key) if key else None

    providers[pid] = {"name": name, "base_url": base, "env_key": env_key, "wire_api": WIRES}
    is_first = not cur_pid
    write_config(providers, cur_pid or pid, (cur_model if not is_first else model) or model)
    if model:
        st = load_state()
        st.setdefault("last_model", {})[pid] = model
        save_state(st)
    print(f"  ✔ 已保存为 [{pid}]" + (f", 当前默认模型 {model}" if model else ""))
    print("  提示: use 命令可随时切换; 重启 Godex 生效。")


def _strip_suffix(raw: str) -> str:
    base = raw.strip().rstrip("/")
    for suf in ("/chat/completions", "/responses", "/messages"):
        if base.endswith(suf):
            base = base[: -len(suf)]
            print(f"  ⚠ 已去除结尾 {suf} (引擎自动拼接, 双写会 404)")
            break
    return base


def _pick_pid(providers: dict, cur_pid: str | None, verb: str) -> str | None:
    if not providers:
        print("(没有任何已配置的服务, 先 add)")
        return None
    ids = sorted(providers)
    st = load_state()
    print(f"已配置的服务 (当前 = {cur_pid}):")
    for i, pid in enumerate(ids, 1):
        pv = providers[pid]
        k = load_keys().get(pv["env_key"])
        mark = " <== 当前" if pid == cur_pid else ""
        if not is_enabled(st, pid):
            mark += " [已禁用]"
        print(f"  {i}. {pid:16s} {pv['name']:20s} {pv['base_url']}"
              f"  key={mask(k) if k else '未配置'}{mark}")
    pick = input(f"{verb}哪个(序号) > ").strip()
    if pick.isdigit() and 1 <= int(pick) <= len(ids):
        return ids[int(pick) - 1]
    return pick if pick in providers else None


def flow_use():
    providers, cur_pid, cur_model = read_managed()
    pid = _pick_pid(providers, cur_pid, "切换")
    if not pid:
        return
    if not is_enabled(load_state(), pid):
        print("✘ 该服务已禁用, 请先 enable 或在设置页启用。")
        return
    model = pick_model_interactive(providers[pid]["base_url"], pid, providers[pid]["env_key"]) \
        if input("重选模型? [y/N] > ").strip().lower() in ("y", "yes") \
        else load_state().get("last_model", {}).get(pid)
    # 兜底: 目标服务没记住过模型时不写空串, 沿用当前头部模型
    model = model or load_state().get("last_model", {}).get(pid) or cur_model
    write_config(providers, pid, model)
    if model:
        st = load_state()
        st.setdefault("last_model", {})[pid] = model
        save_state(st)
    print(f"✔ 当前服务 -> {pid}" + (f", 模型 {model}" if model else "") + "; 重启 Godex 生效。")


def flow_edit():
    providers, cur_pid, cur_model = read_managed()
    pid = _pick_pid(providers, cur_pid, "编辑")
    if not pid:
        return
    pv = providers[pid]
    nv = ask("显示名称", pv["name"])
    bv = _strip_suffix(ask("Base URL", pv["base_url"]))
    env_key = ask("密钥环境变量名", pv["env_key"])
    kv = upsert_key_flow(env_key, load_keys().get(env_key))
    providers[pid] = {"name": nv or pv["name"], "base_url": bv or pv["base_url"],
                      "env_key": env_key, "wire_api": pv.get("wire_api", WIRES)}
    write_config(providers, cur_pid, cur_model)
    print(f"✔ [{pid}] 已更新")


def flow_del():
    providers, cur_pid, cur_model = read_managed()
    pid = _pick_pid(providers, cur_pid, "删除")
    if not pid:
        return
    if input(f"确认删除 [{pid}]? [y/N] > ").strip().lower() not in ("y", "yes"):
        return
    providers.pop(pid, None)
    if cur_pid == pid:
        cur_pid = next(iter(providers), None)
        cur_model = load_state().get("last_model", {}).get(cur_pid) if cur_pid else None
        print(f"  (当前服务已删除, 回落到 {cur_pid or '无'})")
    write_config(providers, cur_pid, cur_model)
    print("✔ 已删除")


def flow_key():
    env = input("环境变量名 (如 DEEPSEEK_API_KEY) > ").strip()
    if not env:
        return
    v = getpass.getpass(f"粘贴 {env} (不回显) > ").strip()
    if v:
        save_key(env, v)
        print(f"✔ {env} -> {mask(v)}")


def flow_toggle(pid_arg: str, enabled: bool):
    """启用/禁用服务; 禁用最后一个已启用的服务被拒绝, 禁用当前服务时回落。"""
    providers, cur_pid, cur_model = read_managed()
    pid = pid_arg if pid_arg in providers \
        else _pick_pid(providers, cur_pid, "启用" if enabled else "禁用")
    if not pid:
        return
    st = load_state()
    en = st.setdefault("enabled", {})
    if is_enabled(st, pid) == enabled:
        print(f"[{pid}] 已是{'启用' if enabled else '禁用'}状态")
        return
    if enabled:
        en.pop(pid, None)
        save_state(st)
        gen_catalog(providers)
        print(f"✔ 已启用 [{pid}]")
    else:
        others = [p for p in sorted(providers) if p != pid and is_enabled(st, p)]
        if not others:
            print("✘ 至少需要保留一个已启用的供应商。")
            return
        en[pid] = False
        save_state(st)
        if cur_pid == pid:
            new_pid = others[0]
            new_model = st.get("last_model", {}).get(new_pid) or cur_model
            write_config(providers, new_pid, new_model)
            print(f"✔ 已禁用 [{pid}], 当前服务回落到 {new_pid}")
        else:
            gen_catalog(providers)
            print(f"✔ 已禁用 [{pid}], 选择器不再显示其模型")


def do_oauth():
    print("\n[OpenAI 会员 OAuth 登录]")
    print(f"凭据只会写入: {AUTH}")
    env = {**os.environ, "CODEX_HOME": str(HOME), "GODEX_HOME": str(HOME)}
    rc = subprocess.call([str(GODEX_EXE), "login"], env=env)
    print("✔ OAuth 完成" if rc == 0 else f"✘ 退出码 {rc}")


def show_status():
    providers, cur_pid, cur_model = read_managed()
    print("=" * 56)
    print("Godex 数据隔离 + BYOK 状态")
    print("=" * 56)
    print(f"GODEX_HOME  : {HOME}  (引擎读取 CODEX_HOME)")
    if AUTH.exists():
        try:
            d = json.loads(AUTH.read_text(encoding="utf-8"))
            if d.get("tokens"):
                print(f"登录态      : OAuth (account {str(d['tokens'].get('account_id'))[:12]}...)")
            elif d.get("OPENAI_API_KEY"):
                print(f"登录态      : API Key ({mask(d['OPENAI_API_KEY'])})")
            else:
                print("登录态      : 空")
        except Exception:
            print("登录态      : auth.json 解析失败")
    else:
        print("登录态      : 未登录 (菜单 5 = OAuth 订阅登录)")
    if providers:
        print(f"模型服务    : {len(providers)} 个 (当前 = {cur_pid or '-'}, 模型 {cur_model or '-'})")
        keys = load_keys()
        st = load_state()
        for pid, pv in sorted(providers.items()):
            k = keys.get(pv["env_key"])
            state = "禁用" if not is_enabled(st, pid) else "启用"
            print(f"  [{pid}] {pv['base_url']} wire={pv['wire_api']} {state}"
                  f" key={'✔ ' + mask(k) if k else '✘ 未配置'}")
    else:
        print("模型服务    : (无, 菜单 1 添加)")
    if CATALOG_FILE.exists():
        try:
            n = len(json.loads(CATALOG_FILE.read_text(encoding="utf-8")).get("models", []))
            print(f"模型目录    : {CATALOG_FILE.name} ({n} 个模型, 选择器数据源)")
        except Exception:
            print(f"模型目录    : {CATALOG_FILE.name} (解析失败)")
    else:
        print("模型目录    : (未生成, 任一写配置操作会自动生成)")
    try:
        env = {**os.environ, "CODEX_HOME": str(HOME), "GODEX_HOME": str(HOME)}
        r = subprocess.run([str(GODEX_EXE), "login", "status"], capture_output=True,
                           text=True, env=env, timeout=30)
        print("引擎视角    :", (r.stdout or r.stderr).strip()[:100])
    except Exception:
        pass


MENU = """
====== Godex 模型服务管理 ======
 1. 添加/覆盖模型服务 (BYOK, 自由输入)
 2. 切换当前服务/模型
 3. 编辑服务
 4. 删除服务
 5. OpenAI 订阅 OAuth 登录
 6. 设置/更换某把密钥
 7. 查看状态
 0. 退出"""


def main():
    HOME.mkdir(parents=True, exist_ok=True)
    argv = sys.argv[1:]
    if argv:
        cmd = argv[0]
        if cmd == "status":
            return show_status()
        if cmd == "list":
            return show_status()
        if cmd == "add":
            return flow_add()
        if cmd == "use":
            providers, cur_pid, cur_model = read_managed()
            pid = argv[1] if len(argv) > 1 and argv[1] in providers else _pick_pid(providers, cur_pid, "切换")
            if pid:
                model = argv[2] if len(argv) > 2 else None
                model = model or load_state().get("last_model", {}).get(pid) or cur_model
                write_config(providers, pid, model)
                print(f"✔ 当前服务 -> {pid}" + (f", 模型 {model}" if model else ""))
            return
        if cmd == "del":
            providers, cur_pid, cur_model = read_managed()
            pid = argv[1] if len(argv) > 1 and argv[1] in providers else _pick_pid(providers, cur_pid, "删除")
            if pid:
                providers.pop(pid)
                if cur_pid == pid:
                    cur_pid, cur_model = next(iter(providers), None), None
                write_config(providers, cur_pid, cur_model)
                print(f"✔ 已删除 {pid}")
            return
        if cmd in ("enable", "disable"):
            return flow_toggle(argv[1] if len(argv) > 1 else "", cmd == "enable")
        if cmd == "key" and len(argv) > 1:
            v = getpass.getpass(f"粘贴 {argv[1]} (不回显) > ").strip()
            if v:
                save_key(argv[1], v)
                print(f"✔ {argv[1]} 已保存")
            return
        print(__doc__)
        return

    print("\n提示: 首次使用建议先选 5 完成 OpenAI 订阅登录, 或用 1 添加自己的模型服务。")
    while True:
        print(MENU)
        c = input("选择 > ").strip()
        {"1": flow_add, "2": flow_use, "3": flow_edit, "4": flow_del,
         "5": do_oauth, "6": flow_key, "7": show_status}.get(c, lambda: None)()
        if c == "0":
            break


if __name__ == "__main__":
    if not GODEX_EXE.exists():
        sys.exit(f"找不到 {GODEX_EXE}")
    main()
