// Pruebas de static/js/entregas/sin_conexion.js (spec 11, RF-11-02 a RF-11-06, RF-11-10, RF-11-13 y RF-11-16).
// DOM simulado, almacén en memoria y servidor simulado. Datos sintéticos, sin RUT.
const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const { crearAlmacen, memoria, fechaLocal } = require(path.join(__dirname, "../../static/js/entregas/almacen.js"));
const sincronizar = require(path.join(__dirname, "../../static/js/entregas/sincronizar.js"));
const sinConexion = require(path.join(__dirname, "../../static/js/entregas/sin_conexion.js"));
const { Documento, crear, evento } = require("./dom_simulado.cjs");

const HOY = fechaLocal(new Date());
const MOTIVOS = [["sin_receptor", "No había nadie para recibir"], ["otro", "Otro"]];

function paqueteDe(cuenta) {
  return {
    formato: 1, fecha: HOY, generado_en: new Date().toISOString(), cuenta, motivos: MOTIVOS,
    paradas: [
      { intento: 41, numero: 1, seccion: "ruta", fecha_programada: HOY, atrasada: false, nombre: "Paciente sintético Uno",
        direccion: "Camino sintético km 2", referencias: "Portón sintético", localidad: "Localidad demo", sector: "Verde",
        telefono: "+56 9 0000 0000", recetas: 2, traslado_iniciado: false },
      { intento: 42, numero: null, seccion: "sin_coordenadas", fecha_programada: "2026-01-02", atrasada: true,
        nombre: "Paciente sintético Dos", direccion: "Sin número", referencias: "", localidad: "", sector: "",
        telefono: "", recetas: 1, traslado_iniciado: true },
    ],
  };
}

function estado(cuenta, extra = {}) {
  return ["section", Object.assign({ "data-reparto-estado": true, "data-cuenta": cuenta, "data-paquete-url": "/entregas/mis/paquete/",
    "data-sincronizar-url": "/entregas/mis/sincronizar/", "data-sin-conexion-url": "/entregas/mis/sin-conexion/",
    "data-mis-url": "/entregas/mis/", hidden: true }, extra),
  ["ul", { role: "status", "aria-live": "polite", "data-estado-lista": true },
    ["li", { "data-estado-conexion": true }], ["li", { "data-estado-guardada": true }],
    ["li", { "data-estado-pendientes": true }], ["li", { "data-estado-envio": true, hidden: true }]],
  ["div", { class: "acciones" }, ["button", { type: "button", "data-sincronizar": true, hidden: true }, "Sincronizar ahora"],
    ["button", { type: "button", "data-actualizar": true, hidden: true }, "Actualizar la lista"]],
  ["section", { "data-rechazados": true, hidden: true }, ["h3", {}, "No se pudo enviar"], ["ul", { "data-lista-rechazados": true }]]];
}

function paginaSinConexion() {
  const documento = new Documento();
  documento.body.appendChild(crear(documento, ["div", { "data-sin-conexion": true },
    estado(""),
    ["p", { "data-sin-paquete": true, hidden: true }, "No hay una ruta guardada para hoy. Ábrela con señal."],
    ["section", { "data-paradas": true, hidden: true }, ["h2", {}, "Por visitar (", ["span", { "data-cantidad": true }, "0"], ")"],
      ["ol", { "data-lista-paradas": true }]]]));
  return documento;
}

function respuesta(status, cuerpo, tipo = "basic") {
  return { status, ok: status >= 200 && status < 300, type: tipo, json: async () => cuerpo };
}

function entorno(documento, almacen, opciones = {}) {
  const llamadas = { fetch: [], ir: [], normal: [], mensajes: [], sync: 0, recargas: 0 };
  const fetch = opciones.fetch || (async () => { throw new TypeError("Failed to fetch"); });
  const fetchRegistrado = async (url, o) => { llamadas.fetch.push({ url, o }); return fetch(url, o); };
  let n = 0;
  const raiz = documento.querySelector("[data-reparto-estado]");
  const sincronizador = sincronizar.crearSincronizador({ almacen, url: "/entregas/mis/sincronizar/", fetch: fetchRegistrado,
    obtenerCuenta: () => raiz.getAttribute("data-cuenta") || almacen.leerMeta("cuenta_activa"),
    obtenerToken: () => "token-sintetico" });
  const navegador = Object.assign({ onLine: true, serviceWorker: { ready: Promise.resolve({ active: { postMessage: (m) => llamadas.mensajes.push(m) } }) } },
    opciones.navegador || {});
  return {
    llamadas,
    entorno: {
      documento, raiz, almacen, sincronizador, fetch: fetchRegistrado, navegador,
      ventana: { location: opciones.location || { pathname: "/entregas/mis/", search: "" } },
      uuid: () => "00000000-0000-4000-8000-00000000000" + (n += 1),
      formData: (form) => ({ form }), ir: (url) => llamadas.ir.push(url), enviarNormal: (form) => llamadas.normal.push(form),
      registrarSync: () => { llamadas.sync += 1; },
      recargar: () => { llamadas.recargas += 1; },
    },
  };
}

async function vistaConPaquete(opciones = {}) {
  const documento = paginaSinConexion();
  const almacen = crearAlmacen(memoria());
  await almacen.guardarMeta("cuenta_activa", "7");
  await almacen.guardarPaquete(paqueteDe(7));
  const e = entorno(documento, almacen, opciones);
  const controlador = await sinConexion.crear(e.entorno).iniciar();
  return { documento, almacen, controlador, llamadas: e.llamadas };
}

function texto(documento, selector) {
  const nodo = documento.querySelector(selector);
  return nodo ? nodo.textContent : null;
}

function enviarFormulario(form) {
  form.dispatchEvent(evento("submit"));
  return new Promise((resolver) => setTimeout(resolver, 0));
}

test("RF-11-04 y RF-11-13: sin señal dibuja la ruta guardada y dice el estado con texto", async () => {
  const { documento } = await vistaConPaquete();
  assert.equal(documento.querySelector("[data-reparto-estado]").hidden, false);
  assert.equal(texto(documento, "[data-estado-conexion]"), "Sin conexión");
  assert.match(texto(documento, "[data-estado-guardada]"), /^Ruta guardada en este celular a las \d\d:\d\d · 2 visitas$/);
  assert.equal(texto(documento, "[data-estado-pendientes]"), "No hay registros por enviar.");
  assert.equal(documento.querySelector("[data-paradas]").hidden, false);
  assert.equal(documento.querySelector("[data-sin-paquete]").hidden, true);
  assert.equal(texto(documento, "[data-cantidad]"), "2");
  const tarjetas = documento.querySelectorAll("[data-lista-paradas] li.visita");
  assert.equal(tarjetas.length, 2);
  assert.match(tarjetas[0].textContent, /Parada 1.*Paciente sintético Uno.*Camino sintético km 2.*Portón sintético.*Sector Verde · Localidad demo.*2 recetas/);
  assert.match(tarjetas[1].textContent, /Sin coordenadas.*Traslado iniciado.*Atrasada desde el 02\/01.*No registrado/);
  assert.equal(tarjetas[0].querySelector("a").getAttribute("href"), "tel:+56900000000");
  const region = documento.querySelector("[data-estado-lista]");
  assert.equal(region.getAttribute("aria-live"), "polite");
});

test("RF-11-03: sin paquete de hoy (o de otra cuenta) solo muestra el aviso", async () => {
  const documento = paginaSinConexion();
  const almacen = crearAlmacen(memoria());
  await almacen.guardarMeta("cuenta_activa", "8");
  await almacen.guardarPaquete(paqueteDe(7));  // de otra cuenta
  await sinConexion.crear(entorno(documento, almacen).entorno).iniciar();
  assert.equal(documento.querySelector("[data-sin-paquete]").hidden, false);
  assert.equal(documento.querySelector("[data-paradas]").hidden, true);
  assert.equal(documento.querySelectorAll("li.visita").length, 0);
  assert.equal(texto(documento, "[data-estado-guardada]"), "No hay una ruta guardada para hoy. Ábrela con señal.");
});

test("RF-11-05: valida como el 08, guarda en la cola, no ofrece un segundo registro y permite deshacer", async () => {
  const { documento, almacen, llamadas } = await vistaConPaquete();
  documento.querySelector('[data-abrir="no_entregada"][data-intento="41"]').click();
  await new Promise((r) => setTimeout(r, 0));
  let form = documento.querySelector("#registro-no_entregada-41");
  assert.ok(form, "se abre el formulario de no entrega");
  await enviarFormulario(form);
  assert.equal(form.querySelector("[data-error]").textContent, "Elige el motivo de la no entrega.");
  form.querySelector("[data-motivo]").value = "otro";
  await enviarFormulario(form);
  assert.equal(form.querySelector("[data-error]").textContent, "Con el motivo «Otro», escribe una nota breve.");
  form.querySelector("[data-nota]").value = "x".repeat(201);
  await enviarFormulario(form);
  assert.equal(form.querySelector("[data-error]").textContent, "La nota admite hasta 200 caracteres.");
  assert.equal((await almacen.pendientes(7)).length, 0);
  form.querySelector("[data-motivo]").value = "sin_receptor";
  form.querySelector("[data-nota]").value = "  Nota sintética  ";
  await enviarFormulario(form);
  await new Promise((r) => setTimeout(r, 0));
  const [registro] = await almacen.pendientes(7);
  assert.deepEqual([registro.intento, registro.resultado, registro.motivo, registro.nota, registro.cuenta, registro.fecha_local],
    [41, "no_entregada", "sin_receptor", "Nota sintética", 7, HOY]);
  assert.match(registro.operacion_id, /^00000000-0000-4000-8000-/);
  assert.ok(!Number.isNaN(Date.parse(registro.registrado_en)));
  const tarjeta = documento.querySelector("#parada-41");
  assert.match(tarjeta.textContent, /Registrada sin conexión · por enviar · No entregada · \d\d:\d\d/);
  assert.equal(tarjeta.querySelector("[data-abrir]"), null, "no se ofrece un segundo registro");
  assert.equal(texto(documento, "[data-estado-pendientes]"), "1 registro por enviar");
  assert.equal(documento.querySelector("[data-sincronizar]").hidden, false);
  assert.equal(llamadas.sync, 1, "pide Background Sync");
  documento.querySelector("[data-deshacer]").click();
  await new Promise((r) => setTimeout(r, 0));
  assert.equal((await almacen.pendientes(7)).length, 0);
  assert.ok(documento.querySelector('#parada-41 [data-abrir="entregada"]'));
  form = null;
});

test("RF-11-05: «Entregada» exige confirmar", async () => {
  const { documento, almacen } = await vistaConPaquete();
  documento.querySelector('[data-abrir="entregada"][data-intento="42"]').click();
  await new Promise((r) => setTimeout(r, 0));
  const form = documento.querySelector("#registro-entregada-42");
  await enviarFormulario(form);
  assert.equal(form.querySelector("[data-error]").textContent, "Marca la casilla para confirmar que entregaste las recetas.");
  form.querySelector("[data-confirmar]").checked = true;
  await enviarFormulario(form);
  await new Promise((r) => setTimeout(r, 0));
  assert.equal((await almacen.pendientes(7))[0].resultado, "entregada");
});

test("RF-11-05: abre directo la visita que se quiso registrar sin señal", async () => {
  const { documento } = await vistaConPaquete({ location: { pathname: "/entregas/intentos/42/", search: "?resultado=no_entregada" } });
  assert.ok(documento.querySelector("#registro-no_entregada-42"));
});

test("RF-11-06 y RF-11-10: al volver la señal envía; un rechazo queda visible hasta «Entendido»", async () => {
  let decidir = () => ({ estado: "rechazado", codigo: "reasignada", mensaje: "La Q.F. reasignó esta visita antes de que llegara tu registro." });
  const { documento, almacen, controlador, llamadas } = await vistaConPaquete({
    fetch: async (url, o) => {
      if (o && o.method === "POST") {
        const registros = JSON.parse(o.body).registros;
        return respuesta(200, { resultados: registros.map((r) => Object.assign({ operacion_id: r.operacion_id }, decidir(r))) });
      }
      return respuesta(200, paqueteDe(7));
    },
  });
  await controlador.encolar({ intento: 41, resultado: "entregada", cuenta: 7 });
  await controlador.encolar({ intento: 42, resultado: "no_entregada", motivo: "sin_receptor", nota: "", cuenta: 7 });
  await controlador.refrescar();
  decidir = (r) => (r.intento === 41 ? { estado: "aplicado" } : { estado: "rechazado", codigo: "reasignada", mensaje: "" });
  const resultado = await controlador.sincronizar();
  assert.deepEqual([resultado.aplicados, resultado.rechazados, resultado.pendientes], [1, 1, 0]);
  assert.match(texto(documento, "[data-estado-envio]"), /Se envió 1 registro\. 1 registro no se pudo aplicar/);
  assert.equal(texto(documento, "[data-estado-pendientes]"), "No hay registros por enviar.");
  const rechazados = documento.querySelector("[data-rechazados]");
  assert.equal(rechazados.hidden, false);
  assert.match(rechazados.textContent, /No entregada · Paciente sintético Dos · \d\d:\d\d/);
  assert.match(rechazados.textContent, /La Q\.F\. reasignó esta visita antes de que llegara tu registro\./);
  assert.ok(llamadas.fetch.some((l) => l.url === "/entregas/mis/paquete/"), "vuelve a descargar la ruta tras aplicar");
  documento.querySelector("[data-entendido]").click();
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(documento.querySelector("[data-rechazados]").hidden, true);
  assert.equal((await almacen.registros(7)).length, 0);
});

test("RF-11-06: sin red el registro se queda y el estado lo dice", async () => {
  const { documento, almacen, controlador } = await vistaConPaquete();
  await controlador.encolar({ intento: 41, resultado: "entregada", cuenta: 7 });
  const resultado = await controlador.sincronizar();
  assert.equal(resultado.estado, "sin_red");
  assert.equal((await almacen.pendientes(7)).length, 1);
  assert.equal(texto(documento, "[data-estado-envio]"), "Sin señal: los registros se enviarán solos al volver la conexión.");
});

test("RF-11-06: reintento cada 30 s y envío al volver la señal", async () => {
  const eventos = {};
  const intervalos = [];
  const ventana = { addEventListener: (tipo, fn) => { eventos[tipo] = fn; }, setInterval: (fn, ms) => { intervalos.push(ms); return 1; } };
  let enviados = 0;
  const controlador = { refrescar: async () => {}, sincronizar: async () => { enviados += 1; } };
  sinConexion.programar(controlador, ventana, 30000);
  assert.deepEqual(intervalos, [30000]);
  eventos.online();
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(enviados, 1);
});

test("RF-11-02: con señal, «Mis entregas» guarda el paquete de su cuenta y la página sin conexión", async () => {
  const documento = new Documento();
  documento.body.appendChild(crear(documento, ["div", {}, estado("7", { "data-descargar": true }),
    ["input", { type: "hidden", name: "csrfmiddlewaretoken", value: "token-de-la-pagina" }],
    ["article", { id: "parada-41" }, ["div", { class: "visita-resumen" }, ["h3", {}, "Paciente sintético Uno"]]]]));
  const almacen = crearAlmacen(memoria());
  await almacen.guardarPaquete(paqueteDe(8));  // de otra cuenta que usó el celular
  await almacen.agregarRegistro({ operacion_id: "op-1", intento: 41, resultado: "entregada", motivo: "", nota: "",
    registrado_en: new Date().toISOString(), fecha_local: HOY, cuenta: 7 });
  const e = entorno(documento, almacen, { fetch: async (url, o) => (o && o.method === "POST" ? respuesta(503, null) : respuesta(200, paqueteDe(7))) });
  const controlador = await sinConexion.crear(e.entorno).iniciar();
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(controlador.modo, "en_linea");
  assert.equal((await almacen.leerPaquete(7)).datos.paradas.length, 2);
  assert.equal(await almacen.leerPaquete(8), null, "el de otra cuenta se borra");
  assert.equal(await almacen.leerMeta("cuenta_activa"), "7");
  assert.equal(await almacen.leerMeta("csrf"), "token-de-la-pagina");
  assert.deepEqual(e.llamadas.mensajes, [{ tipo: "guardar-sin-conexion", url: "/entregas/mis/sin-conexion/" }]);
  assert.equal(texto(documento, "[data-estado-conexion]"), "Conectado");
  assert.match(documento.querySelector("#parada-41").textContent, /Registrada sin conexión · por enviar · \d\d:\d\d/);
  assert.equal(texto(documento, "[data-estado-envio]"), "El servidor no respondió. Se reintentará en 30 segundos.");
});

test("RF-11-02: un paquete de otra cuenta no se guarda", async () => {
  const documento = new Documento();
  documento.body.appendChild(crear(documento, estado("7", { "data-descargar": true })));
  const almacen = crearAlmacen(memoria());
  const e = entorno(documento, almacen, { fetch: async () => respuesta(200, paqueteDe(9)) });
  await sinConexion.crear(e.entorno).iniciar();
  assert.equal(await almacen.leerPaquete(7), null);
  assert.equal(await almacen.leerPaquete(9), null);
  assert.equal(e.llamadas.mensajes.length, 0);
});

function paginaRegistro() {
  const documento = new Documento();
  documento.body.appendChild(crear(documento, ["div", {}, estado("7"),
    ["form", { action: "/entregas/intentos/41/no-entregada/", "data-registro-sin-conexion": "no_entregada", "data-intento": "41" },
      ["p", { "data-aviso-sin-conexion": true, hidden: true }],
      ["input", { type: "hidden", name: "csrfmiddlewaretoken", value: "token" }],
      ["input", { type: "hidden", name: "operacion_id", value: "11111111-1111-4111-8111-111111111111" }],
      ["select", { name: "motivo", value: "sin_receptor" }, ["option", { value: "" }, "Elige"], ["option", { value: "sin_receptor" }, "Sin receptor"], ["option", { value: "otro" }, "Otro"]],
      ["textarea", { name: "nota", value: "" }],
      ["button", { type: "submit" }, "Registrar no entregada"]]]));
  return documento;
}

test("RF-11-16: con señal el formulario va al servidor y la cola no se usa", async () => {
  const documento = paginaRegistro();
  const almacen = crearAlmacen(memoria());
  const e = entorno(documento, almacen, { fetch: async () => respuesta(0, null, "opaqueredirect") });
  const controlador = await sinConexion.crear(e.entorno).iniciar();
  const form = documento.querySelector("form");
  assert.equal(await controlador.enviarFormulario(form), "enviado");
  assert.deepEqual(e.llamadas.ir, ["/entregas/mis/"]);
  assert.equal(e.llamadas.fetch[0].o.method, "POST");
  assert.equal((await almacen.registros(7)).length, 0);
});

test("RF-11-16: con errores del servidor se muestra su página, sin cola", async () => {
  const documento = paginaRegistro();
  const almacen = crearAlmacen(memoria());
  const e = entorno(documento, almacen, { fetch: async () => respuesta(400, null) });
  const controlador = await sinConexion.crear(e.entorno).iniciar();
  assert.equal(await controlador.enviarFormulario(documento.querySelector("form")), "servidor");
  assert.equal(e.llamadas.normal.length, 1);
  assert.equal((await almacen.registros(7)).length, 0);
});

test("RF-11-05: si el envío falla por la red, se guarda con el identificador del formulario", async () => {
  const documento = paginaRegistro();
  const almacen = crearAlmacen(memoria());
  const e = entorno(documento, almacen);  // fetch falla por la red
  const controlador = await sinConexion.crear(e.entorno).iniciar();
  const form = documento.querySelector("form");
  assert.equal(await controlador.enviarFormulario(form), "en_cola");
  const [registro] = await almacen.pendientes(7);
  assert.equal(registro.operacion_id, "11111111-1111-4111-8111-111111111111");
  assert.equal(registro.motivo, "sin_receptor");
  assert.match(form.querySelector("[data-aviso-sin-conexion]").textContent, /Registrada sin conexión · por enviar/);
  assert.equal(form.querySelector("button").hasAttribute("disabled"), true);
});

test("RF-11-05: sin conexión no intenta enviar y valida en el celular", async () => {
  const documento = paginaRegistro();
  const almacen = crearAlmacen(memoria());
  const e = entorno(documento, almacen, { navegador: { onLine: false } });
  const controlador = await sinConexion.crear(e.entorno).iniciar();
  const form = documento.querySelector("form");
  form.querySelector("select").value = "otro";
  assert.equal(await controlador.enviarFormulario(form), "invalido");
  assert.equal(form.querySelector("[data-aviso-sin-conexion]").textContent, "Con el motivo «Otro», escribe una nota breve.");
  form.querySelector("textarea").value = "Nota sintética";
  assert.equal(await controlador.enviarFormulario(form), "en_cola");
  assert.equal(e.llamadas.fetch.filter((l) => l.o && l.o.method === "POST" && l.url.includes("intentos")).length, 0);
});

test("validar repite las reglas del formulario del 08", () => {
  const { validar } = sinConexion;
  assert.equal(validar("entregada", "", "", true), "");
  assert.equal(validar("no_entregada", "inventado", "", false, ["otro"]), "Elige el motivo de la no entrega.");
  assert.equal(validar("no_entregada", "otro", "   ", false), "Con el motivo «Otro», escribe una nota breve.");
  assert.equal(validar("no_entregada", "otro", "Nota", false), "");
});

test("RF-11-06: con señal, tras enviar ofrece «Actualizar la lista» sin recargar por sorpresa", async () => {
  const documento = new Documento();
  documento.body.appendChild(crear(documento, estado("7", { "data-descargar": true })));
  const almacen = crearAlmacen(memoria());
  await almacen.agregarRegistro({ operacion_id: "op-1", intento: 41, resultado: "entregada", motivo: "", nota: "",
    registrado_en: new Date().toISOString(), fecha_local: HOY, cuenta: 7 });
  const e = entorno(documento, almacen, { fetch: async (url, o) => (o && o.method === "POST"
    ? respuesta(200, { resultados: [{ operacion_id: "op-1", estado: "aplicado" }] }) : respuesta(200, paqueteDe(7))) });
  await sinConexion.crear(e.entorno).iniciar();
  const boton = documento.querySelector("[data-actualizar]");
  assert.equal(boton.hidden, false);
  assert.equal(texto(documento, "[data-estado-envio]"), "Se envió 1 registro. Pulsa «Actualizar la lista» para ver tu ruta al día.");
  assert.equal(e.llamadas.recargas, 0);
  boton.click();
  assert.equal(e.llamadas.recargas, 1);
});
