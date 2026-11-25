'use strict';
const apps = Object.freeze([
  {id:'probe',title:'動作確認用',note:'入力・画面領域・復帰',url:'fixture.html'},
  {id:'tarot',title:'Tarot Draw',note:'公開アプリ候補・互換性未確認',url:'https://kinoko34077.github.io/tarot-draw/'},
  {id:'chord',title:'μChordbot',note:'公開アプリ候補・互換性未確認',url:'https://kinoko34077.github.io/Micro-Chordbot/'},
  {id:'warp',title:'Frequency Warp',note:'公開アプリ候補・互換性未確認',url:'https://kinoko34077.github.io/frequency-warp-vst/'},
  {id:'clock',title:'Standby Display',note:'外部公開候補・互換性未確認',url:'https://standby-display.kinotch.workers.dev/'}
]);
const home=document.querySelector('#home'),stage=document.querySelector('#stage'),surface=document.querySelector('#surface'),back=document.querySelector('#back');
let sourceButton=null;
function launch(app,button){
  if(!apps.includes(app))return;
  sourceButton=button;
  const frame=document.createElement('iframe');
  frame.title=app.title;
  frame.setAttribute('sandbox','allow-scripts');
  frame.referrerPolicy='no-referrer';
  frame.src=new URL(app.url,document.baseURI).href;
  surface.replaceChildren(frame);home.hidden=true;stage.hidden=false;back.focus();
}
function returnHome(){surface.replaceChildren();stage.hidden=true;home.hidden=false;sourceButton?.focus();sourceButton=null;}
for(const app of apps){const button=document.createElement('button');button.type='button';button.className='tile';button.dataset.appId=app.id;
const title=document.createElement('strong'),note=document.createElement('small');title.textContent=app.title;note.textContent=app.note;button.append(title,note);button.addEventListener('click',()=>launch(app,button));document.querySelector('#apps').append(button);}
back.addEventListener('click',returnHome);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!stage.hidden)returnHome();});
const mode=document.querySelector('#mode');
mode.textContent=(matchMedia('(display-mode: standalone)').matches||navigator.standalone===true)?'ホーム画面起動モード':'ブラウザ表示モード';
if('serviceWorker' in navigator)navigator.serviceWorker.register('sw.js').catch(()=>{mode.textContent+=' · オフライン準備失敗';});
