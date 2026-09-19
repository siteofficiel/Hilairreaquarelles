/* Hilaire Legentil — service worker : notifications des nouvelles aquarelles. */
self.addEventListener("install", function (e) { self.skipWaiting(); });
self.addEventListener("activate", function (e) { e.waitUntil(self.clients.claim()); });

self.addEventListener("push", function (e) {
  var d = {};
  try { d = e.data ? e.data.json() : {}; } catch (err) { d = {}; }
  e.waitUntil(self.registration.showNotification(
    d.title || "Hilaire Legentil",
    {
      body: d.body || "Une nouvelle aquarelle est en ligne.",
      icon: "/static/img/notif-icon.png",
      badge: "/static/img/notif-icon.png",
      tag: d.tag || "hl-galerie",
      data: { url: d.url || "/galerie" }
    }
  ));
});

self.addEventListener("notificationclick", function (e) {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true })
    .then(function (list) {
      var url = (e.notification.data && e.notification.data.url) || "/galerie";
      for (var i = 0; i < list.length; i++) {
        var c = list[i];
        if ("navigate" in c) { c.navigate(url); return c.focus(); }
      }
      return self.clients.openWindow(url);
    }));
});
