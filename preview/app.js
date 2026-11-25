'use strict';
const apps = Object.freeze([
  {id:'probe',title:'動作確認用',note:'入力・画面領域・復帰',url:'fixture.html',glyph:'✓'},
  {id:'tarot',title:'Tarot Draw',note:'公開候補・互換性未確認',url:'https://kinoko34077.github.io/tarot-draw/',iconUrl:'https://kinoko34077.github.io/tarot-draw/favicon.svg',glyph:'✦'},
  {id:'chord',title:'μChordbot',note:'公開候補・互換性未確認',url:'https://kinoko34077.github.io/Micro-Chordbot/',iconUrl:'https://kinoko34077.github.io/Micro-Chordbot/icons/icon-192.svg',glyph:'μ'},
  {id:'warp',title:'Frequency Warp',note:'公開候補・互換性未確認',url:'https://kinoko34077.github.io/frequency-warp-vst/',glyph:'≈'},
  {id:'clock',title:'Standby Display',note:'外部公開候補・互換性未確認',url:'https://standby-display.kinotch.workers.dev/',iconUrl:'https://kinoko34077.github.io/standby-display/icon-192.png',glyph:'◷'}
]);
const home=document.querySelector('#home'),stage=document.querySelector('#stage'),surface=document.querySelector('#surface'),back=document.querySelector('#back');
const menu=document.querySelector('#app-menu'),menuTitle=document.querySelector('#menu-title'),menuNote=document.querySelector('#menu-note');
const openButton=document.querySelector('#menu-open'),shareButton=document.querySelector('#menu-share'),browserLink=document.querySelector('#menu-browser');
const manualShare=document.querySelector('#manual-share'),shareUrl=document.querySelector('#share-url'),feedback=document.querySelector('#feedback');
let sourceButton=null,selected=null,press=null,blockedClick=null,backdropPressed=false;
function appUrl(app){return new URL(app.url,document.baseURI).href;}
function launch(app,button){
  if(!apps.includes(app))return;
  sourceButton=button;
  const frame=document.createElement('iframe');
  frame.title=app.title;frame.setAttribute('sandbox','allow-scripts');frame.referrerPolicy='no-referrer';frame.src=appUrl(app);
  surface.replaceChildren(frame);home.hidden=true;stage.hidden=false;back.focus();
}
function returnHome(){surface.replaceChildren();stage.hidden=true;home.hidden=false;sourceButton?.focus();sourceButton=null;}
function clearPress(){if(press){clearTimeout(press.timer);press=null;}}
function showMenu(app,button){
  if(menu.open)return;
  clearPress();selected={app,button};button.setAttribute('aria-expanded','true');
  menuTitle.textContent=app.title;menuNote.textContent=app.note;browserLink.href=appUrl(app);
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
openButton.addEventListener('click',()=>{if(!selected)return;const {app,button}=selected;closeMenu(false);launch(app,button);});
browserLink.addEventListener('click',()=>closeMenu());
shareButton.addEventListener('click',async()=>{
  if(!selected)return;const current=selected,url=appUrl(current.app);
  if(typeof navigator.share==='function'){
    try{await navigator.share({title:current.app.title,url});if(selected===current&&menu.open)closeMenu();return;}
    catch(e){if(e?.name==='AbortError')return;}
  }
  try{if(!navigator.clipboard?.writeText)throw new Error('unavailable');await navigator.clipboard.writeText(url);if(selected===current&&menu.open){closeMenu();feedback.textContent='リンクをコピーしました';}}
  catch{if(selected===current&&menu.open){manualShare.hidden=false;shareUrl.value=url;shareUrl.focus();shareUrl.select();}}
});
for(const app of apps){
  const button=document.createElement('button');button.type='button';button.className='tile';button.dataset.appId=app.id;
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
}
document.addEventListener('pointermove',e=>{if(press&&press.id===e.pointerId&&Math.hypot(e.clientX-press.x,e.clientY-press.y)>10)clearPress();},{passive:true});
for(const name of ['pointerup','pointercancel'])document.addEventListener(name,e=>{if(press&&press.id===e.pointerId)clearPress();},{passive:true});
window.addEventListener('blur',clearPress);window.addEventListener('scroll',clearPress,{passive:true});
menu.addEventListener('contextmenu',e=>e.preventDefault());
back.addEventListener('click',returnHome);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!stage.hidden)returnHome();});
const mode=document.querySelector('#mode');
mode.textContent=(matchMedia('(display-mode: standalone)').matches||navigator.standalone===true)?'ホーム画面起動モード':'ブラウザ表示モード';
if('serviceWorker' in navigator)navigator.serviceWorker.register('sw.js').catch(()=>{mode.textContent+=' · オフライン準備失敗';});
