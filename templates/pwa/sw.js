// Service worker de la PWA (spec 11, RF-11-01, RF-11-04 y RF-11-06). Plantilla de Django: la vista pone la lista de
// estáticos con su versión (?v=), la URL de la página sin conexión y la de sincronización, ya como JSON.
//
// - Caché versionada SOLO con estáticos (estilos, scripts, fuentes e íconos) y la página sin conexión, que no lleva
//   datos. Nunca guarda páginas con datos, respuestas JSON, fotos ni POST: esas respuestas siguen con no-store.
// - Navegaciones del reparto («/» y «/entregas/…»): red primero; si la red falla, la página sin conexión.
// - Todo lo demás (JSON, POST, fotos, /turnos/, el tótem, la sala y su WebSocket) pasa sin intervenir.
// - Background Sync («cesfam-registros»): envía la cola con la misma función de la página (sincronizar.js).
"use strict";

const CACHE = "cesfam-{{ version }}";
const PREFIJO = "cesfam-";
const ESTATICOS = {{ estaticos|safe }};
const SIN_CONEXION = {{ sin_conexion_url|safe }};
const SINCRONIZAR = {{ sincronizar_url|safe }};
const ETIQUETA_SYNC = "cesfam-registros";

importScripts({{ almacen_js|safe }}, {{ sincronizar_js|safe }});

function esNavegacionDelReparto(url) {
  return url.pathname === "/" || url.pathname.startsWith("/entregas/");
}

// Respaldo si la página sin conexión aún no está guardada (nunca se abrió «Mis entregas» con señal): solo texto.
function respaldo() {
  const html = "<!doctype html><html lang=\"es-CL\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" " +
    "content=\"width=device-width, initial-scale=1\"><title>Sin conexión</title></head><body style=\"font: 1.25rem/1.5 " +
    "system-ui, sans-serif; margin: 1.5rem; color: #1a1a1a; background: #fff\"><h1>Sin conexión</h1><p>No hay una " +
    "ruta guardada para hoy. Ábrela con señal.</p></body></html>";
  return new Response(html, { headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
}

// Guarda la página sin conexión con la sesión del encargado. Solo una respuesta 200 propia, sin redirecciones.
async function guardarSinConexion() {
  const respuesta = await fetch(SIN_CONEXION, { credentials: "same-origin", redirect: "manual", cache: "no-store" });
  if (!respuesta.ok || respuesta.type !== "basic" || respuesta.redirected) return false;
  const cache = await caches.open(CACHE);
  await cache.put(SIN_CONEXION, respuesta);
  return true;
}

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ESTATICOS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const nombres = await caches.keys();
    await Promise.all(nombres.filter((nombre) => nombre.startsWith(PREFIJO) && nombre !== CACHE)
      .map((nombre) => caches.delete(nombre)));
    await self.clients.claim();
    try { await guardarSinConexion(); } catch (error) { /* sin sesión o sin red: se guarda al abrir «Mis entregas» */ }
  })());
});

self.addEventListener("fetch", (event) => {
  const solicitud = event.request;
  if (solicitud.method !== "GET") return;
  const url = new URL(solicitud.url);
  if (url.origin !== self.location.origin) return;
  if (ESTATICOS.includes(url.pathname + url.search)) {
    event.respondWith(caches.match(solicitud, { cacheName: CACHE }).then((guardada) => guardada || fetch(solicitud)));
    return;
  }
  if (solicitud.mode === "navigate" && esNavegacionDelReparto(url)) {
    event.respondWith(fetch(solicitud).catch(async () => {
      const guardada = await caches.match(SIN_CONEXION, { cacheName: CACHE });
      return guardada || respaldo();
    }));
  }
});

self.addEventListener("message", (event) => {
  const datos = event.data || {};
  if (datos.tipo === "guardar-sin-conexion") {
    event.waitUntil(guardarSinConexion().catch(() => false));
  }
});

self.addEventListener("sync", (event) => {
  if (event.tag !== ETIQUETA_SYNC) return;
  const almacen = self.EntregasAlmacen.delNavegador();
  const sincronizador = self.EntregasSincronizar.crearSincronizador({
    almacen,
    url: SINCRONIZAR,
    fetch: self.fetch.bind(self),
    // Solo la cuenta con sesión en este navegador: la cola de otra cuenta espera a que esa cuenta vuelva a entrar.
    obtenerCuenta: () => almacen.leerMeta("cuenta_activa"),
    obtenerToken: () => almacen.leerMeta("csrf"),
  });
  event.waitUntil(sincronizador.enviar().then((resultado) => {
    if (["sin_red", "servidor", "limite"].includes(resultado.estado)) {
      throw new Error("Se reintentará el envío.");  // el navegador vuelve a disparar el evento
    }
  }));
});
