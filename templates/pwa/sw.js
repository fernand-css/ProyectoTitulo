// Este paso solo habilita el registro. La estrategia sin conexión llega en el spec 11.
self.addEventListener("install", () => {
  self.skipWaiting();
});
self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});
