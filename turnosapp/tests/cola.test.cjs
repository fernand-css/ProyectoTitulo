const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {runInNewContext} = require('node:vm');
const codigo = readFileSync(join(__dirname, '../../static/js/cola.js'), 'utf8');

function entorno(response = {ok: true, json: async () => ({html: 'nuevo', firma: '1'})}) {
  let tick, click, solicitudes = 0;
  const automatico = {checked: true};
  const mensaje = {textContent: ''};
  const estado = {dataset: {url: '/turnos/estado/'}, innerHTML: 'anterior',
    contains: elemento => elemento === 'formulario', replaceChildren() { this.innerHTML = ''; }};
  const documento = {activeElement: null, querySelector: selector => ({
    '[data-estado]': estado, '[data-automatico]': automatico, '[data-mensaje-estado]': mensaje,
    '[data-actualizar]': {addEventListener: (_, fn) => { click = fn; }}
  })[selector]};
  runInNewContext(codigo, {document: documento, setInterval: fn => { tick = fn; },
    fetch: async (_, opciones) => {
      solicitudes++;
      assert.equal(opciones.method, undefined, 'Solo GET');
      assert.equal(opciones.cache, 'no-store');
      return typeof response === 'function' ? response() : response;
    }});
  return {tick: () => tick(), click: () => click(), estado, automatico, documento, mensaje,
    solicitudes: () => solicitudes};
}

test('consulta de estado sin mutaciones y actualiza contenido', async () => {
  const e = entorno(); await e.tick();
  assert.equal(e.estado.innerHTML, 'nuevo'); assert.equal(e.solicitudes(), 1);
});
test('respeta pausa de actualización y permite refresco manual', async () => {
  const e = entorno(); e.automatico.checked = false; await e.tick();
  assert.equal(e.solicitudes(), 0); await e.click(); assert.equal(e.solicitudes(), 1);
});
test('conserva foco y formulario mientras se opera', async () => {
  const e = entorno(); e.documento.activeElement = 'formulario'; await e.tick();
  assert.equal(e.solicitudes(), 0); assert.equal(e.estado.innerHTML, 'anterior');
});
test('sesión revocada elimina los datos privados y detiene actualización', async () => {
  const e = entorno({status: 403}); await e.tick(); await e.tick();
  assert.equal(e.estado.innerHTML, ''); assert.equal(e.automatico.checked, false);
  assert.equal(e.solicitudes(), 1); assert.match(e.mensaje.textContent, /sesión/);
});
test('fallo de consulta muestra aviso y admite reintento', async () => {
  let intentos = 0;
  const e = entorno(() => {
    if (++intentos === 1) throw new Error('sintético');
    return {ok: true, json: async () => ({html: 'recuperado', firma: '2'})};
  });
  await e.tick(); assert.match(e.mensaje.textContent, /No se pudo/);
  await e.tick(); assert.equal(e.estado.innerHTML, 'recuperado');
});
