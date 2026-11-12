// Spec 09 (RF-09-09): «Ir a esta parada» con una geolocalización simulada. La posición nunca sale del navegador.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const test = require("node:test");

const ruta = path.join(__dirname, "../../static/js/entregas/ir_a.js");
const guia = require(ruta);

const DESTINO = { lat: -36.4988773, lon: -72.2123601, numero: 3 };
const METROS_POR_GRADO = (6371000 * Math.PI) / 180;

// Punto desde el que la parada queda `este` metros al este y `norte` metros al norte (aproximación plana).
function desde(este, norte) {
  return {
    lat: DESTINO.lat - norte / METROS_POR_GRADO,
    lon: DESTINO.lon - este / (METROS_POR_GRADO * Math.cos((DESTINO.lat * Math.PI) / 180)),
  };
}

function boton() {
  return { disabled: false, manejadores: {}, addEventListener(evento, funcion) { this.manejadores[evento] = funcion; },
    click() { this.manejadores.click(); } };
}

function preparar({ seguro = true, sinGeolocalizacion = false } = {}) {
  const llamadas = { observar: [], limpiar: [], mapa: [] };
  let exito;
  let error;
  const geolocation = {
    watchPosition(alExito, alError, opciones) {
      exito = alExito;
      error = alError;
      llamadas.observar.push(opciones);
      return 77;
    },
    clearWatch(id) { llamadas.limpiar.push(id); },
  };
  const ventana = { isSecureContext: seguro, manejadores: {}, addEventListener(evento, funcion) { this.manejadores[evento] = funcion; } };
  const documento = { visibilityState: "visible", manejadores: {}, addEventListener(evento, funcion) { this.manejadores[evento] = funcion; } };
  const elementos = { estado: { textContent: "" }, anuncio: { textContent: "" }, iniciar: boton(), leer: boton(), detener: boton() };
  elementos.leer.disabled = true;
  elementos.detener.disabled = true;
  const instancia = guia.crearGuia({
    destino: DESTINO,
    navegador: sinGeolocalizacion ? {} : { geolocation },
    ventana,
    documento,
    elementos,
    mapa: { actualizar(lat, lon, precision) { llamadas.mapa.push([lat, lon, precision]); } },
  });
  const posicion = (punto, precision = 15) => exito({ coords: { latitude: punto.lat, longitude: punto.lon, accuracy: precision } });
  return { instancia, elementos, llamadas, ventana, documento, posicion, fallar: (codigo) => error({ code: codigo }) };
}

test("distancia haversine y formato en metros o kilómetros", () => {
  assert.ok(Math.abs(guia.distanciaM({ lat: 0, lon: 0 }, { lat: 1, lon: 0 }) - 111194.93) < 0.01);
  assert.ok(Math.abs(guia.distanciaM(desde(0, 850), DESTINO) - 850) < 1);
  assert.equal(guia.formatearDistancia(850), "850 m");
  assert.equal(guia.formatearDistancia(844), "840 m");
  assert.equal(guia.formatearDistancia(5), "10 m");
  assert.equal(guia.formatearDistancia(0), "0 m");
  assert.equal(guia.formatearDistancia(995), "1,0 km");
  assert.equal(guia.formatearDistancia(1249), "1,2 km");
  assert.equal(guia.formatearDistancia(12345), "12,3 km");
});

test("rumbo en ocho direcciones desde la posición hacia la parada", () => {
  const casos = [
    [desde(0, 1000), "norte"], [desde(1000, 1000), "noreste"], [desde(1000, 0), "este"], [desde(1000, -1000), "sureste"],
    [desde(0, -1000), "sur"], [desde(-1000, -1000), "suroeste"], [desde(-1000, 0), "oeste"], [desde(-1000, 1000), "noroeste"],
  ];
  for (const [punto, esperado] of casos) assert.equal(guia.rumbo(punto, DESTINO), esperado);
});

test("texto de la guía con distancia, dirección y precisión", () => {
  assert.equal(guia.texto(3, 1200, "noreste", 15.4), "La parada 3 está a 1,2 km hacia el noreste (precisión ±15 m).");
  assert.equal(guia.texto(3, 850, "sur"), "La parada 3 está a 850 m hacia el sur.");
  assert.equal(guia.texto(3, 60, "sur", 5), "Estás a menos de 100 m de la parada 3.");
});

test("sigue la posición con el gesto, actualiza el texto y el mapa y avisa solo al iniciar, al leer y al llegar", () => {
  const { elementos, llamadas, posicion } = preparar();
  assert.match(elementos.estado.textContent, /^$|Pulsa/);
  elementos.iniciar.click();
  assert.equal(llamadas.observar.length, 1);
  assert.equal(llamadas.observar[0].enableHighAccuracy, true);
  assert.equal(elementos.iniciar.disabled, true);
  assert.equal(elementos.detener.disabled, false);
  assert.match(elementos.anuncio.textContent, /Buscando tu posición/);
  const inicial = elementos.anuncio.textContent;
  posicion(desde(850, 850), 15);
  assert.equal(elementos.estado.textContent, "La parada 3 está a 1,2 km hacia el noreste (precisión ±15 m).");
  assert.equal(elementos.anuncio.textContent, inicial); // no satura al lector de pantalla
  assert.equal(llamadas.mapa.length, 1);
  elementos.leer.click();
  assert.match(elementos.anuncio.textContent, /La parada 3 está a 1,2 km hacia el noreste/);
  posicion(desde(0, 60), 5);
  assert.match(elementos.anuncio.textContent, /Estás a menos de 100 m de la parada 3\./);
  const cerca = elementos.anuncio.textContent;
  posicion(desde(0, 40), 5);
  assert.equal(elementos.anuncio.textContent, cerca); // el aviso de llegada se da una vez
  elementos.iniciar.click();
  assert.equal(llamadas.observar.length, 1); // no abre un segundo seguimiento
});

test("«Detener», salir de la página u ocultarla terminan el seguimiento", () => {
  const primero = preparar();
  primero.elementos.iniciar.click();
  primero.elementos.detener.click();
  assert.deepEqual(primero.llamadas.limpiar, [77]);
  assert.match(primero.elementos.estado.textContent, /Seguimiento detenido/);
  assert.equal(primero.instancia.siguiendo(), false);
  assert.equal(primero.elementos.iniciar.disabled, false);

  const segundo = preparar();
  segundo.elementos.iniciar.click();
  segundo.ventana.manejadores.pagehide();
  assert.deepEqual(segundo.llamadas.limpiar, [77]);

  const tercero = preparar();
  tercero.elementos.iniciar.click();
  tercero.documento.visibilityState = "hidden";
  tercero.documento.manejadores.visibilitychange();
  assert.deepEqual(tercero.llamadas.limpiar, [77]);
});

test("permiso denegado, sin posición o sin contexto seguro se explican con texto", () => {
  const denegado = preparar();
  denegado.elementos.iniciar.click();
  denegado.fallar(1);
  assert.match(denegado.elementos.estado.textContent, /No diste permiso/);
  assert.match(denegado.elementos.anuncio.textContent, /app de navegación o las coordenadas/);
  assert.deepEqual(denegado.llamadas.limpiar, [77]);

  const sinPosicion = preparar();
  sinPosicion.elementos.iniciar.click();
  sinPosicion.fallar(2);
  assert.match(sinPosicion.elementos.estado.textContent, /No pudimos obtener tu posición/);
  sinPosicion.fallar(3);
  assert.match(sinPosicion.elementos.estado.textContent, /Aún buscamos tu posición/);

  for (const opciones of [{ seguro: false }, { sinGeolocalizacion: true }]) {
    const inseguro = preparar(opciones);
    assert.match(inseguro.elementos.estado.textContent, /conexión segura \(HTTPS\)/);
    inseguro.elementos.iniciar.click();
    assert.equal(inseguro.llamadas.observar.length, 0);
    assert.match(inseguro.elementos.anuncio.textContent, /coordenadas/);
  }
});

test("la posición nunca se envía: el módulo no usa red ni almacenamiento", () => {
  const codigo = fs.readFileSync(ruta, "utf8");
  const sinComentarios = codigo.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  assert.doesNotMatch(sinComentarios, /\bfetch\s*\(|XMLHttpRequest|sendBeacon|WebSocket|localStorage|sessionStorage|indexedDB|new Image/);
  // En un contexto donde cualquier acceso a la red falla, la guía completa funciona igual.
  const prohibido = () => { throw new Error("solicitud de red"); };
  const contexto = { module: { exports: {} }, fetch: prohibido, XMLHttpRequest: prohibido, navigator: { sendBeacon: prohibido },
    Math, Number, Boolean, String };
  vm.runInNewContext(codigo, contexto);
  const aislado = contexto.module.exports;
  assert.equal(aislado.formatearDistancia(1249), "1,2 km");
});
