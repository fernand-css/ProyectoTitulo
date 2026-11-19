// Pruebas de static/js/entregas/almacen.js (spec 11, RF-11-03, RF-11-05 y RF-11-14), con el adaptador en memoria.
const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const { crearAlmacen, memoria, fechaLocal } = require(path.join(__dirname, "../../static/js/entregas/almacen.js"));

function reloj(texto) {
  const estado = { ahora: new Date(texto) };
  return { estado, ahora: () => estado.ahora };
}

function paquete(cuenta, fecha, paradas = 2) {
  return { formato: 1, fecha, cuenta, generado_en: fecha + "T08:00:00-03:00", motivos: [],
    paradas: Array.from({ length: paradas }, (_, i) => ({ intento: i + 1, nombre: "Paciente sintético " + i })) };
}

function registro(datos) {
  return Object.assign({ operacion_id: "op-" + Math.random(), intento: 1, resultado: "entregada", motivo: "", nota: "",
    registrado_en: "2026-11-18T12:00:00.000Z", fecha_local: "2026-11-18", cuenta: 7 }, datos);
}

test("el paquete se guarda por cuenta y solo vale para hoy", async () => {
  const r = reloj("2026-11-18T10:00:00");
  const almacen = crearAlmacen(memoria(), { ahora: r.ahora });
  await almacen.guardarPaquete(paquete(7, "2026-11-18"));
  await almacen.guardarPaquete(paquete(8, "2026-11-18", 3));
  assert.equal((await almacen.leerPaquete(7)).datos.paradas.length, 2);
  assert.equal((await almacen.leerPaquete("8")).datos.paradas.length, 3);
  assert.equal(await almacen.leerPaquete(""), null);
  r.estado.ahora = new Date("2026-11-19T07:00:00");
  assert.equal(await almacen.leerPaquete(7), null, "el de ayer se borra");
  r.estado.ahora = new Date("2026-11-18T10:00:00");
  assert.equal(await almacen.leerPaquete(7), null, "y no vuelve");
});

test("limpiar deja solo el paquete de hoy de la cuenta que entró", async () => {
  const adaptador = memoria();
  const almacen = crearAlmacen(adaptador, { ahora: () => new Date("2026-11-18T10:00:00") });
  await almacen.guardarPaquete(paquete(7, "2026-11-18"));
  await almacen.guardarPaquete(paquete(8, "2026-11-18"));
  await almacen.guardarPaquete(paquete(9, "2026-11-17"));
  await almacen.limpiarPaquetes(8);
  assert.deepEqual(Array.from(adaptador.datos.paquete.keys()), ["8"]);
});

test("un solo registro por intento y cuenta mientras esté en la cola", async () => {
  const almacen = crearAlmacen(memoria());
  await almacen.agregarRegistro(registro({ operacion_id: "a", intento: 41 }));
  await assert.rejects(almacen.agregarRegistro(registro({ operacion_id: "b", intento: 41 })), (error) => error.codigo === "duplicado");
  await almacen.agregarRegistro(registro({ operacion_id: "c", intento: 41, cuenta: 8 }));
  assert.deepEqual((await almacen.pendientes(7)).map((r) => r.operacion_id), ["a"]);
  // Rechazado no bloquea: se puede volver a registrar con señal.
  await almacen.marcarRechazado((await almacen.pendientes(7))[0], "reasignada", "Mensaje");
  assert.equal((await almacen.pendientes(7)).length, 0);
  assert.equal((await almacen.rechazados(7))[0].codigo, "reasignada");
  await almacen.agregarRegistro(registro({ operacion_id: "d", intento: 41 }));
  await almacen.quitarRegistro("d");
  assert.equal((await almacen.pendientes(7)).length, 0);
});

test("la cola borra lo que tiene más de 2 días y conserva el resto", async () => {
  const almacen = crearAlmacen(memoria(), { ahora: () => new Date("2026-11-18T10:00:00") });
  await almacen.agregarRegistro(registro({ operacion_id: "hace3", intento: 1, fecha_local: "2026-11-15" }));
  await almacen.agregarRegistro(registro({ operacion_id: "hace2", intento: 2, fecha_local: "2026-11-16" }));
  await almacen.agregarRegistro(registro({ operacion_id: "hoy", intento: 3, fecha_local: "2026-11-18" }));
  await almacen.purgarCola();
  assert.deepEqual((await almacen.registros(7)).map((r) => r.operacion_id).sort(), ["hace2", "hoy"]);
});

test("meta guarda y borra la cuenta activa y el token", async () => {
  const almacen = crearAlmacen(memoria());
  await almacen.guardarMeta("cuenta_activa", "7");
  await almacen.guardarMeta("csrf", "token-sintetico");
  assert.equal(await almacen.leerMeta("cuenta_activa"), "7");
  await almacen.guardarMeta("csrf", null);
  assert.equal(await almacen.leerMeta("csrf"), null);
});

test("fecha local del celular en AAAA-MM-DD", () => {
  assert.equal(fechaLocal(new Date(2026, 0, 5, 23, 59)), "2026-01-05");
});
