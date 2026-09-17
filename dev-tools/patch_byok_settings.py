#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_byok_settings.py —— 应用内「模型服务」BYOK 面板 (P2, 幂等, MSZB patch 范式)

改动面 (全部带 GODEX_BYOK_* 幂等标记):
  1. .vite/build/main-D8abTQQE.js      尾部追加 godex-byok:rpc 主进程实现
  2. .vite/build/preload.js            追加 window.godexByok 桥
  3. webview/assets/app-initial-*.js   路由 + slug + 白名单 + 标签 case + 面板组件
  4. webview/assets/use-visible-settings-sections-*.js  可见性放行 + 未登录白名单
  5. webview/assets/settings-page-*.js 侧栏 Personal 分组入口

用法:
  python patch_byok_settings.py            # 应用 (已应用则跳过)
  python patch_byok_settings.py --check    # 自检
  python patch_byok_settings.py --restore  # 从同目录 .godex-bak 还原
"""
from __future__ import annotations
import io
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

APP = Path(r"D:\Odyssey\GodexDesktop\app\resources\app")
BUILD = APP / ".vite" / "build"
ASSETS = APP / "webview" / "assets"
MAIN_F = BUILD / "main-D8abTQQE.js"
PRELOAD_F = BUILD / "preload.js"
REND_F = ASSETS / "app-initial-d9bed9d614d8.js"
SPV_F = ASSETS / "use-visible-settings-sections-9008162f86fd.js"
SPG_F = ASSETS / "settings-page-cd8e20bd79ad.js"
FILES = [MAIN_F, PRELOAD_F, REND_F, SPV_F, SPG_F]

SLUG = "godex-byok"

# ---------------------------------------------------------------------------
# 主进程 RPC 实现 (追加到 main bundle EOF)
# ---------------------------------------------------------------------------
MAIN_RPC = r'''
;/*GODEX_BYOK_RPC*/globalThis.__GODEX_BYOK_RPC__=(function(){
  const{ipcMain}=require("electron"),fs=require("fs"),pathMod=require("path"),osMod=require("os");
  const HOME=process.env.CODEX_HOME||pathMod.join(osMod.homedir(),".codex");
  const CFG=pathMod.join(HOME,"config.toml");
  const DATA=process.env.GODEX_DATA||pathMod.dirname(HOME);
  const KEYS=pathMod.join(DATA,"godex-keys.env");
  const STATE=pathMod.join(DATA,"byok-state.json");
  const HB="# >>> godex-managed-header (auto; use godex-byok.py) >>>";
  const HE="# <<< godex-managed-header <<<";
  const BB="# >>> godex-managed (auto; use godex-byok.py) >>>";
  const BE="# <<< godex-managed <<<";
  function rd(p,d){try{return fs.readFileSync(p,"utf-8")}catch(e){return d}}
  function esc(s){return String(s).replace(/\\/g,"\\\\").replace(/"/g,'\\"')}
  function tomlUnq(s){let out="",i=0;
    while(i<s.length){const c=s[i];
      if(c==="\\"&&i+1<s.length){const n=s[i+1];out+=(n==="n"?"\n":n==="t"?"\t":n);i+=2;}
      else{out+=c;i++;}
    }
    return out;
  }
  function stripRegions(t){
    for(const pair of[[HB,HE],[BB,BE]]){
      const b=pair[0],e=pair[1];
      const i=t.indexOf(b);if(i<0)continue;const j=t.indexOf(e,i);if(j<0)continue;
      const inner=t.slice(i+b.length,j),pre=t.slice(0,i),post=t.slice(j+e.length);
      let keep=[],cur=null;
      for(const line of inner.split(/\r?\n/)){
        const s=line.trim();
        if(s.startsWith("[")&&s.endsWith("]"))cur=s.slice(1,-1);
        if(cur&&!cur.startsWith("model_providers"))keep.push(line);
      }
      t=pre+keep.join("\n")+post;
    }
    return t;
  }
  function readCfg(){
    const t=rd(CFG,""),out={providers:{},current:null,currentModel:null,lastModel:{},modelsMeta:{}};
    if(!t)return out;
    const hi=t.indexOf(HB),hj=t.indexOf(HE);
    if(hi>=0&&hj>hi){
      for(const line of t.slice(hi+HB.length,hj).split(/\r?\n/)){
        let m=line.match(/^\s*model\s*=\s*"((?:[^"\\]|\\.)*)"/);if(m)out.currentModel=m[1];
        m=line.match(/^\s*model_provider\s*=\s*"((?:[^"\\]|\\.)*)"/);if(m)out.current=m[1];
      }
    }
    const bi=t.indexOf(BB),bj=t.indexOf(BE);
    if(bi>=0&&bj>bi){
      const inner=t.slice(bi+BB.length,bj);
      const segs=inner.split(/\[model_providers\.([A-Za-z0-9_-]+)\]/);
      for(let i=1;i+1<segs.length;i+=2){
        const pid=segs[i],body=segs[i+1],pv={name:"",base_url:"",env_key:"",wire_api:"responses",models:[]};
        for(const f of["name","base_url","env_key","wire_api"]){
          const m=body.match(new RegExp('\\s+'+f+'\\s*=\\s*"((?:[^"\\\\]|\\\\.)*)"'));
          if(m)pv[f]=tomlUnq(m[1]);
        }
        const mm=body.match(/^\s*models\s*=\s*\[([^\]]*)\]/m);
        if(mm)pv.models=mm[1].split(",").map(s=>s.trim().replace(/^"|"$/g,"")).filter(Boolean);
        out.providers[pid]=pv;
      }
    }
    try{const st=JSON.parse(rd(STATE,"{}"));out.lastModel=st.last_model||{};out.modelsMeta=st.models_meta||{}}catch(e){}
    return out;
  }
  function readKeys(){
    const out={};
    for(const line of rd(KEYS,"").split(/\r?\n/)){
      const s=line.trim();
      if(s&&!s.startsWith("#")){
        const i=s.indexOf("=");
        if(i>0)out[s.slice(0,i).trim()]=s.slice(i+1).trim();
      }
    }
    return out;
  }
  function writeKey(k,v){try{if(v!=null)process.env[k]=v;}catch(e){}
    const seen=[],map={};
    for(const line of rd(KEYS,"").split(/\r?\n/)){
      const s=line.trim();
      if(!s||s.startsWith("#"))continue;
      const i=s.indexOf("=");
      if(i>0){const kk=s.slice(0,i).trim();map[kk]=s.slice(i+1).trim();seen.push(kk);}
    }
    map[k]=v;
    if(seen.indexOf(k)<0)seen.push(k);
    fs.writeFileSync(KEYS,seen.map(kk=>kk+"="+map[kk]).join("\n")+"\n","utf-8");
  }
  function readState(){try{return JSON.parse(rd(STATE,"{}"))}catch(e){return{}}}
  function writeState(s){fs.writeFileSync(STATE,JSON.stringify(s,null,2),"utf-8");}
  function rememberModel(pid,model){
    if(!model)return;
    const st=readState();st.last_model=st.last_model||{};
    if(st.last_model[pid]!==model){st.last_model[pid]=model;writeState(st);}
  }
  function writeCfg(providers,curPid,curModel){
    if(!(curPid in providers))curPid=Object.keys(providers)[0]||null;
    let t=stripRegions(rd(CFG,""));
    t=t.split(/\r?\n/).filter(l=>!/^\s*(model|model_provider)\s*=/.test(l)).join("\n").trim();
    let out="";
    if(providers&&curPid){
      out+=HB+"\n"+'model = "'+esc(curModel||"")+'"\n'+'model_provider = "'+esc(curPid)+'"\n'+HE+"\n\n";
    }
    out+=t+"\n\n";
    if(providers&&curPid){
      out+=BB+"\n";
      for(const pid of Object.keys(providers).sort()){
        const pv=providers[pid];
        out+="[model_providers."+pid+"]\n"
            +'name = "'+esc(pv.name)+'"\n'
            +'base_url = "'+esc(pv.base_url)+'"\n'
            +'env_key = "'+esc(pv.env_key)+'"\n'
            +'wire_api = "'+esc(pv.wire_api||"responses")+'"\n';
        if(pv.models&&pv.models.length)
          out+='models = ["'+pv.models.map(m=>esc(m)).join('","')+'"]\n';
        out+='\n';
      }
      out+=BE+"\n";
    }
    fs.writeFileSync(CFG,out,"utf-8");
  }
  function stripSuffix(raw){
    let b=String(raw||"").trim().replace(/\/+$/,"");
    for(const s of["/chat/completions","/responses","/messages"])
      if(b.endsWith(s)){b=b.slice(0,-s.length);break;}
    return b;
  }
  function slugify(n){return String(n).trim().toLowerCase().replace(/[^a-zA-Z0-9_-]+/g,"-").replace(/-+/g,"-").replace(/^-|-$/g,"")||"provider";}
  function pidFor(name,providers){
    let pid=slugify(name),n=2;
    while(pid in providers){pid=slugify(name)+"-"+n;n++;}
    return pid;
  }
  const OPS={
    list(){
      const c=readCfg(),keys=readKeys(),masked={};
      for(const pid of Object.keys(c.providers)){
        const ek=c.providers[pid].env_key,k=keys[ek];
        masked[ek]=k?(k.slice(0,6)+"..."+k.slice(-4)):null;
      }
      c.keysMasked=masked;c.configPath=CFG;c.keysPath=KEYS;
      return c;
    },
    upsert(a){
      const c=readCfg();
      const firstEmpty=Object.keys(c.providers).length===0;
      const pid=(a.pid&&c.providers[a.pid])?a.pid:pidFor(a.name,c.providers);
      const envKey=(a.env_key||slugify(a.name)+"_api_key").toUpperCase().replace(/[^A-Z0-9_]/g,"_");
      const models=(a.models||[]).filter(m=>m&&m.id&&String(m.id).trim())
        .map(m=>({id:String(m.id).trim(),name:(m.name||'').trim(),contextWindow:m.contextWindow||0,maxOutputTokens:m.maxOutputTokens||0}));
      c.providers[pid]={name:a.name,base_url:stripSuffix(a.base_url),env_key:envKey,wire_api:(a.api_format==="openai-chat-completions"?"chat":"responses"),models:models.map(m=>m.id)};
      if(a.key&&String(a.key).trim())writeKey(envKey,String(a.key).trim());
      if(models.length){const st=readState();st.models_meta=st.models_meta||{};st.models_meta[pid]=models;writeState(st);}
      const model=(a.model&&String(a.model).trim())||(models.length?models[0].id:"");
      if(model)rememberModel(pid,model);
      const last=readState().last_model||{};
      const ptr=(firstEmpty||!(c.current in c.providers))?pid:c.current;
      const effModel=(c.current===pid)?(model||last[pid]||c.currentModel):(ptr===pid?(last[pid]||model||c.currentModel):c.currentModel);
      writeCfg(c.providers,ptr,effModel);
      return{pid:pid,models:models.map(m=>m.id),model:model};
    },
    del(a){
      const c=readCfg();
      if(!(a.pid in c.providers))throw new Error("不存在: "+a.pid);
      delete c.providers[a.pid];
      const ptr=(c.current!==a.pid&&c.current in c.providers)?c.current:Object.keys(c.providers)[0]||null;
      const last=readState().last_model||{};
      const model=ptr?(last[ptr]||c.currentModel):c.currentModel;
      writeCfg(c.providers,ptr,model);
      return{ok:true};
    },
    select(a){
      const c=readCfg();
      if(!(a.pid in c.providers))throw new Error("不存在: "+a.pid);
      if(a.model)rememberModel(a.pid,String(a.model).trim());
      const last=readState().last_model||{};
      const model=a.model||last[a.pid]||c.currentModel;
      writeCfg(c.providers,a.pid,model);
      return{ok:true,model:model};
    },
    discover(a){
      const key=a.key||readKeys()[a.env_key]||"";
      const url=stripSuffix(a.base_url).replace(/\/+$/,"")+"/models";
      const fmt=String(a.api_format||"");
      const isAnthropic=fmt.indexOf("anthropic")>=0;
      const headers=isAnthropic?{"x-api-key":key,"anthropic-version":"2023-06-01",Accept:"application/json"}:{"Authorization":"Bearer "+key,Accept:"application/json"};
      return fetch(url,{headers:headers,signal:AbortSignal.timeout(15000)})
        .then(async r=>{
          const body=await r.json().catch(()=>null);
          if(r.status===401||r.status===403)return{models:[],info:"HTTP "+r.status+" (key 无效或无权限)"};
          if(!r.ok)return{models:[],info:"HTTP "+r.status};
          const arr=(body&&(body.data||body))||[];
          return{models:Array.isArray(arr)?arr.filter(m=>m&&m.id).map(m=>({id:m.id,name:m.name||m.id})):[],info:"HTTP "+r.status};
        })
        .catch(e=>({models:[],info:String(e&&e.message||e)}));
    },
    test(a){
      const key=a.key||readKeys()[a.env_key]||"";
      const base=stripSuffix(a.base_url).replace(/\/+$/,"");
      const fmt=String(a.api_format||"");
      const isAnthropic=fmt.indexOf("anthropic")>=0;
      const model=a.model||"";
      const headers=isAnthropic?{"x-api-key":key,"anthropic-version":"2023-06-01","content-type":"application/json"}:{"Authorization":"Bearer "+key,"content-type":"application/json"};
      const body=JSON.stringify({model:model,max_tokens:8,messages:[{role:"user",content:"hi"}]});
      const attempt=url=>fetch(url,{method:"POST",headers:headers,body:body,signal:AbortSignal.timeout(15000)})
        .then(async r=>{
          if(!isAnthropic&&(r.status===404||r.status===405)&&url===base+"/chat/completions")
            return attempt(base+"/responses");
          if(r.status===401||r.status===403)return{ok:false,error:"HTTP "+r.status+" (key 无效或无权限)"};
          if(!r.ok)return{ok:false,error:"HTTP "+r.status};
          return{ok:true,info:"HTTP "+r.status};
        })
        .catch(e=>({ok:false,error:String(e&&e.message||e)}));
      return attempt(isAnthropic?base+"/v1/messages":base+"/chat/completions");
    }
  };
  try{const __rk=readKeys();for(const __kk in __rk)process.env[__kk]=__rk[__kk];}catch(e){}
  ipcMain.handle("godex-byok:rpc",(ev,payload)=>{
    const op=(payload||{}).op,args=(payload||{}).args;
    try{
      const fn=OPS[op];
      if(!fn)throw new Error("未知操作: "+op);
      return Promise.resolve(fn(args)).then(
        data=>({ok:true,data}),
        e=>({ok:false,error:String(e&&e.message||e)}));
    }catch(e){return Promise.resolve({ok:false,error:String(e&&e.message||e)})}
  });
  return{OPS:OPS,HOME:HOME,CFG:CFG};
})();
'''

# ---------------------------------------------------------------------------
# 渲染层面板组件 (插入 app-initial; 同模块作用域: 可用 m8a/h8a/x2)
# ---------------------------------------------------------------------------
PANEL_JS = r'''function GODEX_dispName(n){const s=String(n||"").replace(/\s*[（(][^）)]*[)）]\s*$/,"").trim();return s||n||"";}
function GODEX_ByokPanel(){
  const uS=m8a.useState,uE=m8a.useEffect,uR=m8a.useRef;
  const J=(t,p)=>(0,h8a.jsx)(t,p),JJ=(t,p)=>(0,h8a.jsxs)(t,p);
  const [snap,setSnap]=uS(null);
  const [sel,setSel]=uS(null);
  const [addMode,setAddMode]=uS(false);
  const [draft,setDraft]=uS(null);
  const [busy,setBusy]=uS(false);
  const [keyShow,setKeyShow]=uS(false);
  const [discOpen,setDiscOpen]=uS(false);
  const [disc,setDisc]=uS({items:[],selected:{},query:"",loading:false,error:""});
  const snapRef=uR(null),draftRef=uR(null),selRef=uR(null),addRef=uR(false),skipSave=uR(true),saveT=uR(null);
  snapRef.current=snap;draftRef.current=draft;selRef.current=sel;addRef.current=addMode;
  function call(o,a){return window.godexByok.call(o,a).then(r=>{if(!r.ok)throw new Error(r.error||"RPC failed");return r.data})}
  function refresh(){return call("list").then(d=>{setSnap(d);
    setSel(p=>{if(p===null&&addRef.current)return p;
      if(p&&d.providers[p])return p;
      return (d.current&&d.providers[d.current])?d.current:(Object.keys(d.providers)[0]||null);});return d;})}
  function buildDraft(pid,s){s=s||snapRef.current;if(!s)return null;const pv=s.providers[pid];if(!pv)return null;
    const meta=(s.modelsMeta||{})[pid]||[];
    return {pid:pid,name:pv.name,base_url:pv.base_url,env_key:pv.env_key,key:"",
      keyMasked:(s.keysMasked||{})[pv.env_key]||"未配置",
      api_format:pv.wire_api==="chat"?"openai-chat-completions":(pv.wire_api==="anthropic"?"anthropic-messages":"openai-responses"),
      models:meta.length?meta.map(m=>Object.assign({},m)):(pv.models||[]).map(id=>({id:id,name:id,contextWindow:0,maxOutputTokens:0})),
      model:(s.lastModel||{})[pid]||""};}
  function resetDraft(pid,s){skipSave.current=true;setDraft(buildDraft(pid,s));}
  uE(()=>{refresh().catch(()=>GODEX_ByokToast("✘ 加载失败, 请重试"))},[]);
  uE(()=>{if(addMode)return;if(!sel){setDraft(null);return;}resetDraft(sel);setKeyShow(false);},[sel]);
  uE(()=>{if(!draft||!draft.pid)return;
    if(skipSave.current){skipSave.current=false;return;}
    if(saveT.current)clearTimeout(saveT.current);
    saveT.current=setTimeout(()=>saveExisting(false),800);},[draft]);
  const S={sub:{fontSize:12,color:"var(--color-foreground-subtle,var(--color-foreground))",opacity:.75},
    lbl:{fontSize:12,color:"var(--color-foreground-subtle,var(--color-foreground))",opacity:.75,marginBottom:4},
    inp:{padding:"7px 10px",borderRadius:8,border:"1px solid var(--color-border)",background:"transparent",color:"var(--color-foreground)",fontSize:13,width:"100%",boxSizing:"border-box"},
    btn:{padding:"5px 12px",borderRadius:8,border:"1px solid var(--color-border)",background:"transparent",color:"var(--color-foreground)",cursor:"pointer",fontSize:13},
    btnPri:{padding:"6px 16px",borderRadius:8,border:"none",background:"var(--color-primary,#1a1a1a)",color:"var(--color-primary-foreground,#fff)",cursor:"pointer",fontSize:13},
    outln:{padding:"3px 12px",borderRadius:8,border:"1px solid var(--color-border)",background:"transparent",color:"var(--color-foreground)",cursor:"pointer",fontSize:12,flexShrink:0},
    ibtn:{width:26,height:26,display:"flex",alignItems:"center",justifyContent:"center",border:"none",background:"transparent",color:"var(--color-foreground)",opacity:.6,cursor:"pointer",borderRadius:6,flexShrink:0,padding:0},
    pillOn:{fontSize:12,fontWeight:600,padding:"2px 10px",borderRadius:999,background:"#16a34a",color:"#fff",flexShrink:0},
    pillOff:{fontSize:12,fontWeight:600,padding:"2px 10px",borderRadius:999,background:"rgba(128,128,128,.18)",color:"var(--color-foreground)",opacity:.85,flexShrink:0},
    badge:{fontSize:11,fontWeight:600,padding:"2px 8px",borderRadius:999,border:"1px solid var(--color-border)",opacity:.85,flexShrink:0},
    icon:{width:26,height:26,borderRadius:7,border:"1px solid var(--color-border)",display:"flex",alignItems:"center",justifyContent:"center",fontSize:12,fontWeight:700,flexShrink:0},
    dot:{width:7,height:7,borderRadius:999,background:"#16a34a",flexShrink:0},
    row:{display:"flex",alignItems:"center",gap:8,padding:"7px 8px",borderRadius:9,cursor:"pointer",fontSize:13},
    rowOn:{background:"var(--color-secondary,rgba(128,128,128,.14))",fontWeight:600},
    mrow:{display:"flex",gap:4,alignItems:"center",marginTop:8,padding:"3px 4px 3px 12px",border:"1px solid var(--color-border)",borderRadius:10},
    minp:{flex:"1 1 auto",minWidth:0,border:"none",background:"transparent",color:"var(--color-foreground)",fontSize:13,padding:"6px 0",outline:"none"},
    ov:{position:"fixed",inset:0,background:"rgba(0,0,0,.45)",display:"flex",alignItems:"center",justifyContent:"center",zIndex:9999},
    box:{background:"var(--color-surface,#fff)",color:"var(--color-foreground)",borderRadius:12,padding:"20px",width:"min(620px,92vw)",maxHeight:"82vh",overflowY:"auto"},
    empty:{display:"flex",alignItems:"center",gap:8,marginTop:8,padding:"14px 16px",border:"1px dashed var(--color-border)",borderRadius:10,fontSize:13,color:"var(--color-foreground-subtle,var(--color-foreground))",opacity:.75}};
  const APIFMT=[["openai-chat-completions","Chat Completions (/chat/completions)"],["openai-responses","Responses (/v1/responses)"],["anthropic-messages","Anthropic Messages (/v1/messages)"]];
  function Ic(ch,size){return J("svg",{width:size||14,height:size||14,viewBox:"0 0 24 24",fill:"none",stroke:"currentColor",strokeWidth:2,strokeLinecap:"round",strokeLinejoin:"round",children:ch})}
  const PEN=()=>Ic([J("path",{d:"M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"}),J("path",{d:"m15 5 4 4"})],14);
  const TRASH=()=>Ic([J("path",{d:"M3 6h18"}),J("path",{d:"M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"}),J("path",{d:"M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"})],14);
  const REFRESH=()=>Ic([J("path",{d:"M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"}),J("path",{d:"M21 3v5h-5"})],15);
  const GRIP=()=>Ic([J("circle",{cx:"9",cy:"5",r:"1"}),J("circle",{cx:"9",cy:"12",r:"1"}),J("circle",{cx:"9",cy:"19",r:"1"}),J("circle",{cx:"15",cy:"5",r:"1"}),J("circle",{cx:"15",cy:"12",r:"1"}),J("circle",{cx:"15",cy:"19",r:"1"})],13);
  const PLUS=()=>Ic([J("path",{d:"M5 12h14"}),J("path",{d:"M12 5v14"})],14);
  const EYE=off=>Ic(off?[J("path",{d:"M9.88 9.88a3 3 0 1 0 4.24 4.24"}),J("path",{d:"M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"}),J("path",{d:"M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"}),J("line",{x1:"2",x2:"22",y1:"2",y2:"22"})]:[J("path",{d:"M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"}),J("circle",{cx:"12",cy:"12",r:"3"})],14);
  const INFO=()=>Ic([J("circle",{cx:"12",cy:"12",r:"10"}),J("path",{d:"M12 16v-4"}),J("path",{d:"M12 8h.01"})],14);
  const ALERT=()=>Ic([J("circle",{cx:"12",cy:"12",r:"10"}),J("line",{x1:"12",x2:"12",y1:"8",y2:"12"}),J("line",{x1:"12",y1:"16",x2:"12.01",y2:"16"})],14);
  function fmtCtx(c){if(!c)return"";if(c>=1048576){return (Math.round(c/104857.6)/10)+"M";}if(c>=1024){return Math.round(c/1024)+"K";}return String(c);}
  function parseCtx(s){s=String(s||"").trim().toUpperCase();if(!s)return 0;const m=s.match(/^([\d.]+)\s*(M|K)?$/);
    if(!m)return parseInt(s,10)||0;let n=parseFloat(m[1])||0;
    if(m[2]==="M")n*=1e6;else if(m[2]==="K")n*=1e3;return Math.round(n);}
  function up(k,v){setDraft(d=>Object.assign({},d,{[k]:v}))}
  function upModelRow(i,k,v){setDraft(d=>{const m=d.models.slice();m[i]=Object.assign({},m[i],{[k]:v});return Object.assign({},d,{models:m})})}
  function startAdd(){setDiscOpen(false);setAddMode(true);skipSave.current=true;
    setDraft({pid:"",name:"",base_url:"",env_key:"",key:"",keyMasked:"",api_format:"openai-chat-completions",models:[],model:""});}
  function pickRow(pid){setAddMode(false);setSel(pid);resetDraft(pid);}
  function doRefresh(){refresh().then(d=>{if(selRef.current)resetDraft(selRef.current,d)}).catch(()=>{})}
  function saveExisting(showToast){const d=draftRef.current;if(!d||!d.pid)return;
    if(!d.name||!d.name.trim()||!d.base_url||!d.base_url.trim())return;
    const models=d.models.filter(m=>m.id&&String(m.id).trim());
    const model=(models.some(m=>m.id===d.model)?d.model:(models[0]||{}).id||"");
    call("upsert",Object.assign({},d,{models:models,model:model})).then(()=>{
      if(showToast)GODEX_ByokToast("已保存, 重启应用后生效");
      if(d.key&&d.key.trim())setDraft(x=>Object.assign({},x,{key:""}));
      return refresh();})
      .catch(e=>GODEX_ByokToast("✘ 保存失败: "+(e&&e.message||e)));}
  function createNew(){const d=draftRef.current;if(!d||!d.name||!d.base_url)return;
    setBusy(true);
    call("upsert",Object.assign({},d,{models:d.models.filter(m=>m.id&&m.id.trim()),model:(d.models.find(m=>m.id&&m.id.trim())||{}).id||""})).then(r=>{
      setAddMode(false);setDiscOpen(false);GODEX_ByokToast("已添加 "+(d.name||r.pid)+", 重启应用后生效");
      setSel(r.pid);return refresh();})
      .catch(e=>GODEX_ByokToast("✘ 创建失败: "+(e&&e.message||e))).then(()=>setBusy(false));}
  function enable(pid){setBusy(true);call("select",{pid:pid}).then(()=>refresh())
      .catch(e=>GODEX_ByokToast("✘ "+(e&&e.message||e))).then(()=>setBusy(false))}
  function disable(pid){const others=Object.keys((snap||{}).providers||{}).filter(x=>x!==pid);
    if(!others.length){GODEX_ByokToast("至少需要保留一个已启用的供应商。");return;}
    setBusy(true);call("select",{pid:others[0]}).then(()=>refresh())
      .catch(e=>GODEX_ByokToast("✘ "+(e&&e.message||e))).then(()=>setBusy(false))}
  function delProv(pid){if(!pid)return;if(!window.confirm("删除供应商 "+pid+" ?"))return;
    setBusy(true);call("del",{pid:pid}).then(()=>{setAddMode(false);setSel(null);return refresh()})
      .catch(e=>GODEX_ByokToast("✘ "+(e&&e.message||e))).then(()=>setBusy(false))}
  function runTest(mid){const d=draftRef.current||{};if(!mid)return;
    GODEX_ByokToast("测试中… ["+mid+"]");
    call("test",{base_url:d.base_url,env_key:d.env_key,model:mid,api_format:d.api_format,key:d.key||""}).then(r=>{
      GODEX_ByokToast((r.ok?"✔ 测试通过":"✘ 测试失败")+" ["+mid+"] "+(r.ok?(r.info||""):(r.error||"")));})
      .catch(e=>GODEX_ByokToast("✘ 测试失败 ["+mid+"] "+(e&&e.message||e)))}
  function runDiscover(){const f=draftRef.current||{};setDiscOpen(true);setDisc({items:[],selected:{},query:"",loading:true,error:""});
    call("discover",{base_url:f.base_url,env_key:f.env_key,api_format:f.api_format,key:f.key||""}).then(r=>{
      setDisc(d=>Object.assign({},d,{loading:false,items:r.models||[],error:r.info||""}));
    }).catch(e=>setDisc(d=>Object.assign({},d,{loading:false,error:String(e&&e.message||e)})))}
  function toggleSel(id){setDisc(d=>{const s=Object.assign({},d.selected);if(s[id])delete s[id];else s[id]=1;return Object.assign({},d,{selected:s})})}
  function modelRow(m,i){return JJ("div",{key:i,style:S.mrow,children:[
    J("input",{style:S.minp,value:m.id,placeholder:"填写供应商提供的模型 ID，而非自定义昵称",
      onChange:e=>upModelRow(i,"id",e.target.value)}),
    J("button",{style:Object.assign({},S.btn,{padding:"2px 10px",fontSize:12,flexShrink:0}),title:"测试该模型的连接",
      disabled:busy||!draft.base_url||!m.id,onClick:()=>runTest(m.id),children:"连接测试"}),
    m.contextWindow>0?J("span",{style:S.badge,title:"上下文窗口："+fmtCtx(m.contextWindow),children:fmtCtx(m.contextWindow)}):null,
    J("button",{style:S.ibtn,title:"编辑模型配置",onClick:()=>{const n=window.prompt("上下文窗口 (tokens, 支持 1M/256K 后缀)",m.contextWindow?String(m.contextWindow):"");if(n!=null)upModelRow(i,"contextWindow",parseCtx(n))},children:J(PEN,{})}),
    J("button",{style:S.ibtn,title:"删除模型",onClick:()=>{const mm=draft.models.slice();mm.splice(i,1);setDraft(d=>Object.assign({},d,{models:mm}))},children:J(TRASH,{})}),
  ]})}
  function fieldsBlock(){return JJ("div",{children:[
    J("div",{style:{marginTop:14},children:J("div",{style:S.lbl,children:"Base URL"})}),
    J("input",{style:S.inp,value:draft.base_url,placeholder:"https://api.deepseek.com",onChange:e=>up("base_url",e.target.value)}),
    JJ("div",{style:{display:"flex",gap:10,marginTop:12,flexWrap:"wrap"},children:[
      JJ("div",{style:{flex:"1 1 240px"},children:[
        J("div",{style:S.lbl,children:"API 格式"}),
        J("select",{style:S.inp,value:draft.api_format,onChange:e=>up("api_format",e.target.value),
          children:APIFMT.map(x=>J("option",{key:x[0],value:x[0],children:x[1]}))}),
      ]}),
      JJ("div",{style:{flex:"1 1 240px"},children:[
        J("div",{style:S.lbl,children:"API Key"}),
        JJ("div",{style:{position:"relative"},children:[
          J("input",{style:Object.assign({},S.inp,{paddingRight:34}),type:keyShow?"text":"password",value:draft.key,placeholder:draft.pid?("已配置: "+draft.keyMasked+" (留空不改)"):"输入 API Key",
            onChange:e=>up("key",e.target.value)}),
          J("button",{style:{position:"absolute",right:6,top:5,border:"none",background:"transparent",color:"var(--color-foreground)",cursor:"pointer",opacity:.6,padding:0,display:"flex"},title:"显示/隐藏",onClick:()=>setKeyShow(k=>!k),children:EYE(keyShow)}),
        ]}),
      ]}),
    ]}),
  ]})}
  function modelsBlock(){return JJ("div",{children:[
    J("div",{style:{marginTop:16,fontSize:13,fontWeight:600},children:"模型列表"}),
    draft.models.length?J("div",{children:draft.models.map((m,i)=>modelRow(m,i))}):
      JJ("div",{style:S.empty,children:[J(ALERT,{}),"当前没有配置模型，添加模型后可在聊天中使用。"]}),
    JJ("div",{style:{display:"flex",gap:8,marginTop:12,flexWrap:"wrap"},children:[
      J("button",{style:S.btn,onClick:()=>setDraft(d=>Object.assign({},d,{models:d.models.concat([{id:"",name:"",contextWindow:0,maxOutputTokens:0}])})),children:"＋ 添加模型"}),
      J("button",{style:S.btn,disabled:busy||!draft.base_url,onClick:runDiscover,children:"获取模型列表"}),
    ]}),
  ]})}
  function detailPane(){
    const isCur=draft.pid&&draft.pid===snap.current;
    return JJ("div",{style:{flex:"1 1 auto",minWidth:0,padding:"18px 22px"},children:[
      JJ("div",{style:{display:"flex",alignItems:"center",gap:10,flexWrap:"wrap"},children:[
        J("span",{style:{fontSize:17,fontWeight:700},children:GODEX_dispName(draft.name)||"(未命名供应商)"}),
        J("button",{style:S.ibtn,title:"重命名",onClick:()=>{const n=window.prompt("供应商名称",draft.name);if(n)up("name",n)},children:J(PEN,{})}),
        isCur?J("span",{style:S.pillOn,children:"已启用"}):J("span",{style:S.pillOff,children:"已禁用"}),
        J("button",{style:S.outln,title:isCur?"停用该供应商":"启用该供应商",disabled:busy,onClick:()=>isCur?disable(draft.pid):enable(draft.pid),children:isCur?"禁用":"启用"}),
        J("span",{style:{flex:1}}),
        J("button",{style:S.ibtn,title:"删除供应商",disabled:busy,onClick:()=>delProv(draft.pid),children:J(TRASH,{})}),
      ]}),
      fieldsBlock(),
      modelsBlock(),
    ]});
  }
  function addPane(){
    const canAdd=draft.name&&draft.base_url&&draft.models.some(m=>m.id&&m.id.trim());
    return JJ("div",{style:{flex:"1 1 auto",minWidth:0,padding:"18px 22px"},children:[
      J("div",{style:{fontSize:17,fontWeight:700},children:"添加模型供应商"}),
      J("div",{style:Object.assign({},S.sub,{marginTop:4}),children:"配置一个完全自定义的 API 端点和初始模型。"}),
      J("div",{style:{marginTop:14},children:J("div",{style:S.lbl,children:"名称"})}),
      J("input",{style:S.inp,value:draft.name,placeholder:"例如: DeepSeek",onChange:e=>up("name",e.target.value)}),
      fieldsBlock(),
      modelsBlock(),
      JJ("div",{style:{display:"flex",alignItems:"center",gap:8,marginTop:18},children:[
        draft.models.some(m=>m.id&&m.id.trim())?null:JJ("div",{style:{display:"flex",alignItems:"center",gap:6,fontSize:12,color:"var(--color-foreground-subtle,var(--color-foreground))",opacity:.8},children:[J(INFO,{}),"添加供应商前，请至少添加一个模型。"]}),
        J("span",{style:{flex:1}}),
        J("button",{style:S.btnPri,disabled:busy||!canAdd,onClick:createNew,children:"添加供应商"}),
      ]}),
    ]});
  }
  function emptyPane(){return J("div",{style:{flex:"1 1 auto",minWidth:0,padding:24,display:"flex",alignItems:"center",justifyContent:"center",fontSize:13,color:"var(--color-foreground-subtle,var(--color-foreground))",opacity:.8},children:"还没有配置任何供应商，点左侧「＋ 添加供应商」。"})}
  function discDialog(){
    const existing=new Set((draft?draft.models:[]).map(m=>m.id));
    const visible=(disc.items||[]).filter(m=>((m.id||"")+" "+(m.name||"")).toLowerCase().indexOf((disc.query||"").toLowerCase())>=0);
    const available=visible.filter(m=>!existing.has(m.id));
    const all=available.length>0&&available.every(m=>disc.selected[m.id]);
    const chosen=(disc.items||[]).filter(m=>disc.selected[m.id]&&!existing.has(m.id));
    return JJ("div",{style:S.ov,onClick:()=>setDiscOpen(false),children:[
      JJ("div",{style:S.box,onClick:e=>e.stopPropagation(),children:[
        JJ("div",{children:[J("div",{style:{fontSize:16,fontWeight:600},children:"选择要添加的模型"}),J("div",{style:S.sub,children:"从当前供应商获取模型 ID,支持一次添加多个模型。"})]}),
        disc.loading?J("div",{style:{padding:"16px",textAlign:"center",color:"var(--color-foreground-subtle)"},children:"正在获取模型列表…"}):null,
        disc.error?J("div",{style:{marginTop:8,fontSize:13,color:"var(--color-primary,#16a34a)"},children:disc.error}):null,
        !disc.loading&&disc.items.length?JJ("div",{children:[
          J("input",{style:S.inp,placeholder:"搜索模型 ID 或名称",value:disc.query,onChange:e=>setDisc(d=>Object.assign({},d,{query:e.target.value}))}),
          JJ("div",{style:{display:"flex",alignItems:"center",justifyContent:"space-between",marginTop:8,fontSize:13},children:[
            J("label",{style:{display:"flex",alignItems:"center",gap:6,cursor:"pointer"},children:[
              J("input",{type:"checkbox",checked:all,onChange:()=>setDisc(d=>{const s=Object.assign({},d.selected);if(all){for(const m of available)delete s[m.id];}else{for(const m of available)s[m.id]=1;}return Object.assign({},d,{selected:s})})}),
              "全选当前结果",
            ]}),
            J("span",{style:S.sub,children:"已选 "+chosen.length+" / 共 "+disc.items.length+" 个"}),
          ]}),
          JJ("div",{style:{marginTop:8,maxHeight:240,overflowY:"auto",border:"1px solid var(--color-border)",borderRadius:8},children:
            visible.length?visible.map(m=>JJ("label",{key:m.id,style:{display:"flex",alignItems:"center",gap:8,padding:"6px 10px",borderBottom:"1px solid var(--color-border)",cursor:existing.has(m.id)?"default":"pointer"},children:[
              J("input",{type:"checkbox",checked:existing.has(m.id)||!!disc.selected[m.id],disabled:existing.has(m.id),onChange:()=>toggleSel(m.id)}),
              J("span",{style:{minWidth:0,flex:1,overflowWrap:"break-word"},children:m.id}),
              (m.name&&m.name!==m.id)?J("span",{style:S.sub,children:m.name}):null,
              existing.has(m.id)?J("span",{style:S.sub,children:"已添加"}):null,
            ]})):J("div",{style:{padding:"12px",color:"var(--color-foreground-subtle)"},children:"没有匹配的模型"}),
          }),
        ]}):null,
        !disc.loading&&!disc.error&&!disc.items.length?J("div",{style:{padding:"12px",color:"var(--color-foreground-subtle)"},children:"供应商返回的模型列表为空,可手动添加模型。"}):null,
        JJ("div",{style:{display:"flex",justifyContent:"flex-end",gap:8,marginTop:14},children:[
          J("button",{style:S.btn,onClick:()=>setDiscOpen(false),children:"取消"}),
          J("button",{style:S.btn,disabled:disc.loading,onClick:runDiscover,children:"重新获取"}),
          J("button",{style:S.btnPri,disabled:disc.loading||!chosen.length,onClick:()=>{
            const picks=(disc.items||[]).filter(m=>disc.selected[m.id]&&!existing.has(m.id));
            setDraft(d=>Object.assign({},d,{models:d.models.concat(picks.map(m=>({id:m.id,name:m.name||m.id,contextWindow:0,maxOutputTokens:0})))}));
            setDiscOpen(false)},children:"添加所选模型（"+chosen.length+"）"}),
        ]}),
      ]}),
    ]});
  }
  if(!snap)return J("div",{style:{maxWidth:1000,margin:"0 auto",padding:"20px 24px",color:"var(--color-foreground-subtle)"},children:"加载中…"});
  const provRows=Object.keys(snap.providers).sort().map(pid=>[pid,snap.providers[pid]]);
  return JJ("div",{style:{maxWidth:1000,margin:"0 auto",padding:"20px 24px 40px"},children:[
    JJ("div",{style:{display:"flex",alignItems:"flex-start",justifyContent:"space-between"},children:[
      JJ("div",{children:[
        J("div",{style:{fontSize:20,fontWeight:600},children:"模型设置"}),
        J("div",{style:S.sub,children:"管理自定义模型供应商，配置后可在聊天时选择使用。"}),
      ]}),
      J("button",{style:S.ibtn,title:"刷新",onClick:doRefresh,children:J(REFRESH,{})}),
    ]}),
    JJ("div",{style:{display:"flex",marginTop:16,border:"1px solid var(--color-border)",borderRadius:12,overflow:"hidden",minHeight:430,background:"var(--color-surface,transparent)"},children:[
      JJ("div",{style:{width:230,flexShrink:0,borderRight:"1px solid var(--color-border)",padding:"12px 10px",display:"flex",flexDirection:"column"},children:[
        J("div",{style:{fontSize:12,fontWeight:600,opacity:.7,padding:"0 8px 8px"},children:"自定义供应商"}),
        J("div",{style:{display:"flex",flexDirection:"column",gap:2},children:provRows.map(r=>JJ("div",{style:Object.assign({},S.row,sel===r[0]&&!addMode?S.rowOn:null),onClick:()=>pickRow(r[0]),children:[
          J("div",{style:S.icon,children:(r[1].name||"?").slice(0,1).toUpperCase()}),
          J("span",{style:{flex:1,minWidth:0,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"},children:GODEX_dispName(r[1].name||r[0])}),
          snap.current===r[0]?J("div",{style:S.dot,title:"当前使用"}):null,
          J("span",{style:{opacity:.35,flexShrink:0,display:"flex",cursor:"grab"},title:"拖拽调整供应商顺序",children:J(GRIP,{})}),
        ]}))}),
        J("div",{style:{flex:1}}),
        addMode?J("button",{style:Object.assign({},S.btnPri,{marginTop:10,width:"100%",textAlign:"center"}),onClick:startAdd,children:"＋ 添加供应商"}):
          J("button",{style:{display:"flex",alignItems:"center",gap:6,padding:"8px 10px",border:"none",background:"transparent",color:"var(--color-foreground-subtle,var(--color-foreground))",opacity:.85,cursor:"pointer",fontSize:13,textAlign:"left"},onClick:startAdd,children:[J(PLUS,{}),"添加供应商"]}),
      ]}),
      addMode?addPane():(draft&&draft.pid?detailPane():emptyPane()),
    ]}),
    discOpen?discDialog():null,
  ]});
}
function GODEX_ByokToast(txt){
  try{document.querySelectorAll("[data-ody-byok-toast]").forEach(e=>e.remove());
    const d=document.createElement("div");d.setAttribute("data-ody-byok-toast","1");
    d.style.cssText="position:fixed;bottom:24px;left:50%;transform:translateX(-50%);z-index:99999;background:var(--color-primary,#2b7);color:var(--color-primary-foreground,#fff);padding:9px 18px;border-radius:10px;font-size:13px;box-shadow:0 6px 24px rgba(0,0,0,.25);";
    d.textContent=txt;document.body.appendChild(d);setTimeout(()=>d.remove(),3800);}catch(e){}
}
function GODEX_ByokOpenSettings(deep){
  function realClick(el){const r=el.getBoundingClientRect();const o={bubbles:true,cancelable:true,clientX:r.x+r.width/2,clientY:r.y+r.height/2,button:0,pointerId:1,pointerType:"mouse",isPrimary:true};
    el.dispatchEvent(new PointerEvent("pointerdown",o));el.dispatchEvent(new MouseEvent("mousedown",o));
    el.dispatchEvent(new PointerEvent("pointerup",o));el.dispatchEvent(new MouseEvent("mouseup",o));
    el.dispatchEvent(new MouseEvent("click",o));}
  function findText(re){const els=[...document.querySelectorAll('button,[role="menuitem"],[role="menuitemradio"],[role="menu"] div,a')].filter(e=>{const t=(e.innerText||"").trim();return re.test(t)&&e.getBoundingClientRect().width>0;});return els[els.length-1]||null;}
  const prof=document.querySelector('[aria-label="打开个人资料菜单"]');
  if(prof){realClick(prof);}
  setTimeout(()=>{const it=findText(/^设置/);if(it)realClick(it);
    setTimeout(()=>{if(deep===false)return;const side=findText(/^模型设置$/);if(side)realClick(side);else GODEX_ByokToast("未找到「模型设置」入口");},6000);
  },1200);
}
function GODEX_ByokMenuInstall(){
  if(globalThis.__GODEX_BYOK_MENU__)return;globalThis.__GODEX_BYOK_MENU__=1;
  const IT_CLS="no-drag outline-hidden flex shrink-0 items-center rounded-xl p-[var(--app-menu-item-padding,var(--padding-row-y)_var(--padding-row-x))] text-sm text-default group hover:bg-primary-ghost-hover focus:bg-primary-ghost-hover cursor-interaction";
  let byokState=null;
  function refreshByok(){try{window.godexByok.call("list",{}).then(r=>{if(r&&r.ok)byokState=r.data;}).catch(()=>{});}catch(e){}}
  function curModelName(){if(!byokState)return null;const pid=byokState.current;if(!pid||!byokState.providers||!byokState.providers[pid])return null;return (byokState.lastModel||{})[pid]||null;}
  function closeMenu(){try{document.dispatchEvent(new KeyboardEvent("keydown",{key:"Escape",bubbles:true,cancelable:true}));}catch(e){}}
  function mkSep(){const d=document.createElement("div");d.setAttribute("data-ody-byok-group","1");d.style.cssText="border-top:1px solid var(--color-border,#ddd2);margin:4px 10px;";d.setAttribute("role","separator");return d;}
  function mkGroup(label){const d=document.createElement("div");d.setAttribute("data-ody-byok-group","1");d.style.cssText="padding:6px 12px 2px;font-size:11px;opacity:.55;pointer-events:none;";d.textContent=label;return d;}
  function mkItem(label,checked,onPick){
    const it=document.createElement("div");it.setAttribute("role","menuitemradio");it.setAttribute("aria-checked",checked?"true":"false");it.className=IT_CLS;
    const row=document.createElement("div");row.style.cssText="display:flex;width:100%;align-items:center;gap:6px;min-width:0;";
    const sp=document.createElement("span");sp.style.cssText="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;";sp.textContent=label;
    row.appendChild(sp);
    if(checked){const c=document.createElement("span");c.style.cssText="color:var(--color-primary,#2b7);font-weight:700;flex-shrink:0;";c.textContent="✓";row.appendChild(c);}
    it.appendChild(row);
    it.addEventListener("click",e=>{e.preventDefault();e.stopPropagation();try{onPick();}catch(_){}});
    return it;}
  function selectModel(pid,pvName,mid){window.godexByok.call("select",{pid:pid,model:mid}).then(r=>{
    if(r.ok){GODEX_ByokToast("已切换到 "+(pvName||pid)+"/"+mid+"，重启应用后生效");}else{GODEX_ByokToast("✘ 切换失败: "+(r.error||"?"));}
    refreshByok();closeMenu();});}
  function appendGroup(menu){
    if(menu.querySelector("[data-ody-byok-group]"))return;
    window.godexByok.call("list",{}).then(res=>{
      if(!res||!res.ok)return;const d=res.data;byokState=d;
      const provs=Object.keys(d.providers||{});if(!provs.length)return;
      if(!document.body.contains(menu))return;
      const curPid=d.current,curModel=(d.lastModel||{})[curPid];
      menu.appendChild(mkSep());
      menu.appendChild(mkGroup("模型服务"));
      for(const pid of provs.sort()){
        const pv=d.providers[pid];
        const meta=(d.modelsMeta||{})[pid]||[];
        const list=meta.length?meta.map(m=>m.id):(pv.models||[]);
        if(!list.length)continue;
        menu.appendChild(mkGroup(GODEX_dispName(pv.name||pid)));
        for(const mid of list)menu.appendChild(mkItem(mid,pid===curPid&&mid===curModel,()=>selectModel(pid,pv.name||pid,mid)));
      }
      const sep2=mkSep();menu.appendChild(sep2);
      const mg=mkItem("管理模型",false,()=>{closeMenu();setTimeout(()=>GODEX_ByokOpenSettings(true),150);});
      mg.setAttribute("role","menuitem");mg.removeAttribute("aria-checked");
      mg.setAttribute("data-ody-byok-group","1");
      mg.style.fontWeight="600";menu.appendChild(mg);
    }).catch(()=>{});
  }
  function fixFooter(){
    const pb=document.querySelector('button[aria-label="打开个人资料菜单"]');
    if(!pb)return;
    const span=pb.querySelector("span");
    if(!span)return;
    const w=document.createTreeWalker(span,NodeFilter.SHOW_TEXT);let n;const tns=[];
    while((n=w.nextNode()))tns.push(n);
    const t=tns.find(x=>(x.data||"").trim());
    if(t&&t.data!=="个人")t.data="个人";
  }
  function ensureUserIcon(){
    const pb=document.querySelector('button[aria-label="打开个人资料菜单"]');
    if(!pb)return;
    if(pb.querySelector('svg[data-ody-user-icon="1"]'))return;
    const svg=pb.querySelector("svg");
    if(!svg)return;
    const ns="http://www.w3.org/2000/svg";
    const n=document.createElementNS(ns,"svg");
    n.setAttribute("data-ody-user-icon","1");
    n.setAttribute("width","16");n.setAttribute("height","16");
    n.setAttribute("viewBox","0 0 24 24");n.setAttribute("fill","none");
    n.setAttribute("stroke","currentColor");n.setAttribute("stroke-width","2");
    n.setAttribute("stroke-linecap","round");n.setAttribute("stroke-linejoin","round");
    n.style.flexShrink="0";
    n.innerHTML='<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle>';
    svg.style.display="none";
    svg.parentNode.insertBefore(n,svg);
  }
  function ensureGear(){
    const pb=document.querySelector('button[aria-label="打开个人资料菜单"]');
    if(!pb)return;
    const row=pb.parentElement;if(!row)return;
    let gear=row.querySelector('button[data-ody-byok-gear]');
    if(!gear){
      gear=document.createElement("button");gear.type="button";
      gear.setAttribute("data-ody-byok-gear","1");gear.setAttribute("aria-label","打开设置");gear.title="设置";
      gear.style.cssText="display:flex;align-items:center;justify-content:center;width:30px;height:30px;border:none;background:transparent;color:inherit;cursor:pointer;border-radius:8px;flex-shrink:0;opacity:.8;";
      gear.innerHTML='<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.08a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"></path><circle cx="12" cy="12" r="3"></circle></svg>';
      gear.addEventListener("click",e=>{e.preventDefault();e.stopPropagation();GODEX_ByokOpenSettings(false);});
      row.appendChild(gear);
    }
  }
  function fixTrigger(){
    const bs=document.querySelectorAll("button");
    let pick=null;
    for(const b of bs){const t=(b.innerText||"").trim();if(t==="自定义"&&b.getBoundingClientRect().width>0)pick=b;}
    if(!pick){
      let sb=null;
      for(const b of bs){const a=b.getAttribute("aria-label")||"";if(a==="发送"||a==="停止"||/^(send|stop)/i.test(a)){sb=b;break;}}
      if(!sb)return;
      const rs=sb.getBoundingClientRect();
      for(const b of bs){const r=b.getBoundingClientRect();if(Math.abs(r.y-rs.y)<10&&r.x<rs.x&&r.width>20&&(b.innerText||"").trim())pick=b;}
    }
    if(!pick)return;
    const want=curModelName();if(!want)return;
    const w=document.createTreeWalker(pick,NodeFilter.SHOW_TEXT);let n;
    while((n=w.nextNode())){if(n.data==="自定义")n.data=want;}
  }
  let fixPending=false;
  function scheduleFix(){
    if(fixPending)return;fixPending=true;
    setTimeout(()=>{fixPending=false;try{fixFooter();ensureUserIcon();ensureGear();fixTrigger();}catch(e){}},120);
  }
  const mo=new MutationObserver(()=>{
    try{
      scheduleFix();
      const menus=document.querySelectorAll('[role="menu"]');
      for(const menu of menus){
        if(menu.dataset.odyByok)continue;
        const radios=menu.querySelectorAll('[role="menuitemradio"]');
        if(radios.length<2)continue;
        if(!/推荐模型集|Recommended model/i.test(menu.textContent||""))continue;
        menu.dataset.odyByok="1";
        appendGroup(menu);
      }
    }catch(e){}
  });
  refreshByok();
  scheduleFix();
  setInterval(refreshByok,10000);
  mo.observe(document.documentElement,{childList:true,subtree:true});
}
if(typeof document!=="undefined"){
  if(document.readyState!=="loading")GODEX_ByokMenuInstall();
  else document.addEventListener("DOMContentLoaded",GODEX_ByokMenuInstall);
}
'''

# ---------------------------------------------------------------------------
# 锚点编辑表: (文件, old, new, 幂等标记)
# ---------------------------------------------------------------------------
LABEL_OLD = "case`voice`:{let e;return t[11]==="
EDITS = [
    (REND_F, "function Ueo(",
     "/*GODEX_BYOK_PANEL*/" + PANEL_JS + '\nglobalThis.GODEX_ByokPanel=GODEX_ByokPanel;\nfunction GODEX_ByokIcon(){return (0,h8a.jsxs)("svg",{width:16,height:16,viewBox:"0 0 16 16",fill:"none",xmlns:"http://www.w3.org/2000/svg",children:[(0,h8a.jsx)("rect",{x:2.5,y:2.5,width:11,height:11,rx:2,stroke:"currentColor",strokeWidth:1.4}),(0,h8a.jsx)("path",{d:"M5 6.5h6M5 9.5h4",stroke:"currentColor",strokeWidth:1.4,strokeLinecap:"round"})]})}\nglobalThis.GODEX_ByokIcon=GODEX_ByokIcon;\nfunction Ueo(',
     "GODEX_BYOK_PANEL"),
    (REND_F,
     '"git-settings":i2(async()=>(await v(async()=>{let{GitSettings:e}',
     '/*GODEX_BYOK_ROUTE*/"' + SLUG + '":i2(async()=>GODEX_ByokPanel),'
     '"git-settings":i2(async()=>(await v(async()=>{let{GitSettings:e}',
     "GODEX_BYOK_ROUTE"),
    (REND_F,
     "e5a=[{slug:`general-settings`},",
     "e5a=[{slug:`general-settings`},{slug:`" + SLUG + "`},/*GODEX_BYOK_SLUG*/",
     "GODEX_BYOK_SLUG"),
    (REND_F,
     "X8a=`general-settings.notifications",
     "X8a=/*GODEX_BYOK_WL*/`general-settings." + SLUG + ".notifications",
     "GODEX_BYOK_WL"),
    (REND_F,
     LABEL_OLD,
     "case`" + SLUG + "`:{return (0,x2.jsx)(`span`,{children:`模型设置`})}/*GODEX_BYOK_LABEL*/"
     + LABEL_OLD,
     "GODEX_BYOK_LABEL"),
    (REND_F,
     "function y2(e,t=!1,n=!1){if(e===`usage`&&t)",
     "function y2(e,t=!1,n=!1){/*GODEX_BYOK_Y2*/if(e===`" + SLUG + "`)return{id:`settings.section." + SLUG + "`,defaultMessage:`模型设置`,description:`Navigation title for BYOK model providers`};if(e===`usage`&&t)",
     "GODEX_BYOK_Y2"),
    (SPV_F,
     "case`keyboard-shortcuts`:return!0;",
     "case`keyboard-shortcuts`:case`" + SLUG + "`:return!0;/*GODEX_BYOK_VIS*/",
     "GODEX_BYOK_VIS"),
    (SPV_F,
     "ai=[`profile`,",
     "ai=[`profile`,`" + SLUG + "`,/*GODEX_BYOK_AI*/",
     "GODEX_BYOK_AI"),
    (SPV_F,
     'Xr={"general-settings":',
     'Xr={"' + SLUG + '":{component:globalThis.GODEX_ByokIcon},/*GODEX_BYOK_XR*/"general-settings":',
     "GODEX_BYOK_XR"),
    (SPG_F,
     ",slugs:[`general-settings`,`notifications`,",
     ",slugs:[`general-settings`,`" + SLUG + "`,`notifications`,/*GODEX_BYOK_GRP*/",
     "GODEX_BYOK_GRP"),
]

PRELOAD_OLD = "`electronBridge`,R),typeof window"
PRELOAD_NEW = ("`electronBridge`,R),"
               "e.contextBridge.exposeInMainWorld(`godexByok`,{call:(op,args)=>"
               "e.ipcRenderer.invoke(`godex-byok:rpc`,{op,args})}),"
               "/*GODEX_BYOK_BRIDGE*/typeof window")


def read(p: Path) -> str:
    with io.open(p, encoding="utf-8", newline="") as f:
        return f.read()


def write(p: Path, s: str):
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)


def do_check() -> int:
    t_main = read(MAIN_F)
    ok = "/*GODEX_BYOK_RPC*/" in t_main
    print("main RPC   :", "OK" if ok else "缺失")
    total = 0
    for p in FILES:
        t = read(p)
        n = sum(1 for f, _o, _n, mk in EDITS if f == p and mk in t)
        extra = 1 if (p == PRELOAD_F and "GODEX_BYOK_BRIDGE" in t) else 0
        total += n + extra
        print(f"{p.name:45s} {n + extra} 处标记")
    print(f"[check] 结论: {'已应用' if (ok and total >= len(EDITS) + 1) else '未全部应用'}")
    return 0 if (ok and total >= len(EDITS) + 1) else 1


def do_restore() -> int:
    for p in FILES:
        bak = p.with_suffix(p.suffix + ".godex-bak")
        if bak.exists():
            shutil.copy2(bak, p)
            print("还原", p.name)
        else:
            print("无备份, 跳过", p.name)
    return 0


def do_apply() -> int:
    texts = {p: read(p) for p in FILES}
    planned = []
    for f, old, new, mk in EDITS:
        if mk in texts[f]:
            print(f"  (已应用) {mk}")
            continue
        c = texts[f].count(old)
        if c != 1:
            sys.exit(f"✘ 锚点命中 {c} 处 (应为 1), 拒绝修改: {mk}")
        planned.append((f, old, new, mk))
    pl_dirty = "GODEX_BYOK_BRIDGE" not in texts[PRELOAD_F]
    if pl_dirty and texts[PRELOAD_F].count(PRELOAD_OLD) != 1:
        sys.exit("✘ preload 锚点异常, 拒绝修改")
    main_dirty = "/*GODEX_BYOK_RPC*/" not in texts[MAIN_F]
    if not planned and not pl_dirty and not main_dirty:
        print("全部已应用, 无事可做")
        return 0
    for p in FILES:
        bak = p.with_suffix(p.suffix + ".godex-bak")
        if not bak.exists():
            shutil.copy2(p, bak)
            print("备份 ->", bak.name)
    for f, old, new, mk in planned:
        texts[f] = texts[f].replace(old, new, 1)
        write(f, texts[f])
        print("  ✓", mk)
    if pl_dirty:
        texts[PRELOAD_F] = texts[PRELOAD_F].replace(PRELOAD_OLD, PRELOAD_NEW, 1)
        write(PRELOAD_F, texts[PRELOAD_F])
        print("  ✓ GODEX_BYOK_BRIDGE (preload)")
    if main_dirty:
        with io.open(MAIN_F, "a", encoding="utf-8", newline="") as fp:
            fp.write(MAIN_RPC)
        print("  ✓ GODEX_BYOK_RPC (main 追加)")
    print("\n完成。重启 Godex 生效。")
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv:
        raise SystemExit(do_check())
    if "--restore" in sys.argv:
        raise SystemExit(do_restore())
    raise SystemExit(do_apply())
