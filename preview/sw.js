'use strict';
const CACHE='kinotch-hub-preview-v8';
const assets=['./','index.html','style.css','app.js','catalog-runtime.js','fixture.html','manifest.webmanifest','icon.svg'].map(p=>new URL(p,self.registration.scope).href);
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(c=>c.addAll(assets))));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('kinotch-hub-preview-')&&k!==CACHE).map(k=>caches.delete(k))))));
self.addEventListener('fetch',event=>{
 const url=new URL(event.request.url);url.hash='';
 if(event.request.method!=='GET'||!assets.includes(url.href))return;
 event.respondWith(fetch(event.request).then(r=>r.ok?r:caches.open(CACHE).then(c=>c.match(url.href)).then(c=>c||r)).catch(()=>caches.open(CACHE).then(c=>c.match(url.href)).then(r=>r||Response.error())));
});
