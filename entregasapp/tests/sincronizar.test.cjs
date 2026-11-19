// Pruebas de static/js/entregas/sincronizar.js (spec 11, RF-11-06, RF-11-07, RF-11-10 y RF-11-11).
const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const { crearAlmacen, memoria } = require(path.join(__dirname, "../../static/js/entregas/almacen.js"));
const sincronizar = require(path.join(__dirname, "../../static/js/entregas/sincronizar.js"));

function respuesta(status, cuerpo, tipo = "basic") {
  return { status, ok: status >= 200 && status < 300, type: tipo, json: async () => cuerpo };
}

// Servidor simulado: responde por operación según `decidir(registro)`; guarda cada solicitud.
function servidor(decidir) {
  const solicitudes = [];
  const fetch = async (url, opciones) => {
    const cuerpo = JSON.parse(opciones.body);
    solicitudes.push({ url, opciones, registros: cuerpo.registros });
    return respuesta(200, { resultados: cuerpo.registros.map((r) => Object.assign({ operacion_id: r.operacion_id }, decidir(r))) });
  };
  return { fetch, solicitudes };
}

async function preparar(cantidad, cuenta = 7) {
  const almacen = crearAlmacen(memoria());
  for (let i = 0; i < cantidad; i += 1) {
    await almacen.agregarRegistro({ operacion_id: `op-${cuenta}-${i}`, intento: i + 1, resultado: "entregada", motivo: "",
      nota: "", registrado_en: new Date(Date.UTC(2026, 10, 18, 12, 0, i)).toISOString(), fecha_local: "2026-11-18", cuenta });
  }
  return almacen;
}

function sincronizador(almacen, fetch, cuenta = 7) {
  return sincronizar.crearSincronizador({ almacen, url: "/entregas/mis/sincronizar/", fetch,
    obtenerCuenta: () => cuenta, obtenerToken: () => Promise.resolve("token-sintetico") });
}

test("envía en lotes de 50 con CSRF por cabecera, sin seguir redirecciones, y vacía la cola", async () => {
  const almacen = await preparar(120);
  const s = servidor(() => ({ estado: "aplicado" }));
  const resultado = await sincronizador(almacen, s.fetch).enviar();
  assert.deepEqual(s.solicitudes.map((x) => x.registros.length), [50, 50, 20]);
  const opciones = s.solicitudes[0].opciones;
  assert.equal(opciones.method, "POST");
  assert.equal(opciones.redirect, "manual");
  assert.equal(opciones.credentials, "same-origin");
  assert.equal(opciones.headers["X-CSRFToken"], "token-sintetico");
  assert.deepEqual(Object.keys(s.solicitudes[0].registros[0]).sort(),
    ["cuenta", "intento", "motivo", "nota", "operacion_id", "registrado_en", "resultado"]);
  assert.deepEqual(resultado, { estado: "enviado", aplicados: 120, rechazados: 0, pendientes: 0 });
});

test("ya_aplicado sale de la cola, rechazado queda con su motivo y reintentar se conserva", async () => {
  const almacen = await preparar(3);
  const s = servidor((r) => ({ "op-7-0": { estado: "ya_aplicado" }, "op-7-1": { estado: "rechazado", codigo: "reasignada", mensaje: "" },
    "op-7-2": { estado: "reintentar" } })[r.operacion_id]);
  const resultado = await sincronizador(almacen, s.fetch).enviar();
  assert.deepEqual(resultado, { estado: "enviado", aplicados: 1, rechazados: 1, pendientes: 1 });
  const rechazado = (await almacen.rechazados(7))[0];
  assert.equal(rechazado.operacion_id, "op-7-1");
  assert.equal(rechazado.mensaje, "La Q.F. reasignó esta visita antes de que llegara tu registro.");
  assert.deepEqual((await almacen.pendientes(7)).map((r) => r.operacion_id), ["op-7-2"]);
});

test("sin red, sesión vencida, límite o servidor caído: todo sigue en la cola", async () => {
  const casos = [
    [async () => { throw new TypeError("Failed to fetch"); }, "sin_red"],
    [async () => respuesta(0, null, "opaqueredirect"), "sesion"],
    [async () => respuesta(302, null), "sesion"],
    [async () => respuesta(403, { error: "x" }), "sesion"],
    [async () => respuesta(429, { error: "x" }), "limite"],
    [async () => respuesta(503, null), "servidor"],
    [async () => ({ status: 200, ok: true, type: "basic", json: async () => { throw new SyntaxError("html"); } }), "servidor"],
  ];
  for (const [fetch, estado] of casos) {
    const almacen = await preparar(2);
    const resultado = await sincronizador(almacen, fetch).enviar();
    assert.equal(resultado.estado, estado);
    assert.equal(resultado.pendientes, 2);
    assert.equal((await almacen.pendientes(7)).length, 2);
  }
});

test("solo envía la cola de la cuenta activa; sin cuenta no envía nada", async () => {
  const almacen = await preparar(2, 7);
  await almacen.agregarRegistro({ operacion_id: "op-8", intento: 99, resultado: "entregada", motivo: "", nota: "",
    registrado_en: "2026-11-18T12:00:00.000Z", fecha_local: "2026-11-18", cuenta: 8 });
  const s = servidor(() => ({ estado: "aplicado" }));
  await sincronizador(almacen, s.fetch, 7).enviar();
  assert.deepEqual(s.solicitudes[0].registros.map((r) => r.cuenta), [7, 7]);
  assert.equal((await almacen.pendientes(8)).length, 1);
  const vacio = await sincronizador(almacen, s.fetch, null).enviar();
  assert.equal(vacio.estado, "sin_cuenta");
  assert.equal(s.solicitudes.length, 1);
});

test("dos llamadas a la vez comparten el mismo envío", async () => {
  const almacen = await preparar(1);
  const s = servidor(() => ({ estado: "aplicado" }));
  const sin = sincronizador(almacen, s.fetch);
  const [a, b] = await Promise.all([sin.enviar(), sin.enviar()]);
  assert.equal(s.solicitudes.length, 1);
  assert.deepEqual(a, b);
  assert.equal((await sin.enviar()).estado, "sin_pendientes");
});

test("Background Sync solo donde existe", async () => {
  const etiquetas = [];
  const con = { serviceWorker: { ready: Promise.resolve({ sync: { register: async (e) => { etiquetas.push(e); } } }) } };
  assert.equal(await sincronizar.registrarSync(con), true);
  assert.deepEqual(etiquetas, ["cesfam-registros"]);
  assert.equal(await sincronizar.registrarSync({ serviceWorker: { ready: Promise.resolve({}) } }), false);
  assert.equal(await sincronizar.registrarSync({}), false);
  assert.equal(sincronizar.INTERVALO_MS, 30000);
  assert.equal(sincronizar.LOTE, 50);
});
