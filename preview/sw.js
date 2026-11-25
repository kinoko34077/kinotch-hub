'use strict';
const CACHE='kinotch-hub-preview-v4';
const assets=['./','index.html','style.css','app.js','catalog-runtime.js','fixture.html','manifest.webmanifest','icon.svg'].map(p=>new URL(p,self.registration.scope).href);
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(c=>c.addAll(assets))));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('kinotch-hub-preview-')&&k!==CACHE).map(k=>caches.delete(k))))));
self.addEventListener('fetch',event=>{
 if(event.request.method!=='GET'||!assets.includes(event.request.url))return;
 event.respondWith(fetch(event.request).then(r=>r.ok?r:caches.open(CACHE).then(c=>c.match(event.request)).then(c=>c||r)).catch(()=>caches.open(CACHE).then(c=>c.match(event.request)).then(r=>r||Response.error())));
});
