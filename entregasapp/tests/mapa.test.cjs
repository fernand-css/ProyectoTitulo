// Spec 09 (RF-09-08, RF-09-11 y RF-09-14): mapa.js con un Leaflet y un DOM simulados.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const ruta = path.join(__dirname, "../../static/js/entregas/mapa.js");
const mapa = require(ruta);

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
  linea: [[-36.498877, -72.21236], [-36.49, -72.21], [-36.48, -72.20], [-36.498877, -72.21236]],
  total_km: "4,2",
  sin_marcador: 1,
  consulta: false,
};

test("dibuja el CESFAM, las paradas con el número de la lista, las registradas y la línea punteada", () => {
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
  const [linea] = L.registro.lineas;
  assert.deepEqual(linea.puntos, DATOS.linea);
  assert.equal(linea.opciones.className, "linea-recorrido");
  assert.ok(linea.opciones.dashArray);
  assert.equal(L.registro.encuadres.length, 1);
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
  assert.deepEqual(enlaces.map((a) => [a.textContent, a.href]), [["Ver domicilio", "/entregas/domicilios/paciente/8/"]]);
  const completo = mapa.resumenParada(documento, DATOS.paradas[0]);
  assert.deepEqual(completo.hijos.at(-1).hijos.map((a) => a.textContent), ["Registrar", "Ir a esta parada", "Ver domicilio"]);
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

test("el destino de «Ir a esta parada» mueve mi posición, su precisión y la línea", () => {
  const L = leafletFalso();
  const documento = documentoFalso();
  const guia = mapa.dibujarDestino(L, documento, documento.crear("div"), { lat: -36.5, lon: -72.2, numero: 3, teselas: DATOS.teselas }, null);
  guia.actualizar(-36.51, -72.21, 15);
  guia.actualizar(-36.505, -72.205, 8);
  assert.deepEqual(L.registro.lineas[0].puntos, [[-36.505, -72.205], [-36.5, -72.2]]);
  assert.equal(L.registro.circulos[0].opciones.radius, 8);
  assert.equal(L.registro.marcadores.length, 2);
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

test("el módulo no hace solicitudes de red ni usa innerHTML", () => {
  const codigo = fs.readFileSync(ruta, "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  assert.doesNotMatch(codigo, /\bfetch\s*\(|XMLHttpRequest|sendBeacon|WebSocket|innerHTML|insertAdjacentHTML/);
});
