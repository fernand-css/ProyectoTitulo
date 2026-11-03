// Contrato del diálogo: cancelar no emite y una pantalla caducada no se imprime.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { runInNewContext } = require('node:vm');
const codigo = readFileSync(join(__dirname, '../../static/js/totem.js'), 'utf8');

function entorno(vigente = true) {
  const eventos = {};
  const botones = {};
  let reloj = 0, limpiar = 0, impresiones = 0, intervalo;
  const solicitudes = [];
  const boton = {hidden: true, addEventListener: (nombre, fn) => { botones[nombre] = fn; }};
  const final = {requestSubmit: () => limpiar++};
  const aviso = {hidden: true};
  const panel = {
    dataset: {segundos: '30', continuar: '/turnos/totem/continuar/', inicio: '/turnos/totem/'},
    querySelector(selector) {
      return ({'[data-finalizar]': final, '[data-aviso]': aviso,
        '[data-ampliar]': {addEventListener() {}}, '[data-imprimir]': boton,
        '[data-cuenta]': {textContent: ''}})[selector] || null;
    }
  };
  const window = {
    addEventListener: (nombre, fn) => { eventos[nombre] = fn; },
    print() {
      impresiones++;
      eventos.beforeprint();
      reloj += 35000;
      intervalo();
      assert.equal(limpiar, 0, 'No limpiar mientras el diálogo está abierto');
      eventos.afterprint(); // Incluye cerrar/cancelar: no existe confirmación de papel.
      intervalo();
      assert.equal(limpiar, 0, 'Dar tiempo a comprobar la sesión al cerrar el diálogo');
    }
  };
  runInNewContext(codigo, {
    document: {querySelector: () => panel}, window, Date: {now: () => reloj},
    setInterval: fn => { intervalo = fn; }, FormData: class {},
    fetch: async (url, opciones) => { solicitudes.push([url, opciones.method]); return {ok: vigente}; },
  });
  return {boton, botones, solicitudes, intervalo: () => intervalo(),
    impresiones: () => impresiones, limpiezas: () => limpiar};
}

test('Cancelar y reimprimir invoca solo el diálogo y la ampliación de contexto', async () => {
  const caso = entorno();
  await caso.botones.click();
  await caso.botones.click();
  assert.equal(caso.impresiones(), 2);
  assert.equal(caso.limpiezas(), 0);
  assert.equal(caso.boton.disabled, false);
  assert.equal(caso.boton.textContent, 'Volver a imprimir número');
  assert.ok(caso.solicitudes.every(([url, metodo]) => url === '/turnos/totem/continuar/' && metodo === 'POST'));
});

test('Contexto vencido impide abrir el diálogo y limpia la pantalla', async () => {
  const caso = entorno(false);
  await caso.botones.click();
  assert.equal(caso.impresiones(), 0);
  assert.equal(caso.limpiezas(), 1);
  caso.intervalo();
  assert.equal(caso.limpiezas(), 1);
});
