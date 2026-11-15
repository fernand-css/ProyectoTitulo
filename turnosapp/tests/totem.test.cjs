// Contrato del tótem sin impresión: vuelve solo al inicio y «Necesito más tiempo» amplía el plazo.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { runInNewContext } = require('node:vm');
const codigo = readFileSync(join(__dirname, '../../static/js/totem.js'), 'utf8');

function entorno({vigente = true, resultado = true} = {}) {
  const ampliar = {};
  let reloj = 0, limpiezas = 0, intervalo;
  const solicitudes = [];
  const final = {requestSubmit: () => limpiezas++};
  const aviso = {hidden: !resultado};
  const cuenta = {textContent: ''};
  const panel = {
    hidden: false,
    dataset: {segundos: resultado ? '30' : '120', continuar: '/turnos/totem/continuar/', inicio: '/turnos/totem/'},
    hasAttribute: nombre => nombre === 'data-resultado' && resultado,
    addEventListener() {},
    querySelector(selector) {
      return ({'[data-finalizar]': final, '[data-aviso]': aviso, '[data-cuenta]': cuenta,
        '[data-ampliar]': {addEventListener: (nombre, fn) => { ampliar[nombre] = fn; }}})[selector] || null;
    }
  };
  runInNewContext(codigo, {
    document: {querySelector: () => panel}, window: {addEventListener() {}},
    Date: {now: () => reloj}, setInterval: fn => { intervalo = fn; }, FormData: class {},
    fetch: async (url, opciones) => { solicitudes.push([url, opciones.method]); return {ok: vigente}; },
  });
  return {
    panel, aviso, cuenta, solicitudes,
    avanzar(ms) { reloj += ms; intervalo(); },
    ampliar: () => ampliar.click(),
    limpiezas: () => limpiezas,
  };
}

test('El código no imprime ni escucha el diálogo de impresión', () => {
  assert.doesNotMatch(codigo, /print/);
  assert.doesNotMatch(codigo, /(localStorage|sessionStorage)\./);
});

test('El resultado muestra la cuenta y vuelve solo al inicio a los 30 s', () => {
  const caso = entorno();
  caso.avanzar(1000);
  assert.equal(caso.aviso.hidden, false);
  assert.equal(caso.cuenta.textContent, '29');
  caso.avanzar(28000);
  assert.equal(caso.limpiezas(), 0);
  caso.avanzar(1000);
  assert.equal(caso.limpiezas(), 1);
  assert.equal(caso.panel.hidden, true);
  caso.avanzar(5000);
  assert.equal(caso.limpiezas(), 1, 'Envía el formulario oculto una sola vez');
});

test('«Necesito más tiempo» reinicia los 30 s sin ocultar la franja', async () => {
  const caso = entorno();
  caso.avanzar(25000);
  await caso.ampliar();
  assert.deepEqual(caso.solicitudes, [['/turnos/totem/continuar/', 'POST']]);
  assert.equal(caso.aviso.hidden, false);
  assert.equal(caso.cuenta.textContent, '30');
  caso.avanzar(29000);
  assert.equal(caso.limpiezas(), 0);
  caso.avanzar(1000);
  assert.equal(caso.limpiezas(), 1);
});

test('Una operación vencida limpia la pantalla al pedir más tiempo', async () => {
  const caso = entorno({vigente: false});
  await caso.ampliar();
  assert.equal(caso.limpiezas(), 1);
});

test('La entrada avisa a los 20 s restantes y luego limpia', () => {
  const caso = entorno({resultado: false});
  caso.avanzar(99000);
  assert.equal(caso.aviso.hidden, true);
  caso.avanzar(1000);
  assert.equal(caso.aviso.hidden, false);
  assert.equal(caso.cuenta.textContent, '20');
  caso.avanzar(20000);
  assert.equal(caso.limpiezas(), 1);
});
