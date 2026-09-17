# -*- coding: utf-8 -*-
"""主进程 godex-byok:rpc 黑盒回归 —— 提取 MAIN_RPC 到 Node + electron stub 跑全 CRUD"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "patch_byok_settings", r"D:\Odyssey\GodexDesktop\dev-tools\patch_byok_settings.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

tmp = Path(tempfile.mkdtemp(prefix="ody-rpc-"))
home = tmp / "home"
data = tmp / "data"
home.mkdir()
data.mkdir()

SEED = (r"D:\Odyssey\GodexDesktop\data\godex-home\config.toml")
(home / "config.toml").write_text(Path(SEED).read_text(encoding="utf-8"), encoding="utf-8")
(data / "godex-keys.env").write_text(
    "# Godex API Keys\nOPENAI_API_KEY=1234\n", encoding="utf-8")

HARNESS = r"""
const fs=require("fs"),pathMod=require("path"),osMod=require("os");
const handlers={};
const ipcMain={handle:(n,f)=>{handlers[n]=f}};
const electron={ipcMain:ipcMain};
const req=name=>{
  if(name==="electron")return electron;
  return require(name);
};
const code=fs.readFileSync(process.argv[2],"utf-8");
new Function("require","process","globalThis",code)(
  req,{env:{
    CODEX_HOME:process.env.CODEX_HOME,
    GODEX_DATA:process.env.GODEX_DATA,
  }},globalThis);
const handler=handlers["godex-byok:rpc"];
if(!handler)throw new Error("handler 未注册");
async function call(op,args){
  const r=await handler(null,{op,args});
  return r;
}
(async()=>{
  const out=[];
  // 1. list 初始
  let r=await call("list",{});
  if(!r.ok)throw new Error("list: "+r.error);
  const d0=r.data;
  out.push(["seed providers", Object.keys(d0.providers).join(",")]);
  out.push(["seed current", d0.current+"/"+d0.currentModel]);
  // 2. upsert 新服务 (含拼接头 + 引号名)
  r=await call("upsert",{name:'Test "X"',base_url:"http://1.2.3.4:9/v1/chat/completions",
    env_key:"TEST_X_KEY",key:"sk-tx-abcdef",model:"mx-1"});
  if(!r.ok)throw new Error("upsert: "+r.error);
  const newPid=r.data.pid;
  out.push(["upsert pid", newPid]);
  // 3. list 校验: 转义/剥后缀/pointer 不变
  r=await call("list",{});
  const d1=r.data;
  const np=d1.providers[newPid];
  out.push(["stripped base", np.base_url]);
  out.push(["escaped name", np.name]);
  out.push(["pointer kept", d1.current+"/"+d1.currentModel]);
  out.push(["key masked", d1.keysMasked["TEST_X_KEY"]]);
  out.push(["lastModel", d1.lastModel[r.data.pid]]);
  // 4. select 切到新服务, model 不给 -> 用记忆
  r=await call("select",{pid:newPid});
  const d2=r.data; out.push(["select model", d2.model]);
  console.log("@@SNAPSHOT@@");
  console.log(fs.readFileSync(pathMod.join(process.env.CODEX_HOME,"config.toml"),"utf-8"));
  // 5. del 新服务 -> 回落 local187
  r=await call("del",{pid:newPid});
  if(!r.ok)throw new Error("del: "+r.error);
  r=await call("list",{});
  out.push(["after del current", r.data.current+"/"+r.data.currentModel]);
  // 6. 错误路径
  r=await call("del",{pid:"nope"});
  out.push(["del unknown ok?", r.ok]);
  console.log("@@JSON@@");
  console.log(JSON.stringify(out,null,1));
  // 输出生成的 config 供外部断言
  console.log("@@CONFIG@@");
  console.log(fs.readFileSync(pathMod.join(process.env.CODEX_HOME,"config.toml"),"utf-8"));
  console.log("@@KEYS@@");
  console.log(fs.readFileSync(pathMod.join(process.env.GODEX_DATA,"godex-keys.env"),"utf-8"));
})().catch(e=>{console.error("HARNESS-FAIL",e);process.exit(1)});
"""

(h_tmp := tmp / "harness.cjs").write_text(HARNESS, encoding="utf-8")
rpc_txt = mod.MAIN_RPC
(tmp / "rpc_extract.cjs").write_text(rpc_txt, encoding="utf-8")

import os
env = dict(os.environ)
env.update({"CODEX_HOME": str(home), "GODEX_DATA": str(data)})
r = subprocess.run(["node", str(h_tmp), str(tmp / "rpc_extract.cjs")],
                   capture_output=True, text=True, env=env, timeout=60, encoding="utf-8")
print(r.stdout[-4000:])
if r.returncode != 0:
    print("STDERR:", r.stderr[-2000:])
    sys.exit(1)

snap_body = r.stdout.split("@@SNAPSHOT@@\n", 1)[1].split("@@CONFIG@@\n", 1)[0]
final_body = r.stdout.split("@@CONFIG@@\n", 1)[1].split("@@KEYS@@\n", 1)[0]
cfg_body = snap_body
keys_body = r.stdout.split("@@KEYS@@\n", 1)[1]
keys_lines = [l for l in keys_body.strip().splitlines() if "=" in l and not l.startswith("#")]
import json as _json
_jtxt = r.stdout.split("@@JSON@@\n", 1)[1].split("@@CONFIG@@\n", 1)[0].strip()
if not _jtxt.startswith("["):
    print("DIAG stdout head:", repr(r.stdout[:200]))
harness_json = _json.loads(_jtxt)
harness_map = {row[0]: row[1] for row in harness_json}

checks = [
    ("upsert 剥掉了 /chat/completions 拼接头", 'base_url = "http://1.2.3.4:9/v1"' in cfg_body),
    ("引号名正确转义 (文件字节单反斜杠)", 'name = "Test \\"X\\""' in cfg_body),
    ("往返不再叠层 (list 回读等于原始输入)", harness_map.get("escaped name") == 'Test "X"'),
    ("pointer 新增不夺位 (JSON)", harness_map.get("pointer kept") == "local187/glm-5.3-flash"),
    ("引擎节 [desktop] 保留", "followUpQueueMode = \"steer\"" in cfg_body),
    ("托管区内遗留 [windows] 被救出到区外", cfg_body.find("[windows]") < cfg_body.find("# >>> godex-managed (auto")),
    ("del 后回落 local187 且无 test-x 残留",
     'model_provider = "local187"' in final_body and "[model_providers.test-x]" not in final_body),
    ("del 回落后 model 非空串", '"model = ""' not in final_body),
    ("keys.env 覆盖更新 TEST_X_KEY", any(l.startswith("TEST_X_KEY=") and "sk-tx-abcdef" in l for l in keys_lines)),
    ("keys.env 保留 OPENAI_API_KEY", any(l.startswith("OPENAI_API_KEY=1234") for l in keys_lines)),
    ("keys.env 无重复行", sum(1 for l in keys_lines if l.startswith("TEST_X_KEY=")) == 1),
]
fails = []
for name, ok in checks:
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        fails.append(name)
print("\n===== harness 快照 (del 前, 含 test-x) =====")
print(snap_body)
if fails:
    sys.exit(1)
shutil.rmtree(tmp, ignore_errors=True)
