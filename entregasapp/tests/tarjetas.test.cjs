// Pruebas de static/js/entregas/tarjetas.js (spec 09, enmienda del 2026-11-15, RF-09-16 y RF-09-18).
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const ruta = path.join(__dirname, "../../static/js/entregas/tarjetas.js");
const tarjetas = require(ruta);
const { Documento, crear } = require("./dom_simulado.cjs");

function tarjeta(id, conMapa) {
  return ["article", { id: "parada-" + id, "data-intento": String(id), "data-compacta": true },
    ["h3", {}, "Paciente sintético " + id],
    ["div", { class: "visita-acciones" },
      ["button", { type: "button", "aria-expanded": "false", "aria-controls": "detalle-" + id, "data-expandir": true, hidden: true },
        ["span", { "data-expandir-texto": true }, "Expandir"]]],
    ["div", { id: "detalle-" + id, "data-detalle": true },
      ["p", {}, "Teléfono y recetas"],
      conMapa
        ? ["div", { "data-mapa-tarjeta": true, "data-latitud": "-36.51", "data-longitud": "-72.2", "data-precision": "12", "data-aviso": "aviso-" + id },
          ["p", { class: "mapa-tarjeta-espera" }, "El mapa se carga al expandir la tarjeta."]]
        : ["p", { class: "mapa-tarjeta-vacio" }, "Domicilio sin coordenadas"],
      ["p", { id: "aviso-" + id, hidden: true }]]];
}

function pagina() {
  const documento = new Documento();
  documento.body.appendChild(crear(documento, tarjeta(1, true)));
  documento.body.appendChild(crear(documento, tarjeta(2, false)));
  documento.body.appendChild(crear(documento, tarjeta(3, true)));
  return documento;
}

function mapasSimulados() {
  const dibujados = [];
  return {
    dibujados,
    dibujarPunto(L, documento, contenedor, datos, aviso, fijo) {
      dibujados.push({ contenedor, datos, fijo });
      return { mapa: { invalidateSize() {} } };
    },
  };
}

function almacen(inicial) {
  const datos = new Map(Object.entries(inicial || {}));
  return { getItem: (k) => (datos.has(k) ? datos.get(k) : null), setItem: (k, v) => datos.set(k, v), datos };
}

const TESELAS = { url: "https://teselas.example.invalid/{z}/{x}/{y}.png", atribucion: "Prueba", zoom_maximo: 19 };

test("sin JavaScript todo se ve; al preparar, cada tarjeta queda compacta con «Expandir» visible", () => {
  const documento = pagina();
  assert.equal(documento.getElementById("detalle-1").hidden, false); // así llega del servidor
  assert.equal(documento.querySelector("[data-expandir]").hidden, true);
  tarjetas.preparar(documento, { L: {}, mapas: mapasSimulados(), teselas: TESELAS, dia: "2026-11-16" });
  for (const id of [1, 2, 3]) {
    const boton = documento.querySelector(`#parada-${id} [data-expandir]`);
    assert.equal(boton.hidden, false);
    assert.equal(boton.getAttribute("aria-expanded"), "false");
    assert.equal(boton.getAttribute("aria-controls"), "detalle-" + id);
    assert.equal(documento.getElementById("detalle-" + id).hidden, true);
  }
});

test("expandir dos tarjetas a la vez cambia el texto, aria-expanded y deja el foco en el botón", () => {
  const documento = pagina();
  const mapas = mapasSimulados();
  tarjetas.preparar(documento, { L: {}, mapas, teselas: TESELAS, dia: "d" });
  const uno = documento.querySelector("#parada-1 [data-expandir]");
  const tres = documento.querySelector("#parada-3 [data-expandir]");
  uno.focus();
  uno.click();
  tres.click();
  assert.equal(uno.getAttribute("aria-expanded"), "true");
  assert.equal(tres.getAttribute("aria-expanded"), "true");
  assert.equal(uno.querySelector("[data-expandir-texto]").textContent, "Contraer");
  assert.equal(documento.getElementById("detalle-1").hidden, false);
  assert.equal(documento.getElementById("detalle-3").hidden, false);
  assert.equal(documento.activeElement, uno);
  uno.click();
  assert.equal(uno.getAttribute("aria-expanded"), "false");
  assert.equal(uno.querySelector("[data-expandir-texto]").textContent, "Expandir");
  assert.equal(documento.getElementById("detalle-1").hidden, true);
  assert.equal(documento.getElementById("detalle-3").hidden, false);
});

test("el mapa pequeño se carga solo al expandir, una vez, fijo y sin datos del paciente", () => {
  const documento = pagina();
  const mapas = mapasSimulados();
  tarjetas.preparar(documento, { L: {}, mapas, teselas: TESELAS, dia: "d" });
  assert.equal(mapas.dibujados.length, 0);
  const uno = documento.querySelector("#parada-1 [data-expandir]");
  uno.click();
  assert.equal(mapas.dibujados.length, 1);
  assert.deepEqual(mapas.dibujados[0].datos, { lat: -36.51, lon: -72.2, precision: 12, teselas: TESELAS });
  assert.equal(mapas.dibujados[0].fijo, true); // sin arrastre ni zoom con los dedos: no captura el desplazamiento
  assert.equal(documento.querySelector("#parada-1 .mapa-tarjeta-espera"), null);
  uno.click();
  uno.click();
  assert.equal(mapas.dibujados.length, 1);
  documento.querySelector("#parada-2 [data-expandir]").click(); // sin coordenadas: solo el texto
  assert.equal(mapas.dibujados.length, 1);
  assert.equal(documento.querySelector("#parada-2 .mapa-tarjeta-vacio").textContent, "Domicilio sin coordenadas");
});

test("sin Leaflet o con un error al dibujar, el aviso lo dice con texto", () => {
  const documento = pagina();
  tarjetas.preparar(documento, { L: null, mapas: null, teselas: TESELAS, dia: "d" });
  documento.querySelector("#parada-1 [data-expandir]").click();
  assert.equal(documento.getElementById("aviso-1").hidden, false);
  assert.equal(documento.getElementById("aviso-1").textContent, tarjetas.TEXTOS.sinMapa);
  const otro = pagina();
  tarjetas.preparar(otro, { L: {}, mapas: { dibujarPunto() { throw new Error("sin red"); } }, teselas: TESELAS, dia: "d" });
  otro.querySelector("#parada-3 [data-expandir]").click();
  assert.equal(otro.getElementById("aviso-3").textContent, tarjetas.TEXTOS.sinMapa);
});

test("recuerda las abiertas del día en sessionStorage y tolera un almacenamiento que falla", () => {
  const guardado = almacen();
  const documento = pagina();
  tarjetas.preparar(documento, { L: {}, mapas: mapasSimulados(), teselas: TESELAS, almacen: guardado, dia: "2026-11-16" });
  documento.querySelector("#parada-3 [data-expandir]").click();
  assert.deepEqual(JSON.parse(guardado.datos.get("entregas-tarjetas-abiertas:2026-11-16")), ["3"]);
  const recarga = pagina();
  tarjetas.preparar(recarga, { L: {}, mapas: mapasSimulados(), teselas: TESELAS, almacen: guardado, dia: "2026-11-16" });
  assert.equal(recarga.querySelector("#parada-3 [data-expandir]").getAttribute("aria-expanded"), "true");
  const otroDia = pagina();
  tarjetas.preparar(otroDia, { L: {}, mapas: mapasSimulados(), teselas: TESELAS, almacen: guardado, dia: "2026-11-17" });
  assert.equal(otroDia.querySelector("#parada-3 [data-expandir]").getAttribute("aria-expanded"), "false");
  const roto = { getItem() { throw new Error("bloqueado"); }, setItem() { throw new Error("bloqueado"); } };
  const sinAlmacen = pagina();
  tarjetas.preparar(sinAlmacen, { L: {}, mapas: mapasSimulados(), teselas: TESELAS, almacen: roto, dia: "d" });
  sinAlmacen.querySelector("#parada-1 [data-expandir]").click();
  assert.equal(sinAlmacen.querySelector("#parada-1 [data-expandir]").getAttribute("aria-expanded"), "true");
  assert.deepEqual(tarjetas.leerAbiertas(almacen({ "entregas-tarjetas-abiertas:x": "{malo" }), "x"), []);
});

test("el archivo no hace solicitudes de red", () => {
  const codigo = fs.readFileSync(ruta, "utf8");
  assert.doesNotMatch(codigo, /fetch\(|XMLHttpRequest|sendBeacon/);
});
