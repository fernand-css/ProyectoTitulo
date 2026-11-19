// Pruebas de static/js/pwa.js (spec 11, RF-11-03 y RF-11-14): datos del reparto al entrar y al salir.
const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const { crearAlmacen, memoria, fechaLocal } = require(path.join(__dirname, "../../static/js/entregas/almacen.js"));
const pwa = require(path.join(__dirname, "../../static/js/pwa.js"));
const { Documento, crear, evento } = require("./dom_simulado.cjs");

const HOY = fechaLocal(new Date());

function paquete(cuenta, fecha = HOY) {
  return { formato: 1, fecha, cuenta, generado_en: new Date().toISOString(), motivos: [], paradas: [{ intento: 1 }] };
}

async function preparar(pendientes) {
  const almacen = crearAlmacen(memoria());
  await almacen.guardarPaquete(paquete(7));
  for (let i = 0; i < pendientes; i += 1) {
    await almacen.agregarRegistro({ operacion_id: "op-" + i, intento: i + 1, resultado: "entregada", motivo: "", nota: "",
      registrado_en: new Date().toISOString(), fecha_local: HOY, cuenta: 7 });
  }
  await almacen.guardarMeta("cuenta_activa", "7");
  await almacen.guardarMeta("csrf", "token-sintetico");
  return almacen;
}

function documentoConSalida() {
  const documento = new Documento();
  documento.body.appendChild(crear(documento, ["div", {},
    ["form", { action: "/usuarios/salir/", method: "post" }, ["button", { type: "submit" }, "Cerrar sesión"]],
    ["form", { action: "/entregas/intentos/1/entregada/", method: "post" }, ["button", { type: "submit" }, "Registrar"]]]));
  return documento;
}

test("RF-11-14: con 2 registros por enviar avisa la cifra; al confirmar borra el paquete y conserva la cola", async () => {
  const almacen = await preparar(2);
  const avisos = [];
  const enviados = [];
  const p = pwa.crear({ documento: new Documento(), almacen, cuenta: "7", salir: "/usuarios/salir/",
    confirmar: (texto) => { avisos.push(texto); return true; }, enviar: (form) => enviados.push(form) });
  assert.equal(await p.alSalir("form"), true);
  assert.deepEqual(avisos, ["Tienes 2 registros sin enviar. Si sales, se enviarán cuando vuelvas a entrar con esta cuenta. ¿Quieres salir?"]);
  assert.deepEqual(enviados, ["form"]);
  assert.equal(await almacen.leerPaquete(7), null);
  assert.equal((await almacen.pendientes(7)).length, 2, "la cola se conserva, ligada a la cuenta");
  assert.equal(await almacen.leerMeta("cuenta_activa"), null);
  assert.equal(await almacen.leerMeta("csrf"), null);
});

test("RF-11-14: si cancela, no sale ni borra nada", async () => {
  const almacen = await preparar(1);
  const enviados = [];
  const p = pwa.crear({ documento: new Documento(), almacen, cuenta: "7", salir: "/usuarios/salir/",
    confirmar: (texto) => { assert.match(texto, /^Tienes 1 registro sin enviar\./); return false; }, enviar: (f) => enviados.push(f) });
  assert.equal(await p.alSalir("form"), false);
  assert.deepEqual(enviados, []);
  assert.ok(await almacen.leerPaquete(7));
});

test("sin registros por enviar sale sin preguntar y borra el paquete", async () => {
  const almacen = await preparar(0);
  let pregunto = false;
  const enviados = [];
  const p = pwa.crear({ documento: new Documento(), almacen, cuenta: "7", salir: "/usuarios/salir/",
    confirmar: () => { pregunto = true; return true; }, enviar: (f) => enviados.push(f) });
  await p.alSalir("form");
  assert.equal(pregunto, false);
  assert.equal(enviados.length, 1);
  assert.equal(await almacen.leerPaquete(7), null);
});

test("solo vigila el formulario de salida", async () => {
  const almacen = await preparar(0);
  const documento = documentoConSalida();
  const enviados = [];
  const p = pwa.crear({ documento, almacen, cuenta: "7", salir: "/usuarios/salir/", confirmar: () => true,
    enviar: (f) => enviados.push(f.getAttribute("action")) });
  p.vigilarSalida();
  const [salir, registrar] = documento.querySelectorAll("form");
  const otro = evento("submit");
  registrar.dispatchEvent(otro);
  assert.equal(otro.defaultPrevented, false);
  const deSalida = evento("submit");
  salir.dispatchEvent(deSalida);
  assert.equal(deSalida.defaultPrevented, true);
  await new Promise((r) => setTimeout(r, 0));
  assert.deepEqual(enviados, ["/usuarios/salir/"]);
});

test("RF-11-03: al entrar otra cuenta se borra la ruta guardada de la anterior; la cola de esta no se envía", async () => {
  const almacen = await preparar(1);
  await almacen.guardarPaquete(paquete(8, "2026-01-01"));
  const p = pwa.crear({ documento: new Documento(), almacen, cuenta: "9", salir: "/usuarios/salir/", confirmar: () => true, enviar: () => {} });
  assert.equal(await p.alEntrar(), true);
  assert.equal(await almacen.leerMeta("cuenta_activa"), "9");
  assert.equal(await almacen.leerPaquete(7), null);
  assert.equal((await almacen.pendientes(7)).length, 1, "la cola de la cuenta 7 espera a que vuelva");
});

test("sin cuenta (páginas públicas o la vista sin conexión) no toca nada", async () => {
  const almacen = await preparar(0);
  const p = pwa.crear({ documento: new Documento(), almacen, cuenta: "", salir: "/usuarios/salir/", confirmar: () => true, enviar: () => {} });
  assert.equal(await p.alEntrar(), false);
  assert.equal(await almacen.leerMeta("cuenta_activa"), "7");
  assert.ok(await almacen.leerPaquete(7));
});
