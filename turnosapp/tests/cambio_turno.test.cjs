const {test} = require('node:test');
const assert = require('node:assert/strict');
const {webcrypto} = require('node:crypto');
const {nuevaOperacion, preparar} = require('../../static/js/cambio_turno.js');

function opcion(letra) {
  const radio = {checked: true, disabled: false, focus() { radio.enfocado = true; }};
  return {dataset: {opcion: letra}, hidden: false, querySelector: () => radio, radio};
}

function dialogo(opciones = []) {
  const operacion = {value: ''};
  const codigo = {textContent: ''};
  const cancelar = {dataset: {}, closest: () => d, focus() { cancelar.enfocado = true; }};
  const formulario = {action: '', querySelector: s => (s === '[data-operacion]' ? operacion : null)};
  const d = {
    abierto: false, operacion, codigo, cancelar, formulario,
    showModal() { d.abierto = true; }, close() { d.abierto = false; },
    querySelector: s => ({form: formulario, '[data-cerrar]': cancelar,
      '[data-opcion]:not([hidden]) input': (opciones.find(o => !o.hidden) || {}).radio})[s],
    querySelectorAll: s => (s === '[data-codigo]' ? [codigo] : s === '[data-opcion]' ? opciones : []),
  };
  return d;
}

function entorno() {
  const opciones = ['P', 'G', 'C'].map(opcion);
  const fila = dialogo(opciones), urgencia = dialogo();
  let clic;
  const documento = {
    getElementById: id => ({'dialogo-fila': fila, 'dialogo-urgencia': urgencia})[id],
    addEventListener: (_, fn) => { clic = fn; },
  };
  assert.equal(preparar(documento, webcrypto), true);
  const pulsar = origen => {
    let prevenido = false;
    clic({target: {closest: s => (s === '[data-abrir]' ? origen : null)}, preventDefault() { prevenido = true; }});
    return prevenido;
  };
  return {fila, urgencia, opciones, pulsar, clic: e => clic(e)};
}

test('operación nueva con formato UUID v4 en cada apertura', () => {
  const uno = nuevaOperacion(webcrypto), dos = nuevaOperacion(webcrypto);
  assert.match(uno, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  assert.notEqual(uno, dos);
});

test('cambiar fila abre el modal sin la fila actual y con la acción del turno', () => {
  const e = entorno();
  const prevenido = e.pulsar({dataset: {abrir: 'fila', codigo: 'C-009', letra: 'C', accion: '/turnos/7/reclasificar/'}});
  assert.equal(prevenido, true, 'Con JavaScript no se navega al historial');
  assert.equal(e.fila.abierto, true);
  assert.equal(e.fila.formulario.action, '/turnos/7/reclasificar/');
  assert.equal(e.fila.codigo.textContent, 'C-009');
  assert.match(e.fila.operacion.value, /^[0-9a-f-]{36}$/);
  const [p, g, c] = e.opciones;
  assert.deepEqual([p.hidden, g.hidden, c.hidden], [false, false, true]);
  assert.equal(c.radio.disabled, true);
  assert.ok([p, g, c].every(o => o.radio.checked === false), 'Ninguna fila queda elegida de antemano');
  assert.equal(p.radio.enfocado, true);
});

test('urgencia pide confirmación con foco en Cancelar y Cancelar cierra', () => {
  const e = entorno();
  e.pulsar({dataset: {abrir: 'urgencia', codigo: 'G-040', letra: 'G', accion: '/turnos/9/urgencia/'}});
  assert.equal(e.urgencia.abierto, true);
  assert.equal(e.urgencia.formulario.action, '/turnos/9/urgencia/');
  assert.equal(e.urgencia.codigo.textContent, 'G-040');
  assert.equal(e.urgencia.cancelar.enfocado, true);
  e.clic({target: {closest: s => (s === '[data-cerrar]' ? e.urgencia.cancelar : null)}});
  assert.equal(e.urgencia.abierto, false);
});

test('sin soporte de <dialog> no intercepta y queda el enlace al historial', () => {
  const documento = {getElementById: () => ({}), addEventListener: () => assert.fail('No debe escuchar clics')};
  assert.equal(preparar(documento, webcrypto), false);
});
