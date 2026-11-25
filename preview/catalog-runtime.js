'use strict';
// Hub catalog admission, independent of rendering and launch permission.
const CatalogRuntime=(()=>{
  const DAY=86400000, OWNER='kinoko34077', PAGES='https://kinoko34077.github.io', WORKER='https://standby-display.kinotch.workers.dev/';
  const key='kinotch-hub.catalog.v1';
  // Preview-only launch policy, not a list of available apps.
  const previewPolicy=Object.freeze({
    'repo:1408820750:main':{url:PAGES+'/tarot-draw/',alias:'tarot',glyph:'✦'},
    'repo:1235346464:main':{url:PAGES+'/Micro-Chordbot/',alias:'chord',glyph:'μ'},
    'repo:1416615773:main':{url:PAGES+'/frequency-warp-vst/',alias:'warp',glyph:'≈'},
    'repo:969335914:main':{url:WORKER,alias:'clock',glyph:'◷'}
  });
  const fixture=Object.freeze({id:'probe',title:'動作確認用',note:'入力・画面領域・復帰',url:'fixture.html',glyph:'✓',embed:true,expires:Infinity});
  function time(value){
    if(typeof value!=='string'||!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(value))throw Error('invalid time');
    const ms=Date.parse(value);if(!Number.isFinite(ms)||new Date(ms).toISOString().replace('.000Z','Z')!==value)throw Error('invalid time');return ms;
  }
  function scoped(value,base){
    if(typeof value!=='string'||!/^https:\/\/[A-Za-z0-9.-]+\/[A-Za-z0-9._/-]*$/.test(value)||value.length>1024)return false;
    try{const u=new URL(value),b=new URL(base);return u.href===value&&u.origin===b.origin&&u.pathname.startsWith(b.pathname)&&!u.pathname.includes('//')&&!u.pathname.split('/').some(s=>s==='.'||s==='..');}catch{return false;}
  }
  function admit(data,now=Date.now()){
    if(!data||data.schemaVersion!==1||!Array.isArray(data.repositories)||!Array.isArray(data.applications)||data.repositories.length>1000||data.applications.length>4000)throw Error('invalid catalog');
    const generated=time(data.generatedAt),expires=time(data.validUntil);
    if(generated>now+300000||expires<=generated||expires-generated>3*DAY||expires<=now)throw Error('expired or invalid catalog');
    const repos=new Map(),names=new Set(),ids=new Set(),urls=new Set();
    for(const r of data.repositories){
      if(!r||typeof r.id!=='string'||! /^[1-9][0-9]*$/.test(r.id)||typeof r.fullName!=='string'||!/^kinoko34077\/[A-Za-z0-9._-]+$/.test(r.fullName)||['.','..'].includes(r.fullName.split('/')[1])||r.visibility!=='public'||typeof r.archived!=='boolean'||time(r.observedAt)>generated||repos.has(r.id)||names.has(r.fullName.toLowerCase()))throw Error('invalid repository');
      repos.set(r.id,r);names.add(r.fullName.toLowerCase());
    }
    const items=[];
    for(const a of data.applications){
      const r=a&&repos.get(a.repositoryId);
      if(!r||r.archived||r.fullName.toLowerCase()===OWNER+'/kinotch-hub'||typeof a.id!=='string'||!/^repo:[1-9][0-9]*:[a-z0-9][a-z0-9-]*$/.test(a.id)||!a.id.startsWith('repo:'+r.id+':')||typeof a.title!=='string'||!a.title.trim()||a.title.length>100||!['application','preview','demo','documentation'].includes(a.kind)||!a.publication||time(a.publication.observedAt)>generated||ids.has(a.id)||urls.has(a.canonicalUrl))throw Error('invalid application');
      const root=PAGES+'/'+r.fullName.split('/')[1]+'/',worker=r.id==='969335914'&&a.canonicalUrl===WORKER;
      if(!(worker?a.publication.basis==='public-deployment':scoped(a.canonicalUrl,root)&&a.publication.basis==='github-pages'))throw Error('invalid app URL');
      if(a.iconUrl!==undefined&&!scoped(a.iconUrl,root))throw Error('invalid icon URL');
      ids.add(a.id);urls.add(a.canonicalUrl);
      if(a.kind==='documentation')continue;
      const p=previewPolicy[a.id],embed=!!p&&p.url===a.canonicalUrl;
      items.push(Object.freeze({id:a.id,title:a.title,url:a.canonicalUrl,iconUrl:a.iconUrl,glyph:p?.glyph??Array.from(a.title.trim())[0],alias:p?.alias,embed,expires,
        note:embed?'Hub内起動・互換性検証中':'Hub内起動未検証・メニューからブラウザで開く'}));
    }
    return {data,generated,expires,items:items.sort((a,b)=>a.title.localeCompare(b.title,'ja'))};
  }
  function cached(){
    try{const raw=localStorage.getItem(key);return raw?admit(JSON.parse(raw)):null;}catch{return null;}
  }
  async function read(){
    const old=cached(),controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);
    try{
      const response=await fetch('catalog.json',{cache:'no-store',signal:controller.signal});
      if(!response.ok)throw Error('unavailable');
      const raw=await response.text();if(raw.length>2000000)throw Error('oversized');
      const current=admit(JSON.parse(raw));
      if(old&&old.generated>current.generated)return {...old,source:'cached'};
      try{localStorage.setItem(key,JSON.stringify(current.data));}catch{}
      return {...current,source:'network'};
    }catch{return old&&Date.now()<old.expires?{...old,source:'cached'}:null;}
    finally{clearTimeout(timer);}
  }
  return Object.freeze({fixture,admit,read,key});
})();
