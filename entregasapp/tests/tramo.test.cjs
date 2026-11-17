// Pruebas de static/js/entregas/tramo.js (spec 09, enmienda del 2026-11-15, RF-09-21, RF-09-23 y RF-09-26).
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const ruta = path.join(__dirname, "../../static/js/entregas/tramo.js");
const tramo = require(ruta);

function alNorte(lat, metros) { return lat + metros / 111195; }

test("formato de la distancia: metros redondeados a 10 bajo 1 km y km con coma desde ahí", () => {
  assert.equal(tramo.formatearDistancia(80), "80 m");
  assert.equal(tramo.formatearDistancia(854), "850 m");
  assert.equal(tramo.formatearDistancia(996), "1,0 km");
  assert.equal(tramo.formatearDistancia(1234), "1,2 km");
  assert.equal(tramo.formatearDistancia(23449), "23,4 km");
});

test("lejos de la parada: recalcula al moverse más de 150 m y con al menos 20 s", () => {
  const anterior = { lat: -36.5, lon: -72.2, t: 0, distancia_m: 1200 };
  assert.equal(tramo.debeRecalcular(null, anterior, 0), true);
  assert.equal(tramo.debeRecalcular(anterior, { lat: alNorte(-36.5, 100), lon: -72.2 }, 25000), false);
  assert.equal(tramo.debeRecalcular(anterior, { lat: alNorte(-36.5, 200), lon: -72.2 }, 15000), false);
  assert.equal(tramo.debeRecalcular(anterior, { lat: alNorte(-36.5, 200), lon: -72.2 }, 20000), true);
});

test("cerca de la parada (tramo menor de 500 m): recalcula a los 30 m y 10 s, para avisar a tiempo", () => {
  const anterior = { lat: -36.5, lon: -72.2, t: 0, distancia_m: 450 };
  assert.equal(tramo.debeRecalcular(anterior, { lat: alNorte(-36.5, 20), lon: -72.2 }, 15000), false);
  assert.equal(tramo.debeRecalcular(anterior, { lat: alNorte(-36.5, 40), lon: -72.2 }, 9000), false);
  assert.equal(tramo.debeRecalcular(anterior, { lat: alNorte(-36.5, 40), lon: -72.2 }, 10000), true);
});

test("tras un cálculo fallido se reintenta pasados 20 s aunque no haya movimiento", () => {
  const fallido = { lat: -36.5, lon: -72.2, t: 0, fallido: true };
  assert.equal(tramo.debeRecalcular(fallido, { lat: -36.5, lon: -72.2 }, 19000), false);
  assert.equal(tramo.debeRecalcular(fallido, { lat: -36.5, lon: -72.2 }, 20000), true);
});

function respuesta(status, cuerpo) {
  return { status, json: () => (cuerpo === undefined ? Promise.reject(new Error("sin json")) : Promise.resolve(cuerpo)) };
}

class ControlFalso {
  constructor() { this.signal = { abortado: false }; }
  abort() { this.signal.abortado = true; }
}

function cliente(fetch, enLinea = true) {
  return tramo.crearCliente({
    fetch, AbortController: ControlFalso, urlTramo: "/entregas/mis/tramo/", urlCercana: "/entregas/mis/cercana/",
    csrf: () => "token", enLinea: () => enLinea,
  });
}

test("el cliente envía a Django la visita y la posición en JSON, con CSRF; nunca a OSRM", async () => {
  const llamadas = [];
  const c = cliente((url, opciones) => {
    llamadas.push({ url, opciones });
    return Promise.resolve(respuesta(200, { intento: 7, numero: 3, distancia_m: 1200, distancia_texto: "1,2 km", geometria: [] }));
  });
  const resultado = await c.pedirTramo(7, { lat: -36.5, lon: -72.2 });
  assert.equal(resultado.ok, true);
  assert.equal(resultado.distancia_texto, "1,2 km");
  assert.equal(llamadas[0].url, "/entregas/mis/tramo/");
  assert.equal(llamadas[0].opciones.method, "POST");
  assert.equal(llamadas[0].opciones.headers["X-CSRFToken"], "token");
  assert.deepEqual(JSON.parse(llamadas[0].opciones.body), { intento: 7, latitud: -36.5, longitud: -72.2 });
  await c.pedirCercana({ lat: -36.5, lon: -72.2 });
  assert.equal(llamadas[1].url, "/entregas/mis/cercana/");
  assert.deepEqual(JSON.parse(llamadas[1].opciones.body), { latitud: -36.5, longitud: -72.2 });
});

test("una respuesta vieja que llega después de una nueva se descarta y la anterior se cancela", async () => {
  const pendientes = [];
  const c = cliente((url, opciones) => new Promise((resolver) => pendientes.push({ resolver, opciones })));
  const primera = c.pedirTramo(1, { lat: 0, lon: 0 });
  const segunda = c.pedirTramo(2, { lat: 0, lon: 0 });
  await new Promise((r) => setImmediate(r));
  assert.equal(pendientes[0].opciones.signal.abortado, true);
  pendientes[1].resolver(respuesta(200, { intento: 2, numero: 2, distancia_m: 10, distancia_texto: "10 m", geometria: [] }));
  pendientes[0].resolver(respuesta(200, { intento: 1, numero: 1, distancia_m: 10, distancia_texto: "10 m", geometria: [] }));
  assert.deepEqual(await primera, { ok: false, descartada: true });
  assert.equal((await segunda).intento, 2);
});

test("sin conexión no envía nada; con la red cortada, OSRM caído o el límite, responde con texto", async () => {
  let llamado = false;
  const desconectado = await cliente(() => { llamado = true; }, false).pedirTramo(1, { lat: 0, lon: 0 });
  assert.equal(llamado, false);
  assert.equal(desconectado.mensaje, "Sin conexión: no se pudo calcular el tramo. Sigue el orden de la lista.");
  const sinCercana = await cliente(() => {}, false).pedirCercana({ lat: 0, lon: 0 });
  assert.equal(sinCercana.mensaje, "Sin conexión: no se pudo calcular la parada más cercana.");
  const corte = await cliente(() => Promise.reject(new TypeError("Failed to fetch"))).pedirTramo(1, { lat: 0, lon: 0 });
  assert.equal(corte.mensaje, tramo.TEXTOS.sinRed);
  const caido = await cliente(() => Promise.resolve(respuesta(503, { error: "No se pudo calcular el tramo: el servidor de rutas no respondió. Sigue el orden de la lista." })))
    .pedirTramo(1, { lat: 0, lon: 0 });
  assert.deepEqual(caido, { ok: false, mensaje: "No se pudo calcular el tramo: el servidor de rutas no respondió. Sigue el orden de la lista.", status: 503 });
  const limite = await cliente(() => Promise.resolve(respuesta(429, { error: "Pediste muchos cálculos seguidos." }))).pedirTramo(1, { lat: 0, lon: 0 });
  assert.equal(limite.status, 429);
  const roto = await cliente(() => Promise.resolve(respuesta(500))).pedirTramo(1, { lat: 0, lon: 0 });
  assert.equal(roto.mensaje, tramo.TEXTOS.fallo);
});

test("el seguimiento pide la posición con el gesto, recalcula según los umbrales y se detiene sin guardar nada", async () => {
  const geo = {
    watchPosition(exito, fallo, opciones) { this.exito = exito; this.fallo = fallo; this.opciones = opciones; return 9; },
    clearWatch(id) { this.limpiado = id; },
  };
  const pedidos = [];
  const avisos = [];
  const reloj = { t: 0 };
  const seguimiento = tramo.crearSeguimiento({
    geo, seguro: true, ahora: () => reloj.t, destino: () => 5,
    cliente: {
      pedirTramo(intento, pos) { pedidos.push([intento, pos]); return Promise.resolve({ ok: true, intento, numero: 2, distancia_m: 2000, distancia_texto: "2,0 km", geometria: [] }); },
      abortar() { avisos.push("abortado"); },
    },
    avisos: { inicio: (t) => avisos.push(t), tramo: (r) => avisos.push(r.distancia_texto), fin: (t) => avisos.push(t), error: (t) => avisos.push(t) },
  });
  assert.equal(seguimiento.iniciar(), true);
  assert.equal(geo.opciones.enableHighAccuracy, true);
  geo.exito({ coords: { latitude: -36.5, longitude: -72.2, accuracy: 12 } });
  await new Promise((r) => setImmediate(r));
  reloj.t = 30000;
  geo.exito({ coords: { latitude: alNorte(-36.5, 100), longitude: -72.2, accuracy: 12 } });
  geo.exito({ coords: { latitude: alNorte(-36.5, 220), longitude: -72.2, accuracy: 12 } });
  await new Promise((r) => setImmediate(r));
  assert.equal(pedidos.length, 2);
  assert.deepEqual(pedidos[0], [5, { lat: -36.5, lon: -72.2 }]);
  seguimiento.detener();
  assert.equal(geo.limpiado, 9);
  assert.equal(seguimiento.posicion(), null);
  assert.deepEqual(avisos, [tramo.TEXTOS.iniciando, "2,0 km", "2,0 km", "abortado", tramo.TEXTOS.detenido]);
});

test("el archivo solo habla con las rutas de Django que recibe; nunca con OSRM ni con sendBeacon", () => {
  const codigo = fs.readFileSync(ruta, "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  assert.doesNotMatch(codigo, /XMLHttpRequest|sendBeacon|WebSocket|localStorage|sessionStorage|127\.0\.0\.1|osrm/i);
});
