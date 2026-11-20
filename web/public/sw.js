// The service worker: shows a notification for every push the worker sends
// (a new killshot -- see killshot/push.py), and opens the game when it's
// tapped. Served as-is at /sw.js; not bundled, so it stays plain JS.

self.addEventListener("push", (event) => {
  let data = { title: "Killshot", body: "", url: "/" };
  try {
    data = { ...data, ...event.data.json() };
  } catch {
    // No JSON payload (or no payload at all): fall back to the defaults above.
  }
  event.waitUntil(self.registration.showNotification(data.title, { body: data.body, data: { url: data.url } }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url ?? "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window" }).then((clients) => {
      const open = clients.find((c) => new URL(c.url).pathname === url);
      return open ? open.focus() : self.clients.openWindow(url);
    }),
  );
});
