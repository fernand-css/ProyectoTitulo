// Pruebas de static/js/entregas/usar_mapa.js (spec 09, enmienda del 2026-11-15, RF-09-25), con DOM y Leaflet simulados.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const ruta = path.join(__dirname, "../../static/js/entregas/usar_mapa.js");
const usarMapa = require(ruta);
const { Documento, crear, evento } = require("./dom_simulado.cjs");

const ORIGEN = { lat: -36.498877, lon: -72.21236 };

function pagina({ latitud = "", longitud = "", precision = "12" } = {}) {
  const documento = new Documento();
  documento.body.appendChild(crear(documento, ["form", { "data-domicilio-form": true },
    ["input", { name: "latitud", value: latitud }],
    ["input", { name: "longitud", value: longitud }],
    ["input", { name: "precision_metros", value: precision }],
    ["button", { "data-usar-mapa-abrir": "dialogo-usar-mapa", hidden: true }, "Usar mapa"],
    ["p", { "data-usar-mapa-resultado": true }]]));
  const dialogo = crear(documento, ["dialog", { "data-usar-mapa": true },
    ["button", { "data-usar-mapa-cerrar": true }],
    ["div", { "data-usar-mapa-mapa": true, tabindex: "0" }],
    ["p", { id: "aviso-usar-mapa", hidden: true }],
    ["p", { "data-usar-mapa-estado": true }, "Aún no marcas un punto."],
    ["button", { "data-usar-mapa-centro": true }],
    ["button", { "data-usar-mapa-usar": true, disabled: true }],
    ["button", { "data-usar-mapa-cancelar": true }]]);
  dialogo.open = false;
  dialogo.showModal = function () { this.open = true; };
  dialogo.close = function () { if (!this.open) return; this.open = false; this.dispatchEvent(evento("close")); };
  documento.body.appendChild(dialogo);
  // Los botones del DOM simulado guardan `disabled` como propiedad.
  dialogo.querySelector("[data-usar-mapa-usar]").disabled = true;
  return { documento, dialogo };
}

function leafletFalso() {
  const registro = { vistas: [], marcadores: [], quitados: 0, centro: { lat: -36.51, lng: -72.19 } };
  const mapa = {
    escuchas: {},
    on(tipo, fn) { this.escuchas[tipo] = fn; return this; },
    setView(centro, zoom) { registro.vistas.push({ centro, zoom }); },
    getCenter() { return registro.centro; },
    removeLayer() { registro.quitados += 1; },
    invalidateSize() { registro.invalidado = true; },
  };
  const L = {
    registro,
    marker(latlng, opciones) {
      const marcador = { latlng, opciones, setLatLng(n) { this.latlng = n; }, addTo() { return this; } };
      registro.marcadores.push(marcador);
      return marcador;
    },
  };
  const mapas = {
    crearMapa(Lx, contenedor, teselas, aviso, extra) { registro.creado = { contenedor, teselas, extra }; return mapa; },
    nombrar(marcador) { return marcador; },
    iconoPunto() { return { className: "marcador marcador-domicilio" }; },
  };
  return { L, mapas, mapa, registro };
}

class EventoFalso { constructor(tipo, opciones) { this.type = tipo; this.bubbles = opciones && opciones.bubbles; } }

function preparar(opciones) {
  const { documento, dialogo } = pagina(opciones);
  const falso = leafletFalso();
  const cambios = [];
  ["latitud", "longitud", "precision_metros"].forEach((nombre) => {
    const campo = documento.querySelector(`[name=${nombre}]`);
    campo.dispatchEvent = (e) => { cambios.push([nombre, e.type]); return true; };
  });
  const control = usarMapa.preparar(documento, { L: falso.L, mapas: falso.mapas, datos: { origen: ORIGEN, teselas: { url: "x" } }, Evento: EventoFalso });
  return { documento, dialogo, falso, control, cambios, campo: (n) => documento.querySelector(`[name=${n}]`) };
}

test("el centro inicial es el punto del formulario si es válido; si no, el CESFAM", () => {
  assert.deepEqual(usarMapa.centroInicial("-36.512345", "-72.198765", ORIGEN), { lat: -36.512345, lon: -72.198765, marcado: true });
  assert.deepEqual(usarMapa.centroInicial("-36,5", "-72,2", ORIGEN), { lat: -36.5, lon: -72.2, marcado: true });
  for (const [lat, lon] of [["", ""], ["95", "-72"], ["-36.5", ""], ["abc", "-72.2"], ["-36.5", "-190"]]) {
    assert.deepEqual(usarMapa.centroInicial(lat, lon, ORIGEN), { lat: ORIGEN.lat, lon: ORIGEN.lon, marcado: false });
  }
});

test("el botón «Usar mapa» aparece solo con JavaScript y lo necesario; sin <dialog> no aparece", () => {
  const { documento } = preparar();
  assert.equal(documento.querySelector("[data-usar-mapa-abrir]").hidden, false);
  const sinDialogo = pagina();
  delete sinDialogo.dialogo.showModal;
  const falso = leafletFalso();
  assert.equal(usarMapa.preparar(sinDialogo.documento, { L: falso.L, mapas: falso.mapas, datos: { origen: ORIGEN } }), null);
  assert.equal(sinDialogo.documento.querySelector("[data-usar-mapa-abrir]").hidden, true);
  const sinLeaflet = pagina();
  assert.equal(usarMapa.preparar(sinLeaflet.documento, { L: null, mapas: null, datos: { origen: ORIGEN } }), null);
  assert.equal(sinLeaflet.documento.querySelector("[data-usar-mapa-abrir]").hidden, true);
});

test("sin coordenadas abre en el CESFAM sin marca; con coordenadas válidas, en el punto marcado", () => {
  const vacio = preparar();
  vacio.documento.querySelector("[data-usar-mapa-abrir]").click();
  assert.equal(vacio.dialogo.open, true);
  assert.deepEqual(vacio.falso.registro.vistas[0], { centro: [ORIGEN.lat, ORIGEN.lon], zoom: 14 });
  assert.equal(vacio.falso.registro.marcadores.length, 0);
  assert.equal(vacio.dialogo.querySelector("[data-usar-mapa-usar]").disabled, true);
  assert.equal(vacio.falso.registro.creado.extra.scrollWheelZoom, true); // el mapa se mueve y se acerca libremente
  assert.equal(vacio.documento.activeElement, vacio.dialogo.querySelector("[data-usar-mapa-mapa]"));
  const lleno = preparar({ latitud: "-36.512345", longitud: "-72.198765" });
  lleno.documento.querySelector("[data-usar-mapa-abrir]").click();
  assert.deepEqual(lleno.falso.registro.vistas[0], { centro: [-36.512345, -72.198765], zoom: 17 });
  assert.equal(lleno.falso.registro.marcadores.length, 1);
  assert.match(lleno.dialogo.querySelector("[data-usar-mapa-estado]").textContent, /Punto marcado: -36\.512345, -72\.198765/);
});

test("un clic marca el punto y otro lo reemplaza; «Marcar el centro del mapa» usa la mira", () => {
  const p = preparar();
  p.documento.querySelector("[data-usar-mapa-abrir]").click();
  p.falso.mapa.escuchas.click({ latlng: { lat: -36.5012345678, lng: -72.2098765432 } });
  assert.equal(p.falso.registro.marcadores.length, 1);
  assert.equal(p.dialogo.querySelector("[data-usar-mapa-usar]").disabled, false);
  p.falso.mapa.escuchas.click({ latlng: { lat: -36.52, lng: -72.22 } });
  assert.equal(p.falso.registro.marcadores.length, 1); // el mismo marcador se mueve
  assert.deepEqual(p.falso.registro.marcadores[0].latlng, [-36.52, -72.22]);
  p.dialogo.querySelector("[data-usar-mapa-centro]").click();
  assert.deepEqual(p.control.elegido(), { lat: "-36.510000", lon: "-72.190000" });
});

test("«Usar este punto» copia 6 decimales, vacía la precisión, avisa al formulario, cierra y devuelve el foco", () => {
  const p = preparar({ latitud: "", longitud: "", precision: "25" });
  const abrir = p.documento.querySelector("[data-usar-mapa-abrir]");
  abrir.click();
  p.falso.mapa.escuchas.click({ latlng: { lat: -36.5012345678, lng: -72.2098765432 } });
  p.dialogo.querySelector("[data-usar-mapa-usar]").click();
  assert.equal(p.campo("latitud").value, "-36.501235");
  assert.equal(p.campo("longitud").value, "-72.209877");
  assert.equal(p.campo("precision_metros").value, "");
  assert.deepEqual(p.cambios, [["latitud", "input"], ["latitud", "change"], ["longitud", "input"], ["longitud", "change"],
    ["precision_metros", "input"], ["precision_metros", "change"]]);
  assert.equal(p.dialogo.open, false);
  assert.equal(p.documento.activeElement, abrir);
  assert.match(p.documento.querySelector("[data-usar-mapa-resultado]").textContent, /guarda el domicilio/);
});

test("«Cancelar», Esc y la X cierran sin cambiar los campos", () => {
  for (const cerrar of [(p) => p.dialogo.querySelector("[data-usar-mapa-cancelar]").click(),
    (p) => p.dialogo.dispatchEvent(evento("cancel")),
    (p) => p.dialogo.querySelector("[data-usar-mapa-cerrar]").click()]) {
    const p = preparar({ latitud: "-36.5", longitud: "-72.2", precision: "12" });
    const abrir = p.documento.querySelector("[data-usar-mapa-abrir]");
    abrir.click();
    p.falso.mapa.escuchas.click({ latlng: { lat: -36.6, lng: -72.3 } });
    cerrar(p);
    assert.equal(p.dialogo.open, false);
    assert.deepEqual([p.campo("latitud").value, p.campo("longitud").value, p.campo("precision_metros").value], ["-36.5", "-72.2", "12"]);
    assert.deepEqual(p.cambios, []);
    assert.equal(p.documento.activeElement, abrir);
  }
});

test("no hace solicitudes propias ni guarda nada en el navegador", () => {
  const codigo = fs.readFileSync(ruta, "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  assert.doesNotMatch(codigo, /fetch\(|XMLHttpRequest|sendBeacon|localStorage|sessionStorage|\.submit\(/);
});
