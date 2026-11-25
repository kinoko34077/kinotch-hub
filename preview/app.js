'use strict';
const diagnostic=location.hash==='#fixture';
const initialApps=()=>diagnostic?[CatalogRuntime.fixture]:[];
let apps=initialApps(),snapshot=null,refreshing=false,lastRefresh=0,activeApp=null;
const home=document.querySelector('#home'),stage=document.querySelector('#stage'),surface=document.querySelector('#surface'),back=document.querySelector('#back');
const menu=document.querySelector('#app-menu'),menuTitle=document.querySelector('#menu-title'),menuNote=document.querySelector('#menu-note');
const openButton=document.querySelector('#menu-open'),shareButton=document.querySelector('#menu-share'),browserLink=document.querySelector('#menu-browser');
const manualShare=document.querySelector('#manual-share'),shareUrl=document.querySelector('#share-url'),feedback=document.querySelector('#feedback');
let sourceButton=null,selected=null,press=null,blockedClick=null,backdropPressed=false;
function eligible(app){return apps.includes(app);}
const external=document.querySelector('#stage-browser'),retry=document.querySelector('#stage-retry');
function loadFrame(app){
  const frame=document.createElement('iframe');
  frame.title=app.title;frame.setAttribute('sandbox','allow-scripts');frame.referrerPolicy='no-referrer';frame.src=appUrl(app);
  surface.replaceChildren(frame);
}
function appUrl(app){return new URL(app.url,document.baseURI).href;}
function launch(app,button){
  if(!eligible(app))return;
  sourceButton=button;activeApp=app;
  external.href=appUrl(app);external.hidden=app.id==='probe';retry.hidden=app.id==='probe';
  loadFrame(app);home.hidden=true;stage.hidden=false;back.focus();
}
function returnHome(){surface.replaceChildren();stage.hidden=true;home.hidden=false;const id=sourceButton?.dataset.appId;activeApp=null;external.removeAttribute('href');[...document.querySelectorAll('#apps button')].find(b=>b.dataset.appId===id)?.focus();sourceButton=null;}
retry.addEventListener('click',()=>{if(activeApp&&apps.some(a=>a.id===activeApp.id&&a.url===activeApp.url))loadFrame(activeApp);});
external.addEventListener('click',e=>{if(!activeApp||!apps.some(a=>a.id===activeApp.id&&a.url===activeApp.url))e.preventDefault();});
function clearPress(){if(press){clearTimeout(press.timer);press=null;}}
function showMenu(app,button){
  if(menu.open||!eligible(app))return;
  clearPress();selected={app,button};button.setAttribute('aria-expanded','true');
  menuTitle.textContent=app.title;menuNote.textContent=app.note;browserLink.href=appUrl(app);openButton.hidden=false;
  manualShare.hidden=true;feedback.textContent='';backdropPressed=false;
  menu.showModal();
  const r=button.getBoundingClientRect(), m=menu.getBoundingClientRect(),w=window.innerWidth,h=window.innerHeight;
  menu.style.left=Math.max(12,Math.min(r.left+r.width/2-m.width/2,w-m.width-12))+'px';
  menu.style.top=Math.max(12,Math.min(r.bottom+m.height+8<=h-12?r.bottom+8:r.top-m.height-8,h-m.height-12))+'px';
  openButton.focus();
}
function closeMenu(restoreFocus=true){
  const old=selected;selected=null;
  old?.button.setAttribute('aria-expanded','false');
  if(menu.open)menu.close();
  if(restoreFocus&&!home.hidden)old?.button.focus();
}
menu.addEventListener('cancel',e=>{e.preventDefault();closeMenu();});
menu.addEventListener('close',()=>{if(!menu.open&&selected)closeMenu();});
menu.addEventListener('pointerdown',e=>{backdropPressed=e.target===menu;});
menu.addEventListener('click',e=>{if(e.target===menu&&backdropPressed)closeMenu();backdropPressed=false;});
document.querySelector('#menu-cancel').addEventListener('click',()=>closeMenu());
openButton.addEventListener('click',()=>{if(!selected||!eligible(selected.app))return;const {app,button}=selected;closeMenu(false);launch(app,button);});
browserLink.addEventListener('click',e=>{if(!selected||!eligible(selected.app)){e.preventDefault();return;}closeMenu();});
shareButton.addEventListener('click',async()=>{
  if(!selected||!eligible(selected.app)){return;}const current=selected,url=appUrl(current.app);
  if(typeof navigator.share==='function'){
    try{await navigator.share({title:current.app.title,url});if(selected===current&&menu.open)closeMenu();return;}
    catch(e){if(e?.name==='AbortError')return;}
  }
  try{if(!navigator.clipboard?.writeText)throw new Error('unavailable');await navigator.clipboard.writeText(url);if(selected===current&&menu.open){closeMenu();feedback.textContent='リンクをコピーしました';}}
  catch{if(selected===current&&menu.open){manualShare.hidden=false;shareUrl.value=url;shareUrl.focus();shareUrl.select();}}
});
function renderApps(){
  clearPress();blockedClick=null;document.querySelector('#apps').replaceChildren();
for(const app of apps){
  const button=document.createElement('button');button.type='button';button.className='tile';button.dataset.appId=app.id; if(app.alias)button.dataset.alias=app.alias;
  button.setAttribute('aria-haspopup','dialog');button.setAttribute('aria-expanded','false');button.setAttribute('aria-describedby','gesture-hint');
  const icon=document.createElement('span');icon.className='app-icon';icon.setAttribute('aria-hidden','true');
  const glyph=document.createElement('span');glyph.className='glyph';glyph.textContent=app.glyph;icon.append(glyph);
  if(app.iconUrl){const img=document.createElement('img');img.alt='';img.draggable=false;img.referrerPolicy='no-referrer';img.hidden=true;
    img.addEventListener('load',()=>{img.hidden=false;glyph.hidden=true;});
    img.addEventListener('error',()=>{img.hidden=true;glyph.hidden=false;});img.src=app.iconUrl;icon.append(img);}
  const title=document.createElement('span');title.className='app-name';title.textContent=app.title;button.append(icon,title);
  button.addEventListener('pointerdown',e=>{
    blockedClick=null;clearPress();
    if(!e.isPrimary||e.button!==0||e.pointerType==='mouse')return;
    const p={id:e.pointerId,x:e.clientX,y:e.clientY,button,timer:0};
    p.timer=setTimeout(()=>{if(press!==p)return;blockedClick=button;showMenu(app,button);},500);press=p;
  });
  button.addEventListener('contextmenu',e=>{e.preventDefault();clearPress();blockedClick=button;showMenu(app,button);});
  button.addEventListener('keydown',e=>{if(e.key==='ContextMenu'||(e.shiftKey&&e.key==='F10')){e.preventDefault();showMenu(app,button);}});
  button.addEventListener('click',e=>{if(menu.open||(blockedClick===button&&e.detail!==0)){blockedClick=null;return;}launch(app,button);});
  document.querySelector('#apps').append(button);
}}
const catalogStatus=document.querySelector('#catalog-status');
function renderRepositories(data){
  const panel=document.querySelector('#repo-panel'),list=document.querySelector('#repo-list'),label=document.querySelector('#repo-summary');
  const rows=[...data.repositories].sort((a,b)=>a.fullName.localeCompare(b.fullName,'ja'));
  const focused=document.activeElement?.dataset?.repoId;
  const fragment=document.createDocumentFragment();
  for(const repo of rows){
    const li=document.createElement('li'),link=document.createElement('a');
    link.dataset.repoId=repo.id;link.href='https://github.com/'+repo.fullName;
    link.target='_blank';link.rel='noopener noreferrer';link.textContent=repo.fullName.split('/')[1];
    li.append(link);fragment.append(li);
  }
  list.replaceChildren(fragment);label.textContent='公開リポジトリ ('+rows.length+')';panel.hidden=false;
  if(focused)[...list.querySelectorAll('a')].find(a=>a.dataset.repoId===focused)?.focus();
}
async function refreshCatalog(){
  if(refreshing)return;refreshing=true;lastRefresh=Date.now();
  try{
    const next=await CatalogRuntime.read();
    if(!next){catalogStatus.textContent=snapshot?'取得失敗 · 保存済み一覧 · 更新 '+new Date(snapshot.generated).toLocaleString('ja-JP'):'公開カタログを取得できません';document.querySelector('#catalog-retry').hidden=false;return;}
    document.querySelector('#catalog-retry').hidden=next.source!=='cached';
    if(!snapshot||next.generated>snapshot.generated){closeMenu();snapshot=next;apps=[...initialApps(),...next.items];renderApps();renderRepositories(next.data);}
    const active=snapshot;const age=Date.now()-active.generated;
    catalogStatus.textContent=(next.source==='cached'?'保存済み一覧 · ':'')+(Date.now()>=active.expires||age>30*3600000?'更新遅延 · ':'')+'更新 '+new Date(active.generated).toLocaleString('ja-JP')+' · '+active.items.length+'件';
    if(activeApp&&!apps.some(a=>a.id===activeApp.id&&a.url===activeApp.url)){external.hidden=true;retry.hidden=true;}
  }finally{refreshing=false;}
}
renderApps();refreshCatalog();
document.addEventListener('visibilitychange',()=>{if(!document.hidden){if(Date.now()-lastRefresh>300000)refreshCatalog();}});
document.addEventListener('pointermove',e=>{if(press&&press.id===e.pointerId&&Math.hypot(e.clientX-press.x,e.clientY-press.y)>10)clearPress();},{passive:true});
for(const name of ['pointerup','pointercancel'])document.addEventListener(name,e=>{if(press&&press.id===e.pointerId)clearPress();},{passive:true});
window.addEventListener('blur',clearPress);window.addEventListener('scroll',clearPress,{passive:true});
menu.addEventListener('contextmenu',e=>e.preventDefault());
back.addEventListener('click',returnHome);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!stage.hidden)returnHome();});
if('serviceWorker' in navigator)navigator.serviceWorker.register('sw.js').catch(()=>{feedback.textContent='オフライン準備に失敗しました';});
document.querySelector('#catalog-retry').addEventListener('click',refreshCatalog);
window.addEventListener('online',refreshCatalog);
