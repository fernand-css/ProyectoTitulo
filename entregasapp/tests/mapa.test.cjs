// Spec 09 (RF-09-08, RF-09-11 y RF-09-14; enmienda del 2026-11-15, RF-09-21, RF-09-22 y RF-09-26): mapa.js con
// un Leaflet y un DOM simulados. Desde la enmienda no hay línea del recorrido completo: solo el tramo por camino.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const ruta = path.join(__dirname, "../../static/js/entregas/mapa.js");
const mapa = require(ruta);
const tramo = require(path.join(__dirname, "../../static/js/entregas/tramo.js"));
const { Documento, crear, evento } = require("./dom_simulado.cjs");

// Leaflet simulado: registra cada capa, marcador y opción para revisarlos.
function leafletFalso() {
  const registro = { capas: [], marcadores: [], lineas: [], circulos: [], vistas: [], encuadres: [], prefijo: null };
  const capaConEventos = (extra) => {
    const manejadores = {};
    return Object.assign({
      manejadores,
      on(evento, funcion) { manejadores[evento] = funcion; return this; },
      emitir(evento) { if (manejadores[evento]) manejadores[evento](); },
      addTo() { this.agregado = true; if (manejadores.add) manejadores.add(); return this; },
    }, extra);
  };
  const L = {
    registro,
    map(contenedor, opciones) {
      return {
        contenedor, opciones,
        removeLayer(capa) { capa.quitada = true; },
        attributionControl: { setPrefix(prefijo) { registro.prefijo = prefijo; } },
        fitBounds(puntos, opciones2) { registro.encuadres.push({ puntos, opciones: opciones2 }); },
        setView(centro, zoom) { registro.vistas.push({ centro, zoom }); },
      };
    },
    tileLayer(url, opciones) {
      const capa = capaConEventos({ url, opciones });
      registro.capas.push(capa);
      return capa;
    },
    divIcon(opciones) { return opciones; },
    marker(latlng, opciones) {
      const elemento = { atributos: {}, setAttribute(nombre, valor) { this.atributos[nombre] = valor; } };
      const marcador = capaConEventos({
        latlng, opciones, elemento,
        getElement() { return elemento; },
        bindPopup(contenido) { this.popup = contenido; return this; },
        setLatLng(nuevo) { this.latlng = nuevo; },
        setIcon(icono) { this.opciones.icon = icono; },
        getLatLng() { return this.latlng; },
      });
      registro.marcadores.push(marcador);
      return marcador;
    },
    circleMarker(latlng, opciones) { return L.marker(latlng, opciones); },
    polyline(puntos, opciones) {
      const linea = capaConEventos({ puntos, opciones, setLatLngs(nuevos) { this.puntos = nuevos; } });
      registro.lineas.push(linea);
      return linea;
    },
    circle(latlng, opciones) {
      const circulo = capaConEventos({ latlng, opciones, setLatLng(n) { this.latlng = n; }, setRadius(r) { this.opciones.radius = r; } });
      registro.circulos.push(circulo);
      return circulo;
    },
  };
  return L;
}

// DOM mínimo: nodos con textContent, hijos y atributos; los textos nunca se interpretan como HTML.
function documentoFalso(elementos = {}) {
  const crear = (etiqueta) => ({
    etiqueta, hijos: [], textContent: "", className: "", hidden: false, atributos: {},
    appendChild(hijo) { this.hijos.push(hijo); return hijo; },
    getAttribute(nombre) { return this.atributos[nombre]; },
    setAttribute(nombre, valor) { this.atributos[nombre] = valor; },
  });
  return {
    crear,
    createElement: crear,
    getElementById(id) { return elementos[id] || null; },
    querySelectorAll() { return Object.values(elementos).filter((e) => e.atributos && e.atributos["data-mapa"]); },
  };
}

function textos(nodo) {
  return [nodo.textContent, ...nodo.hijos.flatMap(textos)].filter(Boolean);
}

const DATOS = {
  origen: { lat: -36.498877, lon: -72.21236, etiqueta: "CESFAM" },
  partida: null,
  teselas: { url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png", atribucion: "© colaboradores de OpenStreetMap", zoom_maximo: 19 },
  paradas: [
    { numero: 1, intento: 41, lat: -36.49, lon: -72.21, estado: "Pendiente", nueva: false, titulo: "Paciente sintético 1",
      sector: "Verde", localidad: "Localidad demo 1", direccion: "Camino sintético", referencias: "Portón azul",
      url_registrar: "/entregas/intentos/41/", url_ir: "/entregas/mis/ir/41/", url_domicilio: "/entregas/domicilios/paciente/7/" },
    { numero: 3, intento: 43, lat: -36.48, lon: -72.20, estado: "Atrasada desde el 10/11", nueva: true,
      titulo: "<img src=x onerror=alert(1)>", sector: "", localidad: "", direccion: "Parcela 4", referencias: "",
      url_registrar: "", url_ir: "", url_domicilio: "/entregas/domicilios/paciente/8/" },
  ],
  registradas: [
    { intento: 39, lat: -36.47, lon: -72.22, entregada: false, resultado: "No entregada", motivo: "Domicilio no encontrado",
      hora: "10:15", titulo: "Paciente sintético 9", sector: "Azul", localidad: "", direccion: "Camino 9", referencias: "",
      url_domicilio: "/entregas/domicilios/paciente/9/" },
  ],
  distancia: "camino",
  total_km: "4,2",
  sin_marcador: 1,
  consulta: false,
  url_tramo: "/entregas/mis/tramo/",
  url_cercana: "/entregas/mis/cercana/",
  url_mover: "/entregas/mis/orden/mover/",
  version: 0,
};

test("dibuja el CESFAM, las paradas con el número de la lista y las registradas, sin línea del recorrido", () => {
  const L = leafletFalso();
  const documento = documentoFalso();
  const aviso = documento.crear("p");
  const { marcadores } = mapa.dibujarRuta(L, documento, documento.crear("div"), DATOS, aviso);
  assert.equal(L.registro.marcadores.length, 1 + 2 + 1);
  assert.deepEqual(marcadores.paradas.map((m) => m.opciones.icon.html), ["<span>1</span>", "<span>3</span>"]);
  assert.deepEqual(marcadores.paradas.map((m) => m.elemento.atributos["aria-label"]),
    ["Parada 1, pendiente", "Parada 3, atrasada desde el 10/11, nueva"]);
  assert.ok(marcadores.paradas.every((m) => m.opciones.keyboard === true));
  assert.match(marcadores.paradas[1].opciones.icon.className, /marcador-atrasada/);
  const registrada = marcadores.registradas[0];
  assert.equal(registrada.opciones.icon.html, "<span>✗</span>");
  assert.equal(registrada.elemento.atributos["aria-label"], "No entregada: Domicilio no encontrado, a las 10:15. Paciente sintético 9");
  assert.equal(L.registro.marcadores[0].elemento.atributos["aria-label"], "CESFAM, inicio y fin del recorrido");
  assert.equal(L.registro.lineas.length, 0); // RF-09-21: se quitó la línea punteada del recorrido completo
  assert.equal(L.registro.encuadres.length, 1);
});

test("el tramo por camino es una línea continua; la parada más cercana cambia de forma y de nombre", () => {
  const L = leafletFalso();
  const documento = documentoFalso();
  const dibujo = mapa.dibujarRuta(L, documento, documento.crear("div"), DATOS, documento.crear("p"));
  dibujo.mostrarPosicion(-36.5, -72.2, 15);
  dibujo.dibujarTramo([[-36.5, -72.2], [-36.495, -72.205], [-36.48, -72.20]]);
  const [linea] = L.registro.lineas;
  assert.equal(linea.opciones.className, "linea-tramo");
  assert.equal(linea.opciones.dashArray, undefined);
  assert.equal(linea.puntos.length, 3);
  dibujo.dibujarTramo([[-36.49, -72.2], [-36.48, -72.20]]);
  assert.equal(L.registro.lineas.length, 1); // se reutiliza la misma capa
  assert.equal(dibujo.destacar(43), true);
  const destacada = dibujo.marcadores.paradas[1];
  assert.match(destacada.opciones.icon.className, /marcador-cercana/);
  assert.equal(destacada.elemento.atributos["aria-label"], "Parada 3, atrasada desde el 10/11, nueva, la más cercana por camino");
  dibujo.destacar(41);
  assert.doesNotMatch(destacada.opciones.icon.className, /marcador-cercana/);
  assert.equal(destacada.elemento.atributos["aria-label"], "Parada 3, atrasada desde el 10/11, nueva");
  dibujo.limpiar();
  assert.equal(linea.quitada, true);
  assert.doesNotMatch(dibujo.marcadores.paradas[0].opciones.icon.className, /marcador-cercana/);
});

test("al cambiar de destino encuadra la posición, el tramo y la parada; al recalcular no mueve la vista", () => {
  const L = leafletFalso();
  const documento = documentoFalso();
  const dibujo = mapa.dibujarRuta(L, documento, documento.crear("div"), DATOS, documento.crear("p"));
  const antes = L.registro.encuadres.length;
  dibujo.mostrarPosicion(-36.5, -72.2, 10);
  dibujo.dibujarTramo([[-36.4995, -72.2001], [-36.4991, -72.2005]], 43);
  const encuadre = L.registro.encuadres.at(-1);
  assert.equal(L.registro.encuadres.length, antes + 1);
  assert.deepEqual(encuadre.puntos.slice(-2), [[-36.5, -72.2], [-36.48, -72.20]]); // mi posición y la parada 3
  assert.equal(encuadre.opciones.maxZoom, 16);
  dibujo.dibujarTramo([[-36.4993, -72.2002], [-36.4991, -72.2005]], 43);
  assert.equal(L.registro.encuadres.length, antes + 1);
  dibujo.dibujarTramo([[-36.4993, -72.2002], [-36.49, -72.21]], 41);
  assert.equal(L.registro.encuadres.length, antes + 2);
});

test("en «Rutas» (consulta) los resúmenes no ofrecen tramo", () => {
  const documento = documentoFalso();
  const consulta = mapa.resumenParada(documento, DATOS.paradas[0], false);
  assert.ok(!consulta.hijos.some((h) => h.atributos && h.atributos["data-trazar"]));
  const encargado = mapa.resumenParada(documento, DATOS.paradas[0], true);
  const boton = encargado.hijos.at(-1);
  assert.equal(boton.textContent, "Trazar tramo hasta aquí");
});

test("las teselas piden solo el origen como referente y llevan la atribución de OpenStreetMap", () => {
  const L = leafletFalso();
  const documento = documentoFalso();
  mapa.dibujarRuta(L, documento, documento.crear("div"), DATOS, documento.crear("p"));
  const [capa] = L.registro.capas;
  assert.equal(capa.url, DATOS.teselas.url);
  assert.equal(capa.opciones.referrerPolicy, "strict-origin");
  assert.equal(capa.opciones.maxZoom, 19);
  assert.match(capa.opciones.attribution, /href="https:\/\/www\.openstreetmap\.org\/copyright"/);
  assert.match(capa.opciones.attribution, /© colaboradores de OpenStreetMap/);
  assert.doesNotMatch(L.registro.prefijo, /svg/i);
  // Otro proveedor: la atribución configurada va como texto, escapada.
  const otra = mapa.opcionesTeselas({ url: "https://teselas.example.invalid/{z}/{x}/{y}.png", atribucion: "<b>Proveedor</b>", zoom_maximo: 18 });
  assert.equal(otra.attribution, "&lt;b&gt;Proveedor&lt;/b&gt;");
});

test("si el mapa base falla, avisa con texto y los marcadores siguen", () => {
  const L = leafletFalso();
  const documento = documentoFalso();
  const aviso = documento.crear("p");
  aviso.hidden = true;
  mapa.dibujarRuta(L, documento, documento.crear("div"), DATOS, aviso);
  const [capa] = L.registro.capas;
  capa.emitir("loading");
  capa.emitir("tileerror");
  assert.equal(aviso.hidden, false);
  assert.equal(aviso.textContent, "No se pudo cargar el mapa base. Los puntos y la lista siguen disponibles.");
  capa.emitir("load");
  assert.equal(aviso.hidden, false); // la carga terminó con errores: el aviso sigue
  capa.emitir("loading");
  capa.emitir("load");
  assert.equal(aviso.hidden, true);
  assert.equal(L.registro.marcadores.length, 4);
});

test("el resumen del marcador se arma con texto, sin interpretar HTML de los datos", () => {
  const documento = documentoFalso();
  const resumen = mapa.resumenParada(documento, DATOS.paradas[1]);
  const contenido = textos(resumen);
  assert.ok(contenido.includes("<img src=x onerror=alert(1)>"));
  assert.ok(contenido.includes("Parada 3 · Atrasada desde el 10/11 · Nueva"));
  const enlaces = resumen.hijos.at(-1).hijos;
  assert.deepEqual(enlaces.map((a) => [a.textContent, a.href]), [["Detalles del domicilio", "/entregas/domicilios/paciente/8/"]]);
  const completo = mapa.resumenParada(documento, DATOS.paradas[0]);
  assert.deepEqual(completo.hijos.at(-1).hijos.map((a) => a.textContent), ["Registrar", "Ir a esta parada", "Detalles del domicilio"]);
  assert.ok(textos(completo).includes("Sector Verde · Localidad demo 1"));
});

test("mapa pequeño del domicilio con su círculo de precisión", () => {
  const L = leafletFalso();
  const documento = documentoFalso();
  mapa.dibujarPunto(L, documento, documento.crear("div"), { lat: -36.5, lon: -72.2, precision: 12, teselas: DATOS.teselas }, null);
  assert.equal(L.registro.marcadores.length, 1);
  assert.equal(L.registro.marcadores[0].elemento.atributos["aria-label"], "Ubicación del domicilio");
  assert.equal(L.registro.circulos[0].opciones.radius, 12);
  assert.deepEqual(L.registro.vistas[0], { centro: [-36.5, -72.2], zoom: 16 });
});

test("el destino de «Ir a esta parada» mueve mi posición y dibuja solo el tramo por camino", () => {
  const L = leafletFalso();
  const documento = documentoFalso();
  const guia = mapa.dibujarDestino(L, documento, documento.crear("div"), { lat: -36.5, lon: -72.2, numero: 3, teselas: DATOS.teselas }, null);
  guia.actualizar(-36.51, -72.21, 15);
  guia.actualizar(-36.505, -72.205, 8);
  assert.equal(L.registro.lineas.length, 0); // sin línea recta hasta la parada
  assert.equal(L.registro.circulos[0].opciones.radius, 8);
  assert.equal(L.registro.marcadores.length, 2);
  guia.dibujarTramo([[-36.505, -72.205], [-36.503, -72.2], [-36.5, -72.2]]);
  assert.equal(L.registro.lineas[0].opciones.className, "linea-tramo");
});

// Corrección del 2026-11-16: zoom con Ctrl + rueda; la rueda sola sigue desplazando la página.
test("la rueda solo acerca el mapa con Ctrl; sin Ctrl no llega a Leaflet", () => {
  const conEscucha = () => {
    const contenedor = { escuchas: [], addEventListener(tipo, funcion, captura) { this.escuchas.push({ tipo, funcion, captura }); } };
    return contenedor;
  };
  const rueda = (ctrlKey) => ({ ctrlKey, detenido: false, stopImmediatePropagation() { this.detenido = true; } });
  for (const extra of [null, mapa.FIJO]) {
    const L = leafletFalso();
    const contenedor = conEscucha();
    const creado = mapa.crearMapa(L, contenedor, DATOS.teselas, null, extra);
    assert.equal(creado.opciones.scrollWheelZoom, true);
    assert.equal(contenedor.escuchas.length, 1);
    const { tipo, funcion, captura } = contenedor.escuchas[0];
    assert.deepEqual([tipo, captura], ["wheel", true]); // en captura, antes que el manejador de Leaflet
    const sinCtrl = rueda(false);
    funcion(sinCtrl);
    assert.equal(sinCtrl.detenido, true);
    const conCtrl = rueda(true);
    funcion(conCtrl);
    assert.equal(conCtrl.detenido, false);
  }
  const libre = conEscucha(); // «Usar mapa»: la rueda sola acerca, sin filtro
  mapa.crearMapa(leafletFalso(), libre, DATOS.teselas, null, { scrollWheelZoom: true });
  assert.equal(libre.escuchas.length, 0);
});

test("sin Leaflet, oculta el contenedor y deja el texto de la lista", () => {
  const documento = documentoFalso();
  const contenedor = documento.crear("div");
  contenedor.atributos = { "data-mapa": "ruta", "data-datos": "datos-mapa", "data-aviso": "aviso" };
  const aviso = documento.crear("p");
  const fuente = documento.crear("script");
  fuente.textContent = JSON.stringify(DATOS);
  const conElementos = documentoFalso({ contenedor, aviso, "datos-mapa": fuente });
  mapa.iniciar(conElementos, undefined);
  assert.equal(contenedor.hidden, true);
  assert.match(aviso.textContent, /La lista tiene toda la información/);
  const L = leafletFalso();
  contenedor.hidden = false;
  const resultado = mapa.iniciar(conElementos, L);
  assert.ok(resultado.ruta);
  assert.equal(L.registro.marcadores.length, 4);
});

test("solo pide a Django mover la parada; no usa innerHTML ni otras vías de red", () => {
  const codigo = fs.readFileSync(ruta, "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  assert.doesNotMatch(codigo, /XMLHttpRequest|sendBeacon|WebSocket|innerHTML|insertAdjacentHTML/);
  assert.equal((codigo.match(/\bfetch\s*\(/g) || []).length, 1);
  assert.match(codigo, /global\.fetch\(datos\.url_mover/);
  assert.doesNotMatch(codigo, /5000|osrm/i); // el navegador no conoce la dirección de OSRM
});

// Guía del «Mapa» del encargado (RF-09-21 y RF-09-22) con geolocalización, red y dibujo simulados ------------

function paginaGuia() {
  const documento = new Documento();
  ["mapa-guia-estado", "mapa-guia-anuncio"].forEach((id) => documento.body.appendChild(crear(documento, ["p", { id }])));
  documento.body.appendChild(crear(documento, ["div", { id: "mapa-guia-caja" }]));
  documento.body.appendChild(crear(documento, ["button", { id: "mapa-guia-cerrar", hidden: true }, "Cerrar el mensaje"]));
  ["mapa-mostrar", "mapa-detener", "mapa-cercana"].forEach((id) => documento.body.appendChild(crear(documento, ["button", { id }])));
  documento.body.appendChild(crear(documento, ["button", { id: "mapa-mover", hidden: true }]));
  documento.body.appendChild(crear(documento, ["div", { id: "panel", "data-guia-mapa": true, hidden: true }]));
  // Desde el 2026-11-22 la lista vive en el panel desplegable «Paradas».
  const panel = crear(documento, ["details", { class: "mapa-panel-paradas" },
    ["button", { "data-trazar": "43", hidden: true }, "Trazar tramo hasta aquí"]]);
  panel.open = true;
  documento.body.appendChild(panel);
  return documento;
}

function dibujoFalso() {
  const registro = { posiciones: [], tramos: [], limpiado: 0, limpiadoTramo: 0, destacadas: [], quitadas: 0 };
  return {
    registro,
    mostrarPosicion(lat, lon, p) { registro.posiciones.push([lat, lon, p]); },
    dibujarTramo(g) { registro.tramos.push(g); },
    limpiar() { registro.limpiado += 1; },
    limpiarTramo() { registro.limpiadoTramo += 1; },
    destacar(i) { registro.destacadas.push(i); return true; },
    quitarDestacada() { registro.quitadas += 1; },
  };
}

function geoFalsa() {
  return {
    vigilancias: 0, limpiadas: 0, exito: null, fallo: null,
    watchPosition(exito, fallo) { this.exito = exito; this.fallo = fallo; this.vigilancias += 1; return 7; },
    clearWatch() { this.limpiadas += 1; },
    mover(lat, lon, precision) { this.exito({ coords: { latitude: lat, longitude: lon, accuracy: precision || 10 } }); },
  };
}

function metrosAlNorte(lat, metros) { return lat + metros / 111195; }

const esperar = () => new Promise((r) => setImmediate(r));

function armarGuia({ tramo: respuestaTramo, cercana: respuestaCercana, seguro = true, mover } = {}) {
  const documento = paginaGuia();
  const dibujo = dibujoFalso();
  const geo = geoFalsa();
  const reloj = { t: 0 };
  const pedidos = { tramo: [], cercana: [] };
  const cliente = {
    pedirTramo(intento, pos) { pedidos.tramo.push({ intento, pos }); return Promise.resolve(respuestaTramo(intento)); },
    pedirCercana(pos) { pedidos.cercana.push(pos); return Promise.resolve(respuestaCercana()); },
    abortar() { pedidos.abortado = (pedidos.abortado || 0) + 1; },
  };
  const almacen = new Map();
  const ventana = { escuchas: {}, addEventListener(t, f) { this.escuchas[t] = f; } };
  const estado = { recargado: false, movidos: [] };
  const guia = mapa.prepararGuia(documento, {
    datos: DATOS, dibujo, cliente, ventana,
    almacen: { getItem: (k) => almacen.get(k) || null, setItem: (k, v) => almacen.set(k, v), removeItem: (k) => almacen.delete(k) },
    crearSeguimiento: (op) => tramo.crearSeguimiento(Object.assign(op, { geo, seguro, cliente, ahora: () => reloj.t })),
    recargar() { estado.recargado = true; },
    mover: (intento, version) => { estado.movidos.push([intento, version]); return Promise.resolve(mover ? mover() : { ok: true }); },
    elementos: {
      estado: documento.getElementById("mapa-guia-estado"), anuncio: documento.getElementById("mapa-guia-anuncio"),
      mostrar: documento.getElementById("mapa-mostrar"), detener: documento.getElementById("mapa-detener"),
      cercana: documento.getElementById("mapa-cercana"), mover: documento.getElementById("mapa-mover"),
      panel: documento.getElementById("panel"),
      caja: documento.getElementById("mapa-guia-caja"), cerrar: documento.getElementById("mapa-guia-cerrar"),
    },
  });
  return { documento, dibujo, geo, reloj, pedidos, guia, estado, almacen, ventana };
}

const tramoOk = (numero) => (intento) => ({ ok: true, intento, numero: numero || (intento === 41 ? 1 : 3), distancia_m: 1200, distancia_texto: "1,2 km", geometria: [[-36.5, -72.2], [-36.49, -72.21]] });

test("mostrar mi posición traza el tramo hasta la primera parada con coordenadas y luego hasta la elegida", async () => {
  const g = armarGuia({ tramo: tramoOk(), cercana: () => ({ ok: false, mensaje: "x" }) });
  assert.equal(g.documento.getElementById("panel").hidden, false);
  assert.equal(g.documento.querySelector("[data-trazar]").hidden, false);
  g.documento.getElementById("mapa-mostrar").click();
  assert.equal(g.geo.vigilancias, 1);
  assert.equal(g.documento.getElementById("mapa-detener").disabled, false);
  g.geo.mover(-36.5, -72.2, 12);
  await esperar();
  assert.deepEqual(g.pedidos.tramo.map((p) => p.intento), [41]);
  assert.deepEqual(g.pedidos.tramo[0].pos, { lat: -36.5, lon: -72.2 });
  assert.equal(g.dibujo.registro.tramos.length, 1);
  assert.equal(g.documento.getElementById("mapa-guia-estado").textContent, "Parada 1: 1,2 km por camino.");
  g.documento.querySelector("[data-trazar]").click();
  assert.equal(g.documento.querySelector(".mapa-panel-paradas").open, false, "el panel se cierra para ver el tramo");
  await esperar();
  assert.deepEqual(g.pedidos.tramo.map((p) => p.intento), [41, 43]);
  assert.equal(g.documento.getElementById("mapa-guia-estado").textContent, "Parada 3: 1,2 km por camino.");
});

test("el tramo no se recalcula a 100 m y sí a 200 m pasados 20 s; «Detener» lo borra", async () => {
  const g = armarGuia({ tramo: tramoOk(), cercana: () => ({ ok: false, mensaje: "x" }) });
  g.documento.getElementById("mapa-mostrar").click();
  g.geo.mover(-36.5, -72.2);
  await esperar();
  g.reloj.t = 25000;
  g.geo.mover(metrosAlNorte(-36.5, 100), -72.2);
  await esperar();
  assert.equal(g.pedidos.tramo.length, 1);
  g.geo.mover(metrosAlNorte(-36.5, 200), -72.2);
  await esperar();
  assert.equal(g.pedidos.tramo.length, 2);
  g.documento.getElementById("mapa-detener").click();
  assert.equal(g.geo.limpiadas, 1);
  assert.equal(g.dibujo.registro.limpiado, 1);
  assert.equal(g.documento.getElementById("mapa-guia-estado").textContent, tramo.TEXTOS.detenido);
  assert.equal(g.documento.getElementById("mapa-mostrar").disabled, false);
});

test("sin permiso, sin contexto seguro o con OSRM caído solo quedan los marcadores y un aviso", async () => {
  const sinPermiso = armarGuia({ tramo: tramoOk(), cercana: () => ({}) });
  sinPermiso.documento.getElementById("mapa-mostrar").click();
  sinPermiso.geo.fallo({ code: 1 });
  assert.equal(sinPermiso.documento.getElementById("mapa-guia-estado").textContent, tramo.TEXTOS.sinPermiso);
  assert.equal(sinPermiso.geo.limpiadas, 1);
  const inseguro = armarGuia({ tramo: tramoOk(), cercana: () => ({}), seguro: false });
  inseguro.documento.getElementById("mapa-mostrar").click();
  assert.equal(inseguro.geo.vigilancias, 0);
  assert.equal(inseguro.documento.getElementById("mapa-guia-estado").textContent, tramo.TEXTOS.sinContexto);
  const caido = armarGuia({
    tramo: () => ({ ok: false, mensaje: "No se pudo calcular el tramo: el servidor de rutas no respondió. Sigue el orden de la lista." }),
    cercana: () => ({}),
  });
  caido.documento.getElementById("mapa-mostrar").click();
  caido.geo.mover(-36.5, -72.2);
  await esperar();
  assert.equal(caido.dibujo.registro.tramos.length, 0);
  assert.equal(caido.dibujo.registro.limpiadoTramo, 1);
  assert.match(caido.documento.getElementById("mapa-guia-estado").textContent, /servidor de rutas no respondió/);
  const sinRed = armarGuia({ tramo: () => ({ ok: false, mensaje: tramo.TEXTOS.sinRed }), cercana: () => ({}) });
  sinRed.documento.getElementById("mapa-mostrar").click();
  sinRed.geo.mover(-36.5, -72.2);
  await esperar();
  assert.equal(sinRed.documento.getElementById("mapa-guia-estado").textContent, "Sin conexión: no se pudo calcular el tramo. Sigue el orden de la lista.");
});

test("sugerir la más cercana la destaca con texto, traza el tramo y ofrece moverla al primer lugar", async () => {
  const g = armarGuia({
    tramo: tramoOk(3),
    cercana: () => ({ ok: true, intento: 43, numero: 3, distancia_m: 900, distancia_texto: "900 m", es_primera: false, version: 2 }),
  });
  g.documento.getElementById("mapa-cercana").click();
  await esperar();
  assert.equal(g.pedidos.cercana.length, 0); // sin posición, explica que necesita el permiso
  assert.equal(g.documento.getElementById("mapa-guia-estado").textContent, mapa.TEXTOS_GUIA.sinPosicionCercana);
  g.documento.getElementById("mapa-mostrar").click();
  g.geo.mover(-36.5, -72.2);
  await esperar();
  g.documento.getElementById("mapa-cercana").click();
  await esperar(); await esperar();
  assert.deepEqual(g.dibujo.registro.destacadas, [43]);
  assert.equal(g.documento.getElementById("mapa-guia-anuncio").textContent.trim(), "La más cercana por camino es la parada 3, a 900 m.");
  assert.equal(g.documento.getElementById("mapa-mover").hidden, false);
  assert.equal(g.pedidos.tramo.at(-1).intento, 43);
  g.documento.getElementById("mapa-mover").click();
  await esperar(); await esperar();
  assert.deepEqual(g.estado.movidos, [[43, 2]]);
  assert.equal(g.estado.recargado, true);
  assert.equal(g.almacen.get(mapa.CLAVE_ANUNCIO), mapa.TEXTOS_GUIA.movida); // se anuncia al volver a cargar
});

test("si ya es la primera lo dice sin ofrecer moverla; sin OSRM no sugiere ninguna", async () => {
  const primera = armarGuia({
    tramo: tramoOk(1),
    cercana: () => ({ ok: true, intento: 41, numero: 1, distancia_m: 80, distancia_texto: "80 m", es_primera: true, version: 0 }),
  });
  primera.documento.getElementById("mapa-mostrar").click();
  primera.geo.mover(-36.5, -72.2);
  await esperar();
  primera.documento.getElementById("mapa-cercana").click();
  await esperar(); await esperar();
  assert.equal(primera.documento.getElementById("mapa-guia-estado").textContent,
    "La más cercana por camino es la parada 1, a 80 m. Ya es tu próxima parada. Parada 1: 1,2 km por camino.");
  assert.equal(primera.documento.getElementById("mapa-mover").hidden, true);
  const caido = armarGuia({ tramo: tramoOk(), cercana: () => ({ ok: false, mensaje: "No se pudo sugerir una parada: el servidor de rutas no respondió." }) });
  caido.documento.getElementById("mapa-mostrar").click();
  caido.geo.mover(-36.5, -72.2);
  await esperar();
  caido.documento.getElementById("mapa-cercana").click();
  await esperar(); await esperar();
  assert.deepEqual(caido.dibujo.registro.destacadas, []);
  assert.equal(caido.documento.getElementById("mapa-mover").hidden, true);
  assert.match(caido.documento.getElementById("mapa-guia-estado").textContent, /servidor de rutas no respondió/);
});

test("al salir de la página se detiene el seguimiento", async () => {
  const g = armarGuia({ tramo: tramoOk(), cercana: () => ({}) });
  g.documento.getElementById("mapa-mostrar").click();
  g.ventana.escuchas.pagehide();
  assert.equal(g.geo.limpiadas, 1);
});

test("2026-11-22: la X cierra el mensaje; las distancias no lo reabren y un aviso nuevo sí", async () => {
  const g = armarGuia({ tramo: tramoOk(), cercana: () => ({ ok: false, mensaje: "Sin camino sintético." }) });
  const caja = g.documento.getElementById("mapa-guia-caja");
  const cerrar = g.documento.getElementById("mapa-guia-cerrar");
  assert.equal(cerrar.hidden, false, "sin JavaScript la X no aparece; con él, sí");
  g.documento.getElementById("mapa-mostrar").click();
  g.geo.mover(-36.5, -72.2);
  await esperar();
  assert.equal(caja.hidden, false);
  cerrar.click();
  assert.equal(caja.hidden, true);
  assert.equal(g.documento.activeElement, g.documento.getElementById("mapa-detener"), "el foco va al control vigente");
  g.reloj.t = 25000;
  g.geo.mover(metrosAlNorte(-36.5, 300), -72.2);
  await esperar();
  assert.equal(g.pedidos.tramo.length, 2);
  assert.equal(caja.hidden, true, "la distancia se actualiza sin reabrir el mensaje");
  g.documento.getElementById("mapa-cercana").click();
  await esperar();
  assert.equal(caja.hidden, false, "un aviso nuevo vuelve a mostrar el mensaje");
  assert.equal(g.documento.getElementById("mapa-guia-estado").textContent, "Sin camino sintético.");
});

test("2026-11-22: el menú de tres barras abre las pestañas a su derecha y se cierra con Escape o al tocar fuera", () => {
  const documento = new Documento();
  documento.body.appendChild(crear(documento, ["div", { "data-mapa-menu": true },
    ["button", { "data-mapa-menu-boton": true, "aria-expanded": "false", hidden: true }],
    ["div", { "data-mapa-menu-lista": true }, ["a", { href: "/entregas/mis/" }, "Mis entregas"]]]));
  documento.body.appendChild(crear(documento, ["p", { id: "fuera" }, "Mapa"]));
  const menu = mapa.prepararMenu(documento);
  assert.equal(menu.boton.hidden, false);
  assert.equal(menu.lista.hidden, true, "con JavaScript parte cerrado");
  menu.boton.click();
  assert.equal(menu.lista.hidden, false);
  assert.equal(menu.boton.getAttribute("aria-expanded"), "true");
  documento.dispatchEvent(evento("keydown", { key: "Escape" }));
  assert.equal(menu.lista.hidden, true);
  assert.equal(documento.activeElement, menu.boton);
  menu.boton.click();
  documento.getElementById("fuera").click();
  assert.equal(menu.lista.hidden, true);
  assert.equal(menu.boton.getAttribute("aria-expanded"), "false");
  assert.equal(mapa.prepararMenu(new Documento()), null, "sin menú en la página no hace nada");
});
