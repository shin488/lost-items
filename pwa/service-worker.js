const CACHE = "lost-items-v1"
const PRECACHE = [
  ".",
  "./index.html",
  "./flutter.js",
  "./flutter_bootstrap.js",
  "./main.dart.js",
  "./python.js",
  "./python-worker.js",
  "./manifest.json",
  "./favicon.png",
  "./icons/Icon-192.png",
  "./icons/Icon-512.png",
]

self.addEventListener("install", (e) => {
  self.skipWaiting()
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(PRECACHE).catch(() => {})),
  )
})

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))),
    ),
  )
})

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return

  if (e.request.mode === "navigate") {
    e.respondWith(
      fetch(e.request).catch(() => caches.match(e.request)),
    )
    return
  }

  e.respondWith(
    caches.match(e.request).then((cached) => {
      const fetchPromise = fetch(e.request)
        .then((res) => {
          if (res && res.status === 200) {
            const clone = res.clone()
            caches.open(CACHE).then((c) => c.put(e.request, clone))
          }
          return res
        })
        .catch(() => cached)
      return cached || fetchPromise
    }),
  )
})
