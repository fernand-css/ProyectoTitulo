// Spec 09, enmienda del 2026-11-15 (RF-09-23): «Ir a esta parada» por camino, con geolocalización y servidor
// simulados. La distancia es la del tramo por camino que responde Django; ya no hay línea recta ni rumbo.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const ruta = path.join(__dirname, "../../static/js/entregas/ir_a.js");
const guia = require(ruta);
const tramo = require(path.join(__dirname, "../../static/js/entregas/tramo.js"));

const DESTINO = { intento: 41, numero: 3 };

function boton() {
  return { disabled: false, manejadores: {}, addEventListener(evento, funcion) { this.manejadores[evento] = funcion; },
    click() { this.manejadores.click(); } };
}

const esperar = () => new Promise((r) => setImmediate(r));

function preparar({ seguro = true, sinGeo = false, respuestas = [] } = {}) {
  const llamadas = { observar: [], limpiar: [], mapa: [], pedidos: [] };
  let exito;
  let error;
  const geo = {
    watchPosition(alExito, alError, opciones) { exito = alExito; error = alError; llamadas.observar.push(opciones); return 77; },
    clearWatch(id) { llamadas.limpiar.push(id); },
  };
  const reloj = { t: 0 };
  const cliente = {
    pedirTramo(intento, pos) {
      llamadas.pedidos.push({ intento, pos });
      return Promise.resolve(respuestas.length ? respuestas.shift() : { ok: false, mensaje: tramo.TEXTOS.fallo });
    },
    abortar() {},
  };
  const ventana = { manejadores: {}, addEventListener(evento, funcion) { this.manejadores[evento] = funcion; } };
  const documento = { visibilityState: "visible", manejadores: {}, addEventListener(evento, funcion) { this.manejadores[evento] = funcion; } };
  const elementos = { estado: { textContent: "" }, anuncio: { textContent: "" }, iniciar: boton(), leer: boton(), detener: boton() };
  const mapa = {
    actualizar(lat, lon, precision) { llamadas.mapa.push(["posicion", lat, lon, precision]); },
    dibujarTramo(geometria) { llamadas.mapa.push(["tramo", geometria.length]); },
    limpiar() { llamadas.mapa.push(["limpiar"]); },
    limpiarTramo() { llamadas.mapa.push(["limpiarTramo"]); },
  };
  const instancia = guia.crearGuia({
    destino: DESTINO, ventana, documento, elementos, mapa,
    crearSeguimiento: (op) => tramo.crearSeguimiento(Object.assign(op, { geo: sinGeo ? null : geo, seguro, cliente, ahora: () => reloj.t })),
  });
  return {
    instancia, elementos, llamadas, ventana, documento, reloj,
    posicion: (lat, lon, precision) => exito({ coords: { latitude: lat, longitude: lon, accuracy: precision } }),
    fallar: (code) => error({ code }),
  };
}

const tramoDe = (metros) => ({ ok: true, intento: 41, numero: 3, distancia_m: metros, distancia_texto: tramo.formatearDistancia(metros),
  geometria: [[-36.5, -72.2], [-36.49, -72.21]] });

test("los textos dicen la distancia por camino, sin rumbo ni línea recta", () => {
  assert.equal(guia.texto(3, 850), "La parada 3 está a 850 m por camino.");
  assert.equal(guia.texto(3, 1234), "La parada 3 está a 1,2 km por camino.");
  assert.equal(guia.texto(3, 80), "Estás a menos de 100 m por camino de la parada 3.");
  assert.equal(guia.rumbo, undefined);
  assert.equal(guia.distanciaM, undefined);
});

test("mostrar mi posición pide el tramo a Django, lo dibuja y deja «Leer distancia» con el texto por camino", async () => {
  const p = preparar({ respuestas: [tramoDe(1234)] });
  assert.equal(p.elementos.leer.disabled, true);
  p.elementos.iniciar.click();
  assert.equal(p.llamadas.observar.length, 1);
  assert.equal(p.llamadas.observar[0].enableHighAccuracy, true);
  assert.equal(p.elementos.iniciar.disabled, true);
  assert.equal(p.elementos.leer.disabled, false);
  assert.equal(p.elementos.anuncio.textContent.trim(), tramo.TEXTOS.iniciando);
  p.posicion(-36.51, -72.21, 14);
  await esperar();
  assert.deepEqual(p.llamadas.pedidos, [{ intento: 41, pos: { lat: -36.51, lon: -72.21 } }]);
  assert.deepEqual(p.llamadas.mapa, [["posicion", -36.51, -72.21, 14], ["tramo", 2]]);
  assert.equal(p.elementos.estado.textContent, "La parada 3 está a 1,2 km por camino.");
  p.elementos.leer.click();
  assert.equal(p.elementos.anuncio.textContent.trim(), "La parada 3 está a 1,2 km por camino.");
});

test("avisa una vez al quedar a menos de 100 m por camino", async () => {
  const p = preparar({ respuestas: [tramoDe(450), tramoDe(80), tramoDe(60)] });
  p.elementos.iniciar.click();
  p.posicion(-36.5, -72.2, 5);
  await esperar();
  p.reloj.t = 11000;
  p.posicion(-36.5 + 40 / 111195, -72.2, 5); // cerca: recalcula al moverse 30 m con 10 s
  await esperar();
  assert.equal(p.elementos.anuncio.textContent.trim(), "Estás a menos de 100 m por camino de la parada 3.");
  p.elementos.anuncio.textContent = "";
  p.reloj.t = 22000;
  p.posicion(-36.5 + 80 / 111195, -72.2, 5);
  await esperar();
  assert.equal(p.llamadas.pedidos.length, 3);
  assert.equal(p.elementos.anuncio.textContent, ""); // no repite el aviso
});

test("sin OSRM, sin señal, sin permiso, sin posición o sin HTTPS: texto sin distancia", async () => {
  const caido = preparar({ respuestas: [{ ok: false, mensaje: "No se pudo calcular el tramo: el servidor de rutas no respondió. Sigue el orden de la lista." }] });
  caido.elementos.iniciar.click();
  caido.posicion(-36.5, -72.2, 5);
  await esperar();
  assert.match(caido.elementos.estado.textContent, /servidor de rutas no respondió/);
  assert.doesNotMatch(caido.elementos.estado.textContent, /\d+ (m|km)\b/);
  assert.deepEqual(caido.llamadas.mapa.at(-1), ["limpiarTramo"]);
  caido.elementos.leer.click();
  assert.equal(caido.elementos.anuncio.textContent.trim(), guia.TEXTOS.sinDatos);
  const sinRed = preparar({ respuestas: [{ ok: false, mensaje: tramo.TEXTOS.sinRed }] });
  sinRed.elementos.iniciar.click();
  sinRed.posicion(-36.5, -72.2, 5);
  await esperar();
  assert.equal(sinRed.elementos.estado.textContent, "Sin conexión: no se pudo calcular el tramo. Sigue el orden de la lista.");
  const denegado = preparar();
  denegado.elementos.iniciar.click();
  denegado.fallar(1);
  assert.equal(denegado.elementos.estado.textContent, tramo.TEXTOS.sinPermiso);
  assert.deepEqual(denegado.llamadas.limpiar, [77]);
  assert.equal(denegado.elementos.iniciar.disabled, false);
  const sinPosicion = preparar();
  sinPosicion.elementos.iniciar.click();
  sinPosicion.fallar(2);
  assert.equal(sinPosicion.elementos.estado.textContent, tramo.TEXTOS.sinPosicion);
  const inseguro = preparar({ seguro: false });
  inseguro.elementos.iniciar.click();
  assert.equal(inseguro.llamadas.observar.length, 0);
  assert.equal(inseguro.elementos.estado.textContent, tramo.TEXTOS.sinContexto);
});

test("«Detener» o salir de la página terminan el seguimiento y borran el tramo", async () => {
  const p = preparar({ respuestas: [tramoDe(900)] });
  p.elementos.iniciar.click();
  p.posicion(-36.5, -72.2, 5);
  await esperar();
  p.elementos.detener.click();
  assert.deepEqual(p.llamadas.limpiar, [77]);
  assert.deepEqual(p.llamadas.mapa.at(-1), ["limpiar"]);
  assert.equal(p.elementos.estado.textContent, tramo.TEXTOS.detenido);
  const salir = preparar();
  salir.elementos.iniciar.click();
  salir.ventana.manejadores.pagehide();
  assert.deepEqual(salir.llamadas.limpiar, [77]);
});

// Corrección del 2026-11-16: cambiar de pestaña o minimizar no borra el tramo ni pide otra vez la posición.
test("ocultar la página pausa el GPS sin borrar el tramo y al volver sigue sola", async () => {
  const p = preparar({ respuestas: [tramoDe(900)] });
  p.elementos.iniciar.click();
  p.posicion(-36.5, -72.2, 5);
  await esperar();
  const dibujos = p.llamadas.mapa.length;
  p.documento.visibilityState = "hidden";
  p.documento.manejadores.visibilitychange();
  assert.deepEqual(p.llamadas.limpiar, [77]); // suelta el GPS mientras está oculta
  assert.equal(p.llamadas.mapa.length, dibujos); // sin «limpiar»: el tramo y la posición siguen dibujados
  assert.equal(p.elementos.estado.textContent, "La parada 3 está a 900 m por camino.");
  assert.equal(p.elementos.detener.disabled, false);
  assert.equal(p.instancia.siguiendo(), true);
  p.documento.visibilityState = "visible";
  p.documento.manejadores.visibilitychange();
  assert.equal(p.llamadas.observar.length, 2); // vuelve a seguir sin otro gesto
  assert.equal(p.elementos.iniciar.disabled, true);
  p.posicion(-36.5, -72.2, 5); // misma posición: no repite el cálculo
  await esperar();
  assert.equal(p.llamadas.pedidos.length, 1);
  p.elementos.detener.click();
  assert.deepEqual(p.llamadas.mapa.at(-1), ["limpiar"]);
  // Pausada y luego detenida (por ejemplo, al salir con la página oculta): también limpia.
  const q = preparar();
  q.elementos.iniciar.click();
  q.documento.visibilityState = "hidden";
  q.documento.manejadores.visibilitychange();
  q.ventana.manejadores.pagehide();
  assert.deepEqual(q.llamadas.limpiar, [77]);
  assert.deepEqual(q.llamadas.mapa.at(-1), ["limpiar"]);
  assert.equal(q.elementos.iniciar.disabled, false);
});

test("el módulo solo pide el tramo a Django con tramo.js; la plantilla deja el enlace y las coordenadas", () => {
  const codigo = fs.readFileSync(ruta, "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  assert.doesNotMatch(codigo, /XMLHttpRequest|sendBeacon|WebSocket|rumbo|noreste|localStorage|sessionStorage/);
  assert.match(codigo, /urlTramo: datos\.url_tramo/);
  const plantilla = fs.readFileSync(path.join(__dirname, "../../templates/entregas/ir_a.html"), "utf8");
  assert.match(plantilla, /Abrir en app de navegación/);
  assert.match(plantilla, /coordenadas-texto/);
  assert.doesNotMatch(plantilla, /línea recta/);
});
