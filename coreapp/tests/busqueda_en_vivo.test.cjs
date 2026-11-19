// Pruebas de static/js/busqueda_en_vivo.js con DOM, reloj y red simulados (datos sintéticos).
const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const { Documento, crear, evento } = require(path.join(__dirname, "../../entregasapp/tests/dom_simulado.cjs"));
const api = require(path.join(__dirname, "../../static/js/busqueda_en_vivo.js"));

// Lo que el DOM simulado no trae y el script usa: nombre y tipo de los controles, elements, replaceWith y contains.
const Nodo = Object.getPrototypeOf(new Documento().createElement("div"));
Object.defineProperties(Nodo, {
  name: { configurable: true, get() { return this.getAttribute("name") || ""; } },
  type: {
    configurable: true,
    get() {
      const tipo = this.getAttribute("type");
      if (tipo) return tipo;
      return this.tagName === "BUTTON" ? "submit" : this.tagName === "INPUT" ? "text" : "";
    },
    set(valor) { this.setAttribute("type", valor); },
  },
  elements: { configurable: true, get() { return this.querySelectorAll("input, button, select, textarea"); } },
});
Nodo.replaceWith = function (nuevo) { this.parentNode.replaceChild(nuevo, this); };
Nodo.contains = function (otro) {
  for (let nodo = otro; nodo; nodo = nodo.parentNode) if (nodo === this) return true;
  return false;
};

const vaciar = () => new Promise((resolver) => setImmediate(resolver));
async function esperar(veces = 4) {
  for (let i = 0; i < veces; i += 1) await vaciar();
}

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

// Red manual: cada fetch queda pendiente hasta que la prueba lo responde; abortar lo rechaza como el navegador.
function crearRed() {
  const llamadas = [];
  function fetch(url, opciones) {
    return new Promise((resolver, rechazar) => {
      const llamada = { url, opciones, cuerpo: opciones.body, resolver, rechazar };
      if (opciones.signal) {
        opciones.signal.addEventListener("abort", () => rechazar(Object.assign(new Error("abortada"), { name: "AbortError" })));
      }
      llamadas.push(llamada);
    });
  }
  return { fetch, llamadas };
}

const respuesta = (html, extra = {}) => ({ ok: true, status: 200, redirected: false, url: "", text: async () => html, ...extra });

const TOKEN = "token-sintetico";
const FILTROS = [["", "Todos"], ["sin_vigente", "Sin receta vigente"]];

function filtros(actual) {
  return ["div", { "data-zona": "filtros" },
    ["div", { class: "filtros", role: "group" },
      ...FILTROS.map(([clave, texto]) => ["button", {
        class: "filtro", type: "submit", name: "filtro", value: clave, "aria-pressed": String(clave === actual),
      }, texto])]];
}

function resultados(anuncio, { buscar = "", siguiente = null } = {}) {
  const nav = ["nav", { class: "paginacion" }];
  if (siguiente) {
    nav.push(["form", { method: "post", "data-en-vivo": "pagina" },
      ["input", { type: "hidden", name: "csrfmiddlewaretoken", value: TOKEN }],
      ["input", { type: "hidden", name: "buscar", value: buscar }],
      ["input", { type: "hidden", name: "filtro", value: "" }],
      ["button", { type: "submit", name: "pagina", value: String(siguiente) }, "Página siguiente"]]);
  }
  return ["div", { "data-zona": "resultados" }, ["p", { "data-anuncio": true }, anuncio], nav];
}

// Lee el formulario como lo haría FormData: los campos con nombre, sin botones.
function leer(formulario) {
  return formulario.elements
    .filter((campo) => campo.name && !["submit", "button", "reset"].includes(campo.type))
    .map((campo) => [campo.name, campo.value]);
}

function preparar({ abortar = true, conSelect = false } = {}) {
  const d = new Documento();
  const reloj = crearReloj();
  const red = crearRed();
  const navegaciones = [];
  const formulario = crear(d, ["form", { method: "post", role: "search", "data-en-vivo": "busqueda" },
    ["input", { type: "hidden", name: "csrfmiddlewaretoken", value: TOKEN }],
    ["label", { for: "id_buscar" }, "Buscar por RUT o nombre"],
    ["p", { id: "ayuda-buscar", class: "campo-ayuda", "data-solo-js": true, hidden: true }, "La lista se actualiza mientras escribes."],
    ["input", { type: "search", name: "buscar", id: "id_buscar", value: "" }],
    ...(conSelect ? [["select", { name: "sector", id: "id_sector", value: "" }]] : []),
    ["button", { class: "boton", type: "submit", name: "filtro", value: "" }, "Buscar"],
    ["input", { type: "hidden", name: "pagina", value: "1" }],
    filtros("")]);
  formulario.action = "/recetas/pacientes/";
  d.body.appendChild(formulario);
  d.body.appendChild(crear(d, resultados("Mostrando del 1 al 20 de 670 pacientes, por apellido.", { siguiente: 2 })));
  // El fragmento que «devuelve el servidor» se arma con la misma descripción que la página.
  const parsear = (html) => JSON.parse(html).map((descripcion) => crear(d, descripcion));
  const vista = api.iniciar(d, {
    fetch: red.fetch, setTimeout: reloj.setTimeout, clearTimeout: reloj.clearTimeout,
    AbortController: abortar ? AbortController : undefined, leer, parsear, navegar: (url) => navegaciones.push(url),
  });
  const campo = d.querySelector("#id_buscar");
  return { d, reloj, red, vista, formulario, campo, navegaciones };
}

function escribir(campo, texto, tipo = "input") {
  campo.value = texto;
  campo.dispatchEvent(evento(tipo, { target: campo }));
}

function enviar(formulario, submitter) {
  const ev = evento("submit", { target: formulario, submitter });
  formulario.dispatchEvent(ev);
  return ev;
}

const html = (...zonas) => JSON.stringify(zonas);

test("lo que se envía: el filtro vigente del botón «Buscar», sin la página; los botones de filtro lo actualizan", () => {
  const { formulario } = preparar();
  const buscar = api.botonPorOmision(formulario);
  assert.equal(buscar.textContent, "Buscar");
  assert.deepEqual(api.paresBusqueda(formulario, leer, null), [["csrfmiddlewaretoken", TOKEN], ["buscar", ""], ["filtro", ""]]);
  const sinVigente = formulario.querySelector('button[value="sin_vigente"]');
  assert.deepEqual(api.paresBusqueda(formulario, leer, sinVigente).filter((par) => par[0] === "filtro"), [["filtro", "sin_vigente"]]);
  assert.equal(buscar.value, "sin_vigente", "Enter conserva el filtro recién elegido");
  assert.equal(api.claveDe([["csrfmiddlewaretoken", "x"], ["buscar", "a"], ["pagina", "3"]]), api.claveDe([["buscar", "a"]]));
});

test("al iniciar muestra la ayuda, la asocia al campo y prepara la región de estado y el aviso de error", () => {
  const { d, vista, campo } = preparar();
  const ayuda = d.querySelector("#ayuda-buscar");
  assert.equal(ayuda.hidden, false);
  assert.equal(campo.getAttribute("aria-describedby"), "ayuda-buscar");
  assert.equal(vista.estado.getAttribute("role"), "status");
  assert.equal(vista.error.hidden, true);
  assert.equal(vista.error.textContent.includes("Reintentar"), true);
  assert.equal(api.iniciar(new Documento(), {}), null, "sin buscador no hace nada");
});

test("escribir espera 300 ms, pide una sola vez por POST con la cabecera y no repite la misma búsqueda", async () => {
  const { d, reloj, red, vista, campo } = preparar();
  campo.focus();
  escribir(campo, "g");
  reloj.avanzar(200);
  escribir(campo, "gon");
  reloj.avanzar(299);
  assert.equal(red.llamadas.length, 0);
  reloj.avanzar(1);
  assert.equal(red.llamadas.length, 1);
  const [llamada] = red.llamadas;
  assert.equal(llamada.url, "/recetas/pacientes/");
  assert.equal(llamada.opciones.method, "POST");
  assert.equal(llamada.opciones.headers[api.CABECERA], "1");
  assert.equal(llamada.opciones.headers["X-CSRFToken"], TOKEN);
  assert.equal(llamada.cuerpo.get("buscar"), "gon");
  assert.equal(llamada.cuerpo.has("pagina"), false, "una búsqueda nueva vuelve a la primera página");
  assert.equal(d.querySelector('[data-zona="resultados"]').getAttribute("aria-busy"), "true");

  llamada.resolver(respuesta(html(filtros(""), resultados("3 pacientes coinciden con «gon».", { buscar: "gon" }))));
  await esperar();
  assert.equal(d.querySelector("[data-anuncio]").textContent, "3 pacientes coinciden con «gon».");
  assert.equal(vista.estado.textContent, "3 pacientes coinciden con «gon».");
  assert.equal(d.activeElement, campo, "el foco y el cursor se quedan en el campo");
  assert.equal(d.querySelector('[data-zona="resultados"]').hasAttribute("aria-busy"), false);

  escribir(campo, "gon", "change"); // al salir del campo
  reloj.avanzar(300);
  assert.equal(red.llamadas.length, 1);
});

test("cambiar una lista desplegable también actualiza", () => {
  const { d, reloj, red } = preparar({ conSelect: true });
  const sector = d.querySelector("#id_sector");
  sector.value = "verde";
  sector.dispatchEvent(evento("change", { target: sector }));
  reloj.avanzar(300);
  assert.equal(red.llamadas.length, 1);
  assert.equal(red.llamadas[0].cuerpo.get("sector"), "verde");
});

test("cancela la solicitud anterior y descarta las respuestas que llegan tarde", async () => {
  for (const abortar of [true, false]) {
    const { d, reloj, red, vista, campo } = preparar({ abortar });
    escribir(campo, "a");
    reloj.avanzar(300);
    escribir(campo, "ab");
    reloj.avanzar(300);
    assert.equal(red.llamadas.length, 2);
    red.llamadas[1].resolver(respuesta(html(resultados("Con «ab».", { buscar: "ab" }))));
    await esperar();
    red.llamadas[0].resolver(respuesta(html(resultados("Con «a».", { buscar: "a" }))));
    await esperar();
    assert.equal(d.querySelector("[data-anuncio]").textContent, "Con «ab».");
    assert.equal(vista.estado.textContent, "Con «ab».");
    assert.equal(vista.error.hidden, true, "la cancelada no se informa como error");
  }
});

test("si falla lo dice, ofrece «Reintentar» y reenvía lo mismo", async () => {
  const { d, reloj, red, vista, campo } = preparar();
  escribir(campo, "gon");
  reloj.avanzar(300);
  red.llamadas[0].resolver(respuesta("", { ok: false, status: 500 }));
  await esperar();
  assert.equal(vista.error.hidden, false);
  assert.equal(vista.estado.textContent, api.MENSAJE_ERROR);
  assert.equal(d.querySelector('[data-zona="resultados"]').hasAttribute("aria-busy"), false);

  vista.reintentar.click();
  assert.equal(red.llamadas.length, 2);
  assert.equal(red.llamadas[1].cuerpo.toString(), red.llamadas[0].cuerpo.toString());
  assert.equal(vista.error.hidden, true);
  red.llamadas[1].resolver(respuesta(html(resultados("3 pacientes coinciden con «gon».", { buscar: "gon" }))));
  await esperar();
  assert.equal(vista.estado.textContent, "3 pacientes coinciden con «gon».");

  // Una respuesta sin zonas (p. ej. otra página) también es un error, no una lista vacía.
  escribir(campo, "gonz");
  reloj.avanzar(300);
  red.llamadas[2].resolver(respuesta("[]"));
  await esperar();
  assert.equal(vista.error.hidden, false);
});

test("si la sesión venció, sigue la redirección al inicio de sesión", async () => {
  const { reloj, red, campo, navegaciones } = preparar();
  escribir(campo, "gon");
  reloj.avanzar(300);
  red.llamadas[0].resolver(respuesta("", { redirected: true, url: "/usuarios/entrar/?next=/recetas/pacientes/" }));
  await esperar();
  assert.deepEqual(navegaciones, ["/usuarios/entrar/?next=/recetas/pacientes/"]);
});

test("un botón de filtro se envía al instante y el foco vuelve al mismo botón dibujado de nuevo", async () => {
  const { d, red, vista, formulario } = preparar();
  const boton = formulario.querySelector('button[value="sin_vigente"]');
  boton.focus();
  const ev = enviar(formulario, boton);
  assert.equal(ev.defaultPrevented, true);
  assert.equal(red.llamadas.length, 1);
  assert.deepEqual(red.llamadas[0].cuerpo.getAll("filtro"), ["sin_vigente"]);
  red.llamadas[0].resolver(respuesta(html(filtros("sin_vigente"), resultados("12 pacientes sin receta vigente."))));
  await esperar();
  const zona = d.querySelector('[data-zona="filtros"]');
  assert.notEqual(d.activeElement, boton);
  assert.equal(zona.contains(d.activeElement), true);
  assert.equal(d.activeElement.value, "sin_vigente");
  assert.equal(d.activeElement.getAttribute("aria-pressed"), "true");
  assert.equal(vista.estado.textContent, "12 pacientes sin receta vigente.");
});

test("Enter o «Buscar» actualizan al instante, sin esperar la pausa", () => {
  const { reloj, red, formulario, campo } = preparar();
  escribir(campo, "gon");
  enviar(formulario, api.botonPorOmision(formulario));
  assert.equal(red.llamadas.length, 1);
  reloj.avanzar(300);
  assert.equal(red.llamadas.length, 1, "la espera pendiente se cancela");
});

test("la paginación cambia de página sin recargar y lleva el foco al resumen", async () => {
  const { d, red, vista, campo } = preparar();
  const estadoAntes = vista.estado.textContent;
  const formularioPagina = d.querySelector('form[data-en-vivo="pagina"]');
  const siguiente = formularioPagina.querySelector("button");
  siguiente.focus();
  const ev = enviar(formularioPagina, siguiente);
  assert.equal(ev.defaultPrevented, true);
  assert.equal(red.llamadas[0].cuerpo.get("pagina"), "2");
  assert.equal(red.llamadas[0].cuerpo.get("buscar"), "");
  red.llamadas[0].resolver(respuesta(html(resultados("Mostrando del 21 al 40 de 670 pacientes, por apellido.", { siguiente: 3 }))));
  await esperar();
  const resumen = d.querySelector("[data-anuncio]");
  assert.equal(d.activeElement, resumen);
  assert.equal(resumen.getAttribute("tabindex"), "-1");
  assert.equal(vista.estado.textContent, estadoAntes, "el lector lee el resumen enfocado; no se anuncia dos veces");
  assert.notEqual(d.activeElement, campo);
});

test("si se escribió algo y se pulsa otra página antes de la pausa, se busca lo nuevo desde la primera", () => {
  const { d, red, campo } = preparar();
  escribir(campo, "gonz");
  const formularioPagina = d.querySelector('form[data-en-vivo="pagina"]');
  enviar(formularioPagina, formularioPagina.querySelector("button"));
  assert.equal(red.llamadas.length, 1);
  assert.equal(red.llamadas[0].cuerpo.get("buscar"), "gonz");
  assert.equal(red.llamadas[0].cuerpo.has("pagina"), false);
});

test("un botón con formaction propio se envía como siempre", () => {
  const { d, red, formulario } = preparar();
  const otro = crear(d, ["button", { type: "submit", formaction: "/otra/" }, "Otra acción"]);
  formulario.appendChild(otro);
  const ev = enviar(formulario, otro);
  assert.equal(ev.defaultPrevented, false);
  assert.equal(red.llamadas.length, 0);
});

test("solo cuentan los campos que la persona escribe o elige", () => {
  const d = new Documento();
  const campo = (descripcion) => crear(d, descripcion);
  assert.equal(api.esCampoDeBusqueda(campo(["input", { type: "search", name: "buscar" }])), true);
  assert.equal(api.esCampoDeBusqueda(campo(["select", { name: "estado" }])), true);
  assert.equal(api.esCampoDeBusqueda(campo(["input", { type: "hidden", name: "accion" }])), false);
  assert.equal(api.esCampoDeBusqueda(campo(["input", { type: "hidden", name: "pagina" }])), false);
  assert.equal(api.esCampoDeBusqueda(campo(["input", { type: "text", name: "csrfmiddlewaretoken" }])), false);
  assert.equal(api.esCampoDeBusqueda(campo(["input", { type: "search" }])), false);
});
