const CACHE = "circa-shell-v2";
const SHELL = ["/static/offline.html", "/static/css/app.css", "/static/js/app.js?v=2", "/static/js/api.js", "/static/js/translations.js", "/static/icons/icon.svg"];

self.addEventListener("install", event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL))));
self.addEventListener("activate", event => event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key))))));
self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  if (event.request.mode === "navigate") {
    event.respondWith(fetch(event.request).catch(() => caches.match("/static/offline.html")));
    return;
  }
  if (url.pathname.startsWith("/static/")) event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request)));
});
