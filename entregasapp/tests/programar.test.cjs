// Pruebas de static/js/entregas/programar.js (spec 08, ampliación del 2026-11-13) con DOM, reloj y red simulados.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const test = require("node:test");

const codigo = fs.readFileSync(path.join(__dirname, "../../static/js/entregas/programar.js"), "utf8");

const vaciar = () => new Promise((resolver) => setImmediate(resolver));
async function esperar(veces = 4) {
  for (let i = 0; i < veces; i += 1) await vaciar();
}

// Reloj manual: setTimeout solo corre al avanzar.
function crearReloj() {
  let ahora = 0;
  let siguiente = 1;
  const pendientes = new Map();
  return {
    setTimeout(funcion, ms) { const id = siguiente++; pendientes.set(id, { funcion, en: ahora + ms }); return id; },
    clearTimeout(id) { pendientes.delete(id); },
    avanzar(ms) {
      ahora += ms;
      for (const [id, tarea] of [...pendientes]) {
        if (tarea.en <= ahora) { pendientes.delete(id); tarea.funcion(); }
      }
    },
  };
}

// Red manual: cada fetch queda pendiente hasta que la prueba lo responde.
function crearRed() {
  const llamadas = [];
  function fetch(url, opciones) {
    return new Promise((resolver, rechazar) => {
      llamadas.push({ url, opciones, cuerpo: Object.fromEntries(opciones.body), resolver, rechazar });
    });
  }
  return { fetch, llamadas };
}

const respuestaHtml = (html, status = 200) => ({ ok: status < 400, status, text: async () => html });
const respuestaJson = (datos, status = 200) => ({ ok: status < 400, status, json: async () => datos });

// Fragmento simulado: «total|id,id,id».
function fragmento(total, ids) {
  return `${total}|${ids.join(",")}`;
}

function crearLista(inicial) {
  const lista = {
    casillasActuales: [],
    soloJs: [],
    total: 0,
    _html: "",
    set innerHTML(html) {
      this._html = html;
      const [total, ids] = html.split("|");
      this.total = Number(total);
      this.casillasActuales = (ids ? ids.split(",") : []).filter(Boolean).map((id) => ({ dataset: { paciente: id }, checked: false }));
      this.soloJs = [{ hidden: true }];
    },
    get innerHTML() { return this._html; },
    querySelector(selector) {
      return selector === "[data-total]" ? { dataset: { total: String(this.total) } } : null;
    },
    querySelectorAll(selector) {
      if (selector === "input[data-paciente]") return this.casillasActuales;
      if (selector === "[data-solo-js]") return this.soloJs;
      return [];
    },
  };
  lista.innerHTML = inicial;
  return lista;
}

function cargar(globales) {
  let alIniciar;
  const fabricas = {};
  const contexto = {
    document: { addEventListener(evento, funcion) { if (evento === "alpine:init") alIniciar = funcion; } },
    Alpine: { data(nombre, funcion) { fabricas[nombre] = funcion; } },
    URLSearchParams,
    AbortController,
    ...globales,
  };
  vm.runInNewContext(codigo, contexto);
  alIniciar();
  return fabricas;
}

function prepararLista({ total = 3, ids = ["1", "2", "3"] } = {}) {
  const reloj = crearReloj();
  const red = crearRed();
  const fabricas = cargar({ setTimeout: reloj.setTimeout, clearTimeout: reloj.clearTimeout, fetch: red.fetch });
  const campos = {
    csrfmiddlewaretoken: { name: "csrfmiddlewaretoken", value: "ficha" },
    buscar: { name: "buscar", value: "" }, sector: { name: "sector", value: "" }, motivo: { name: "motivo", value: "" },
    estado: { name: "estado", value: "" }, localidad: { name: "localidad", value: "" },
  };
  const componente = fabricas.programar();
  componente.$root = { elements: campos, dataset: { urlLista: "/entregas/programar/lista/" } };
  componente.$refs = {
    lista: crearLista(fragmento(total, ids)),
    estado: { textContent: "" }, seleccion: { textContent: "" }, programar: { textContent: "" }, ocultos: { innerHTML: "" },
  };
  componente.init();
  const escribir = (campo, valor) => {
    campos[campo].value = valor;
    componente.cambio({ type: campo === "buscar" ? "input" : "change", target: campos[campo] });
  };
  const marcar = (id, marcada = true) => {
    const casilla = componente.$refs.lista.casillasActuales.find((c) => c.dataset.paciente === id);
    casilla.checked = marcada;
    componente.cambio({ type: "change", target: casilla });
  };
  const enviar = (submitter) => {
    let prevenido = false;
    componente.enviar({ submitter, preventDefault() { prevenido = true; } });
    return prevenido;
  };
  return { componente, reloj, red, escribir, marcar, enviar, campos };
}

test("espera 300 ms después de la última tecla y envía la búsqueda por POST, no en la URL", async () => {
  const { componente, reloj, red, escribir } = prepararLista();
  escribir("buscar", "G");
  reloj.avanzar(200);
  escribir("buscar", "Go");
  reloj.avanzar(200);
  assert.equal(red.llamadas.length, 0);
  escribir("buscar", "Gonz");
  reloj.avanzar(299);
  assert.equal(red.llamadas.length, 0);
  reloj.avanzar(1);
  assert.equal(red.llamadas.length, 1);
  const llamada = red.llamadas[0];
  assert.equal(llamada.url, "/entregas/programar/lista/");
  assert.equal(llamada.opciones.method, "POST");
  assert.equal(llamada.cuerpo.buscar, "Gonz");
  assert.equal(llamada.cuerpo.pagina, "1");
  assert.equal(llamada.opciones.headers["X-CSRFToken"], "ficha");
  llamada.resolver(respuestaHtml(fragmento(1, ["7"])));
  await esperar();
  assert.equal(componente.$refs.estado.textContent, "1 paciente del reparto");
  assert.equal(componente.$refs.lista.soloJs[0].hidden, false);
});

test("sin cambios reales en los filtros no vuelve a pedir la lista", () => {
  const { reloj, red, escribir } = prepararLista();
  escribir("buscar", "");
  reloj.avanzar(400);
  assert.equal(red.llamadas.length, 0);
});

test("cancela la solicitud anterior y descarta las respuestas que llegan fuera de orden", async () => {
  const { componente, red, escribir, reloj } = prepararLista();
  escribir("buscar", "Ana");
  reloj.avanzar(300);
  escribir("sector", "verde");
  reloj.avanzar(300);
  assert.equal(red.llamadas.length, 2);
  assert.equal(red.llamadas[0].opciones.signal.aborted, true);
  red.llamadas[1].resolver(respuestaHtml(fragmento(2, ["4", "5"])));
  await esperar();
  red.llamadas[0].resolver(respuestaHtml(fragmento(9, ["1"])));
  await esperar();
  assert.equal(componente.$refs.lista.total, 2);
  assert.equal(componente.$refs.estado.textContent, "2 pacientes del reparto");
});

test("la selección se conserva al cambiar de página y de búsqueda", async () => {
  const { componente, red, marcar, enviar } = prepararLista({ total: 6, ids: ["1", "2", "3"] });
  marcar("1");
  marcar("2");
  assert.equal(componente.$refs.seleccion.textContent, "2 seleccionados.");
  assert.equal(enviar({ name: "pagina", value: "2", dataset: {} }), true);
  assert.equal(red.llamadas[0].cuerpo.pagina, "2");
  red.llamadas[0].resolver(respuestaHtml(fragmento(6, ["4", "5", "6"])));
  await esperar();
  marcar("5");
  assert.equal(componente.$refs.programar.textContent, "Programar seleccionados (3)");
  enviar({ name: "pagina", value: "1", dataset: {} });
  red.llamadas[1].resolver(respuestaHtml(fragmento(6, ["1", "2", "3"])));
  await esperar();
  const marcadas = componente.$refs.lista.casillasActuales.filter((c) => c.checked).map((c) => c.dataset.paciente);
  assert.deepEqual(marcadas, ["1", "2"]);
  marcar("1", false);
  assert.equal(componente.$refs.seleccion.textContent, "2 seleccionados.");
  assert.equal(enviar({ dataset: { accion: "programar" } }), false);
  assert.equal(componente.$refs.ocultos.innerHTML, '<input type="hidden" name="ids" value="2"><input type="hidden" name="ids" value="5">');
});

test("«Seleccionar los N filtrados» se anula al cambiar un filtro y lo dice con texto", async () => {
  const { componente, red, escribir, reloj, enviar } = prepararLista({ total: 120, ids: ["1", "2"] });
  assert.equal(enviar({ name: "todos", value: "1", dataset: { accion: "todos" } }), true);
  assert.equal(componente.$refs.seleccion.textContent, "Seleccionaste los 120 filtrados.");
  assert.ok(componente.$refs.lista.casillasActuales.every((c) => c.checked));
  assert.equal(componente.$refs.programar.textContent, "Programar seleccionados (120)");
  escribir("sector", "verde");
  reloj.avanzar(300);
  red.llamadas[0].resolver(respuestaHtml(fragmento(40, ["1"])));
  await esperar();
  assert.match(componente.$refs.estado.textContent, /^40 pacientes del reparto\. Se quitó la selección de todos los filtrados/);
  assert.equal(componente.todos, false);
  assert.equal(componente.$refs.seleccion.textContent, "Ningún paciente seleccionado.");
});

test("con «todos» activo, programar envía todos=1; si el filtro cambió sin esperar, se anula antes de enviar", () => {
  const { componente, enviar, campos } = prepararLista({ total: 50, ids: ["1"] });
  enviar({ dataset: { accion: "todos" } });
  assert.equal(enviar({ dataset: { accion: "programar" } }), false);
  assert.equal(componente.$refs.ocultos.innerHTML, '<input type="hidden" name="todos" value="1">');
  campos.motivo.value = "postrado";
  assert.equal(enviar({ dataset: { accion: "programar" } }), true);
  assert.match(componente.$refs.seleccion.textContent, /Se quitó la selección de todos los filtrados/);
});

test("sin selección no envía y lo explica; «Seleccionar esta página» y «Quitar selección»", () => {
  const { componente, enviar } = prepararLista();
  assert.equal(enviar({ dataset: { accion: "programar" } }), true);
  assert.match(componente.$refs.seleccion.textContent, /Marca al menos un paciente/);
  componente.clic({ target: { closest: () => ({}) } });
  assert.equal(componente.$refs.seleccion.textContent, "3 seleccionados.");
  componente.quitarSeleccion();
  assert.equal(componente.$refs.seleccion.textContent, "Ningún paciente seleccionado.");
  assert.ok(componente.$refs.lista.casillasActuales.every((c) => !c.checked));
});

test("un error de red se dice con texto y «Reintentar» repite la misma página", async () => {
  const { componente, red, enviar } = prepararLista();
  enviar({ name: "pagina", value: "3", dataset: {} });
  red.llamadas[0].rechazar(new TypeError("Failed to fetch"));
  await esperar();
  assert.equal(componente.error, true);
  assert.match(componente.$refs.estado.textContent, /No pudimos actualizar la lista/);
  componente.reintentar();
  assert.equal(red.llamadas[1].cuerpo.pagina, "3");
  red.llamadas[1].resolver(respuestaHtml(fragmento(3, ["1"])));
  await esperar();
  assert.equal(componente.error, false);
});

// Confirmación por tramos -------------------------------------------------------------------------------------

function prepararLote({ programables = 60, total = 64, omitidos = 4 } = {}) {
  const red = crearRed();
  const fabricas = cargar({ fetch: red.fetch });
  const componente = fabricas.programarLote();
  const formulario = { elements: { csrfmiddlewaretoken: { value: "ficha" }, contexto: { value: "firmado" } } };
  componente.$root = {
    dataset: { url: "/entregas/programar/varios/confirmar/", programables: String(programables), total: String(total),
               tramo: "25", omitidos: String(omitidos), urlProgramacion: "/entregas/programacion/?encargado=3" },
    querySelector(selector) {
      if (selector === "form") return formulario;
      const id = /data-paciente="(\d+)"/.exec(selector);
      return id ? { textContent: ` Apellido ${id[1]}, Nombre ` } : null;
    },
  };
  componente.init();
  return { componente, red };
}

const programados = (desde, hasta) => Array.from({ length: hasta - desde }, (_, i) => ({ paciente: desde + i + 1, estado: "programado", entrega: 900 + i, recetas: 1 }));

test("envía los tramos en orden, actualiza el avance y termina con «Se programaron X de Y»", async () => {
  const { componente, red } = prepararLote();
  const promesa = componente.confirmar();
  await esperar();
  assert.equal(red.llamadas.length, 1);
  assert.deepEqual([red.llamadas[0].cuerpo.desde, red.llamadas[0].cuerpo.hasta, red.llamadas[0].cuerpo.contexto], ["0", "25", "firmado"]);
  red.llamadas[0].resolver(respuestaJson({ resultados: programados(0, 25) }));
  await esperar();
  assert.equal(componente.hechos, 25);
  assert.equal(componente.estado, "Programando 25 de 60");
  assert.deepEqual([red.llamadas[1].cuerpo.desde, red.llamadas[1].cuerpo.hasta], ["25", "50"]);
  const tramo = programados(25, 50);
  tramo[3] = { paciente: 29, estado: "omitido", motivo: "Ya tiene una entrega abierta" };
  red.llamadas[1].resolver(respuestaJson({ resultados: tramo }));
  await esperar();
  assert.deepEqual([red.llamadas[2].cuerpo.desde, red.llamadas[2].cuerpo.hasta], ["50", "60"]);
  red.llamadas[2].resolver(respuestaJson({ resultados: programados(50, 60) }));
  await promesa;
  assert.equal(red.llamadas.length, 3);
  assert.equal(componente.terminado, true);
  assert.equal(componente.estado, "Se programaron 59 de 64. No se programaron 5: revisa el motivo de cada uno en la lista.");
  assert.deepEqual(JSON.parse(JSON.stringify(componente.omitidosNuevos)), [{ paciente: 29, nombre: "Apellido 29, Nombre", motivo: "Ya tiene una entrega abierta" }]);
  await componente.confirmar();
  assert.equal(red.llamadas.length, 3); // un doble clic al final no reenvía
});

test("ante un corte se detiene y «Reintentar» sigue desde el primer tramo sin respuesta", async () => {
  const { componente, red } = prepararLote({ programables: 40, total: 40, omitidos: 0 });
  const primera = componente.confirmar();
  await esperar();
  red.llamadas[0].resolver(respuestaJson({ resultados: programados(0, 25) }));
  await esperar();
  red.llamadas[1].rechazar(new TypeError("Failed to fetch"));
  await primera;
  assert.equal(componente.interrumpido, true);
  assert.match(componente.estado, /^Se interrumpió en 25 de 40\. Revisa la conexión/);
  assert.equal(componente.ocupado, false);
  const segunda = componente.confirmar();
  await esperar();
  assert.deepEqual([red.llamadas[2].cuerpo.desde, red.llamadas[2].cuerpo.hasta], ["25", "40"]);
  red.llamadas[2].resolver(respuestaJson({ resultados: programados(25, 40) }));
  await segunda;
  assert.equal(componente.estado, "Se programaron 40 de 40.");
});

test("un rechazo del servidor se muestra con su texto y no sigue con los tramos", async () => {
  const { componente, red } = prepararLote({ programables: 30, total: 30, omitidos: 0 });
  const promesa = componente.confirmar();
  await esperar();
  red.llamadas[0].resolver(respuestaJson({ error: "La revisión no es válida o fue alterada. Vuelve a revisar el lote." }, 400));
  await promesa;
  assert.equal(red.llamadas.length, 1);
  assert.equal(componente.estado, "Se interrumpió en 0 de 30. La revisión no es válida o fue alterada. Vuelve a revisar el lote.");
});
