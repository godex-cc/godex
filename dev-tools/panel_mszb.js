function GODEX_dispName(n){const s=String(n||"").replace(/\s*[（(][^）)]*[)）]\s*$/,"").trim();return s||n||"";}
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
