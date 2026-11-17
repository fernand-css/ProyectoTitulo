// Pruebas de static/js/entregas/orden.js (spec 09, enmienda del 2026-11-15, RF-09-17): flechas y arrastre propio.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const ruta = path.join(__dirname, "../../static/js/entregas/orden.js");
const orden = require(ruta);
const { Documento, crear, evento } = require("./dom_simulado.cjs");

// Máquina del arrastre ----------------------------------------------------------------------------------------

function relojSimulado() {
  let siguiente = 1;
  const tareas = new Map();
  const cuadros = new Map();
  return {
    programar(fn, ms) { const id = siguiente++; tareas.set(id, { fn, ms }); return id; },
    cancelar(id) { tareas.delete(id); },
    cuadro(fn) { const id = siguiente++; cuadros.set(id, fn); return id; },
    cancelarCuadro(id) { cuadros.delete(id); },
    pasar(ms) { [...tareas].forEach(([id, t]) => { if (t.ms <= ms) { tareas.delete(id); t.fn(); } }); },
    cuadroSiguiente() { const lista = [...cuadros]; cuadros.clear(); lista.forEach(([, fn]) => fn()); },
    pendientes: () => tareas.size,
  };
}

function adaptadorSimulado(centros, alto) {
  const registro = { huecos: [], desplazado: [], devuelto: 0, soltado: [], anuncios: [], iniciado: 0, siguiendo: [] };
  return {
    registro,
    iniciar() { registro.iniciado += 1; return 1; }, // la tarjeta arrastrada es la segunda
    seguir(y) { registro.siguiendo.push(y); },
    centros: () => centros,
    colocarHueco(i) { registro.huecos.push(i); },
    desplazar(dy) { registro.desplazado.push(dy); },
    alto: () => alto,
    dentro: (x, y) => x >= 0 && x <= 400 && y >= 0 && y <= 1000,
    soltarEn(i) { registro.soltado.push(i); },
    devolver() { registro.devuelto += 1; },
    anunciar(texto) { registro.anuncios.push(texto); },
  };
}

test("con mouse el arrastre empieza al presionar; en pantalla táctil, tras mantener 300 ms", () => {
  const reloj = relojSimulado();
  const mouse = adaptadorSimulado([100, 300], 800);
  const arrastre = orden.crearArrastre(mouse, reloj);
  arrastre.presionar({ x: 380, y: 200, tipo: "mouse" });
  assert.equal(arrastre.estado(), "arrastrando");
  assert.equal(mouse.registro.iniciado, 1);
  const toque = adaptadorSimulado([100, 300], 800);
  const largo = orden.crearArrastre(toque, reloj);
  largo.presionar({ x: 380, y: 200, tipo: "touch" });
  assert.equal(largo.estado(), "esperando");
  assert.equal(toque.registro.iniciado, 0);
  assert.equal(largo.mover({ x: 382, y: 205 }), false); // pequeño temblor: sigue esperando
  reloj.pasar(orden.ESPERA_TOQUE_MS);
  assert.equal(largo.estado(), "arrastrando");
  assert.equal(toque.registro.iniciado, 1);
});

test("si el dedo se mueve antes de los 300 ms es desplazamiento de la página y no arrastra", () => {
  const reloj = relojSimulado();
  const ad = adaptadorSimulado([100, 300], 800);
  const arrastre = orden.crearArrastre(ad, reloj);
  arrastre.presionar({ x: 380, y: 200, tipo: "touch" });
  assert.equal(arrastre.mover({ x: 380, y: 240 }), false);
  assert.equal(arrastre.estado(), "libre");
  assert.equal(reloj.pendientes(), 0);
  reloj.pasar(1000);
  assert.equal(ad.registro.iniciado, 0);
  assert.equal(arrastre.soltar({ x: 380, y: 240 }), null);
});

test("el hueco sigue al puntero entre las otras tarjetas y soltar envía la posición nueva", () => {
  const ad = adaptadorSimulado([100, 300, 500], 900);
  const arrastre = orden.crearArrastre(ad, relojSimulado());
  arrastre.presionar({ x: 380, y: 250, tipo: "mouse" });
  assert.deepEqual(ad.registro.huecos, []); // en su lugar (índice 1), sin mover el hueco
  assert.equal(arrastre.mover({ x: 380, y: 50 }), true);
  arrastre.mover({ x: 380, y: 60 });
  arrastre.mover({ x: 380, y: 520 });
  assert.deepEqual(ad.registro.huecos, [0, 3]);
  assert.equal(arrastre.soltar({ x: 380, y: 520 }), 3);
  assert.deepEqual(ad.registro.soltado, [3]);
  assert.equal(arrastre.estado(), "libre");
});

test("cerca de los bordes la página se desplaza sola", () => {
  const reloj = relojSimulado();
  const ad = adaptadorSimulado([100, 300], 800);
  const arrastre = orden.crearArrastre(ad, reloj);
  arrastre.presionar({ x: 380, y: 400, tipo: "mouse" });
  reloj.cuadroSiguiente();
  assert.deepEqual(ad.registro.desplazado, []);
  arrastre.mover({ x: 380, y: 790 });
  reloj.cuadroSiguiente();
  reloj.cuadroSiguiente();
  arrastre.mover({ x: 380, y: 10 });
  reloj.cuadroSiguiente();
  assert.ok(ad.registro.desplazado.length >= 3);
  assert.ok(ad.registro.desplazado[0] > 0);
  assert.ok(ad.registro.desplazado[ad.registro.desplazado.length - 1] < 0);
  arrastre.soltar({ x: 380, y: 10 });
  const antes = ad.registro.desplazado.length;
  reloj.cuadroSiguiente();
  assert.equal(ad.registro.desplazado.length, antes); // al soltar se detiene
});

test("Esc, soltar fuera de la lista o en el mismo lugar no cambian nada y lo anuncian", () => {
  const casos = [
    [(a) => a.cancelar(), orden.TEXTOS.cancelado],
    [(a) => a.soltar({ x: 900, y: 120 }), orden.TEXTOS.cancelado],
    [(a) => a.soltar({ x: 380, y: 250 }), orden.TEXTOS.sinCambios],
  ];
  for (const [accion, texto] of casos) {
    const ad = adaptadorSimulado([100, 300, 500], 900);
    const arrastre = orden.crearArrastre(ad, relojSimulado());
    arrastre.presionar({ x: 380, y: 250, tipo: "mouse" });
    if (texto !== orden.TEXTOS.sinCambios) arrastre.mover({ x: 380, y: 120 });
    assert.equal(accion(arrastre) ?? null, null);
    assert.equal(ad.registro.devuelto, 1);
    assert.deepEqual(ad.registro.soltado, []);
    assert.deepEqual(ad.registro.anuncios, [texto]);
  }
});

// Guardado --------------------------------------------------------------------------------------------------

function respuesta(status, cuerpo) {
  return { status, json: () => (cuerpo === undefined ? Promise.reject(new Error("sin json")) : Promise.resolve(cuerpo)) };
}

test("guardar envía un POST con Accept JSON y CSRF; sin conexión no envía nada", async () => {
  const llamadas = [];
  const ok = { ok: true, orden: [], version: 2 };
  const resultado = await orden.guardar({
    fetch: (url, opciones) => { llamadas.push({ url, opciones }); return Promise.resolve(respuesta(200, ok)); },
    url: "/entregas/mis/orden/mover/", cuerpo: "cuerpo", csrf: "token", enLinea: true,
  });
  assert.equal(resultado, ok);
  assert.equal(llamadas[0].opciones.method, "POST");
  assert.equal(llamadas[0].opciones.headers.Accept, "application/json");
  assert.equal(llamadas[0].opciones.headers["X-CSRFToken"], "token");
  let llamado = false;
  const sinRed = await orden.guardar({ fetch: () => { llamado = true; }, url: "/x/", enLinea: false });
  assert.equal(llamado, false);
  assert.deepEqual(sinRed, { ok: false, mensaje: orden.TEXTOS.sinRed });
  const corte = await orden.guardar({ fetch: () => Promise.reject(new TypeError("Failed to fetch")), url: "/x/", enLinea: true });
  assert.equal(corte.mensaje, orden.TEXTOS.sinRed);
  const choque = await orden.guardar({
    fetch: () => Promise.resolve(respuesta(409, { ok: false, error: "Tu orden cambió en otro dispositivo; revisa la lista." })),
    url: "/x/", enLinea: true,
  });
  assert.deepEqual(choque, { ok: false, mensaje: "Tu orden cambió en otro dispositivo; revisa la lista.", conflicto: true });
  const caida = await orden.guardar({ fetch: () => Promise.resolve(respuesta(500)), url: "/x/", enLinea: true });
  assert.equal(caida.mensaje, orden.TEXTOS.fallo);
});

test("cada envío lleva una operación nueva con forma de UUID", () => {
  const vistos = new Set();
  for (let i = 0; i < 20; i += 1) vistos.add(orden.nuevaOperacion(null));
  assert.equal(vistos.size, 20);
  for (const valor of vistos) assert.match(valor, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  assert.equal(orden.nuevaOperacion({ randomUUID: () => "fijo" }), "fijo");
});

// Página con tres paradas -------------------------------------------------------------------------------------

function tarjeta(id, numero, total) {
  return ["article", { id: "parada-" + id, "data-intento": String(id), "data-arrastrable": true, class: id === 3 ? "visita visita-nueva" : "visita" },
    ["p", { "data-rotulos": true }, ["span", { "data-numero": true }, "Parada " + numero],
      ...(id === 3 ? [["span", { "data-nueva": true }, "Nueva: no estaba en tu orden"]] : [])],
    ["h3", {}, "Paciente " + id],
    ["form", { action: "/entregas/mis/orden/mover/", "data-orden-form": true },
      ["input", { name: "csrfmiddlewaretoken", value: "token" }],
      ["input", { name: "intento", value: String(id) }],
      ["input", { name: "version", value: "0", "data-version": true }],
      ["input", { name: "operacion_id", value: "vieja" }],
      ["button", { "data-flecha": "subir", value: "subir", ...(numero === 1 ? { hidden: true } : {}) },
        ["span", { "data-flecha-nombre": true }, "Subir parada " + numero]],
      ["button", { "data-flecha": "bajar", value: "bajar", ...(numero === total ? { hidden: true } : {}) },
        ["span", { "data-flecha-nombre": true }, "Bajar parada " + numero]]],
    ["div", { "data-franja": true, hidden: true }]];
}

function pagina() {
  const documento = new Documento();
  documento.body.appendChild(crear(documento, ["p", { "data-orden-estado": true }]));
  documento.body.appendChild(crear(documento, ["p", { "data-ruta-rotulo": true }, "Orden sugerido según distancia por camino"]));
  documento.body.appendChild(crear(documento, ["p", { "data-ruta-resumen": true }, "Recorrido aprox. por camino: 9,0 km"]));
  const lista = crear(documento, ["section", { "data-ruta-lista": true }, ["div", { "data-ruta-paradas": true }]]);
  documento.body.appendChild(lista);
  [1, 2, 3].forEach((id, i) => {
    const nodo = crear(documento, tarjeta(id, i + 1, 3));
    nodo.rect = { top: 100 + i * 200, bottom: 280 + i * 200, height: 180, left: 0, right: 400, width: 400 };
    lista.querySelector("[data-ruta-paradas]").appendChild(nodo);
  });
  lista.rect = { top: 80, bottom: 720, left: 0, right: 400, width: 400, height: 640 };
  documento.body.appendChild(crear(documento, ["details", { "data-restablecer": true, hidden: true },
    ["form", {}, ["input", { name: "version", value: "0" }]]]));
  return documento;
}

class FormDataSimulado {
  constructor(form) {
    this.datos = {};
    form.querySelectorAll("input").forEach((campo) => { this.datos[campo.getAttribute("name")] = campo.value; });
  }
  set(clave, valor) { this.datos[clave] = valor; }
}

function entorno(respuestas) {
  const enviados = [];
  return {
    enviados,
    fetch(url, opciones) { enviados.push({ url, cuerpo: opciones.body.datos }); return Promise.resolve(respuestas.shift()); },
    FormData: FormDataSimulado, navigator: { onLine: true }, cripto: null, recargar() { this.recargado = true; },
    ventana: { innerHeight: 900, scrollBy() {} }, reloj: relojSimulado(),
  };
}

const esperar = () => new Promise((r) => setImmediate(r));
const ids = (documento) => documento.querySelectorAll("[data-arrastrable]").map((t) => t.getAttribute("data-intento"));

function ordenServidor(intentos, version) {
  return {
    ok: true, version, manual: true, mensaje: "Orden guardado.",
    orden: intentos.map((intento, i) => ({ intento, numero: i + 1, numerada: true })),
    rotulo: '<p class="ruta-rotulo" data-ruta-rotulo>Tu orden de hoy, guardado a las 09:15.</p>',
    resumen: '<p class="resumen-visitas" data-ruta-resumen>Recorrido aprox. por camino: 7,5 km</p>',
  };
}

test("la flecha «Bajar» mueve la tarjeta, guarda y aplica el orden del servidor sin recargar", async () => {
  const documento = pagina();
  const red = entorno([respuesta(200, ordenServidor([2, 1, 3], 1))]);
  orden.preparar(documento, red);
  assert.equal(documento.querySelector("[data-franja]").hidden, false); // la franja aparece con JavaScript
  const bajar = documento.querySelector('#parada-1 [data-flecha="bajar"]');
  const enviado = documento.getElementById("parada-1").querySelector("form").dispatchEvent(
    evento("submit", { target: documento.getElementById("parada-1").querySelector("form"), submitter: bajar }));
  assert.equal(enviado, false); // sin recarga
  assert.deepEqual(ids(documento), ["2", "1", "3"]); // se mueve al tiro
  await esperar(); await esperar(); await esperar();
  assert.equal(red.enviados[0].cuerpo.destino, "bajar");
  assert.notEqual(red.enviados[0].cuerpo.operacion_id, "vieja");
  assert.deepEqual(ids(documento), ["2", "1", "3"]);
  assert.equal(documento.querySelector("#parada-1 [data-numero]").textContent, "Parada 2");
  assert.equal(documento.querySelector('#parada-2 [data-flecha="subir"]').hidden, true);
  assert.equal(documento.querySelector('#parada-1 [data-flecha="subir"]').hidden, false);
  assert.equal(documento.querySelector('#parada-1 [data-flecha="bajar"] [data-flecha-nombre]').textContent, "Bajar parada 2: Paciente 1");
  assert.equal(documento.querySelector("#parada-3 [data-nueva]"), null); // al guardar, las nuevas quedan incorporadas
  assert.ok(documento.querySelectorAll("[data-version]").every((c) => c.value === "1"));
  assert.equal(documento.querySelector("[data-restablecer]").hidden, false);
  assert.equal(documento.querySelector("[data-restablecer] [name=version]").value, "1");
  assert.equal(documento.querySelector("[data-ruta-rotulo]").textContent, "Tu orden de hoy, guardado a las 09:15.");
  assert.equal(documento.querySelector("[data-ruta-resumen]").textContent, "Recorrido aprox. por camino: 7,5 km");
  assert.equal(documento.querySelector("[data-orden-estado]").textContent, "Parada movida a la posición 2.");
  assert.equal(documento.activeElement, bajar);
});

test("si el guardado falla, la lista vuelve a como estaba y se dice el motivo", async () => {
  const documento = pagina();
  const red = entorno([respuesta(409, { ok: false, error: "Tu orden cambió en otro dispositivo; revisa la lista." })]);
  orden.preparar(documento, red);
  const form = documento.getElementById("parada-2").querySelector("form");
  form.dispatchEvent(evento("submit", { target: form, submitter: form.querySelector('[data-flecha="subir"]') }));
  assert.deepEqual(ids(documento), ["2", "1", "3"]);
  await esperar(); await esperar(); await esperar();
  assert.deepEqual(ids(documento), ["1", "2", "3"]);
  assert.equal(documento.querySelector("[data-orden-estado]").textContent, "Tu orden cambió en otro dispositivo; revisa la lista.");
  assert.equal(documento.querySelector("[data-restablecer]").hidden, true);
});

test("arrastrar la parada 3 a la posición 1 con el mouse guarda la posición y lo anuncia", async () => {
  const documento = pagina();
  const red = entorno([respuesta(200, ordenServidor([3, 1, 2], 1))]);
  orden.preparar(documento, red);
  const franja = documento.querySelector("#parada-3 [data-franja]");
  franja.dispatchEvent(evento("pointerdown", { target: franja, clientX: 390, clientY: 590, pointerType: "mouse", button: 0 }));
  assert.ok(documento.getElementById("parada-3").classList.contains("visita-arrastrando"));
  assert.equal(documento.querySelectorAll(".visita-hueco").length, 1);
  documento.dispatchEvent(evento("pointermove", { clientX: 390, clientY: 120 }));
  const hueco = documento.querySelector(".visita-hueco");
  assert.equal(hueco.nextSibling, documento.getElementById("parada-1")); // el hueco muestra dónde caerá
  documento.dispatchEvent(evento("pointerup", { clientX: 390, clientY: 120 }));
  assert.equal(documento.querySelectorAll(".visita-hueco").length, 0);
  assert.ok(!documento.getElementById("parada-3").classList.contains("visita-arrastrando"));
  assert.deepEqual(ids(documento), ["3", "1", "2"]);
  await esperar(); await esperar(); await esperar();
  assert.equal(red.enviados[0].cuerpo.destino, "1");
  assert.equal(documento.querySelector("[data-orden-estado]").textContent, "Parada movida a la posición 1.");
  assert.equal(documento.querySelector("#parada-3 [data-numero]").textContent, "Parada 1");
});

test("Esc durante el arrastre devuelve la tarjeta a su lugar sin enviar nada", async () => {
  const documento = pagina();
  const red = entorno([]);
  orden.preparar(documento, red);
  const franja = documento.querySelector("#parada-1 [data-franja]");
  franja.dispatchEvent(evento("pointerdown", { target: franja, clientX: 390, clientY: 190, pointerType: "mouse", button: 0 }));
  documento.dispatchEvent(evento("pointermove", { clientX: 390, clientY: 650 }));
  documento.dispatchEvent(evento("keydown", { key: "Escape" }));
  assert.deepEqual(ids(documento), ["1", "2", "3"]);
  assert.equal(documento.querySelectorAll(".visita-hueco").length, 0);
  assert.equal(documento.querySelector("[data-orden-estado]").textContent, orden.TEXTOS.cancelado);
  documento.dispatchEvent(evento("pointerup", { clientX: 390, clientY: 650 }));
  await esperar();
  assert.equal(red.enviados.length, 0);
});

test("si el servidor responde otras visitas, la página se vuelve a cargar", async () => {
  const documento = pagina();
  const red = entorno([respuesta(200, ordenServidor([2, 1], 1))]);
  orden.preparar(documento, red);
  const form = documento.getElementById("parada-1").querySelector("form");
  form.dispatchEvent(evento("submit", { target: form, submitter: form.querySelector('[data-flecha="bajar"]') }));
  await esperar(); await esperar(); await esperar();
  assert.equal(red.recargado, true);
  assert.equal(documento.querySelector("[data-orden-estado]").textContent, orden.TEXTOS.cambioLista);
});

// Corrección del 2026-11-16: las visitas sin coordenadas del final siguen en su sección al reordenar.
function paginaConSinCoordenadas() {
  const documento = pagina();
  documento.querySelector("#parada-3").parentNode.removeChild(documento.querySelector("#parada-3"));
  const seccion = crear(documento, ["section", { "data-ruta-sin-coordenadas": true },
    ["h2", {}, "Sin coordenadas: fuera del orden sugerido (", ["span", { "data-ruta-sin-cantidad": true }, "2"], ")"],
    ["div", { "data-ruta-sin-lista": true }]]);
  documento.body.appendChild(seccion);
  const sinLista = seccion.querySelector("[data-ruta-sin-lista]");
  [4, 5].forEach((id) => {
    sinLista.appendChild(crear(documento, ["p", { class: "grupo-sector", "data-grupo-sector": true }, "Sin sector"]));
    const nodo = crear(documento, tarjeta(id, id - 1, 4));
    nodo.setAttribute("data-grupo", id === 4 ? "Sin sector" : "Sector Azul");
    nodo.querySelector("[data-numero]").parentNode.removeChild(nodo.querySelector("[data-numero]"));
    sinLista.appendChild(nodo);
  });
  return documento;
}

function ordenMixto(intentos, numeradas, version) {
  const cuerpo = ordenServidor(intentos, version);
  cuerpo.orden.forEach((p) => { p.numerada = numeradas.includes(p.intento); });
  return cuerpo;
}

test("al mover una numerada, las sin coordenadas del final quedan en su sección agrupadas", async () => {
  const documento = paginaConSinCoordenadas();
  const red = entorno([respuesta(200, ordenMixto([2, 1, 4, 5], [1, 2], 1))]);
  orden.preparar(documento, red);
  const form = documento.getElementById("parada-1").querySelector("form");
  form.dispatchEvent(evento("submit", { target: form, submitter: form.querySelector('[data-flecha="bajar"]') }));
  await esperar(); await esperar(); await esperar();
  const lista = documento.querySelector("[data-ruta-paradas]");
  const sinLista = documento.querySelector("[data-ruta-sin-lista]");
  assert.deepEqual(lista.querySelectorAll("[data-arrastrable]").map((t) => t.getAttribute("data-intento")), ["2", "1"]);
  assert.deepEqual(sinLista.querySelectorAll("[data-arrastrable]").map((t) => t.getAttribute("data-intento")), ["4", "5"]);
  assert.equal(documento.querySelector("#parada-4 [data-numero]"), null);
  assert.deepEqual(sinLista.querySelectorAll("[data-grupo-sector]").map((p) => p.textContent), ["Sin sector", "Sector Azul"]);
  assert.equal(documento.querySelector("[data-ruta-sin-cantidad]").textContent, "2");
  assert.equal(documento.querySelector("[data-ruta-sin-coordenadas]").hidden, false);
});

test("solo la sin coordenadas que se ubica entre las numeradas pasa a la lista con número", async () => {
  const documento = paginaConSinCoordenadas();
  const red = entorno([respuesta(200, ordenMixto([1, 4, 2, 5], [1, 4, 2], 1))]);
  orden.preparar(documento, red);
  const form = documento.getElementById("parada-4").querySelector("form");
  form.dispatchEvent(evento("submit", { target: form, submitter: form.querySelector('[data-flecha="subir"]') }));
  await esperar(); await esperar(); await esperar();
  const lista = documento.querySelector("[data-ruta-paradas]");
  const sinLista = documento.querySelector("[data-ruta-sin-lista]");
  assert.deepEqual(lista.querySelectorAll("[data-arrastrable]").map((t) => t.getAttribute("data-intento")), ["1", "4", "2"]);
  assert.equal(documento.querySelector("#parada-4 [data-numero]").textContent, "Parada 2");
  assert.deepEqual(sinLista.querySelectorAll("[data-arrastrable]").map((t) => t.getAttribute("data-intento")), ["5"]);
  assert.deepEqual(sinLista.querySelectorAll("[data-grupo-sector]").map((p) => p.textContent), ["Sector Azul"]);
  assert.equal(documento.querySelector("[data-ruta-sin-cantidad]").textContent, "1");
});

test("las únicas solicitudes van a la acción del formulario de Django", () => {
  const codigo = fs.readFileSync(ruta, "utf8");
  assert.doesNotMatch(codigo, /XMLHttpRequest|sendBeacon/);
  assert.equal((codigo.match(/entorno\.fetch\(/g) || []).length, 1);
  const plantilla = fs.readFileSync(path.join(__dirname, "../../templates/entregas/_tarjeta_intento.html"), "utf8");
  assert.match(plantilla, /class="visita-franja" aria-hidden="true" data-franja hidden/); // sin foco ni lector
});
