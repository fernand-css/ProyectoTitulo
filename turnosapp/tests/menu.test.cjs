// Contrato del menú plegable: el botón abre y cierra, Escape devuelve el foco y ensanchar la ventana lo reinicia.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { runInNewContext } = require('node:vm');
const codigo = readFileSync(join(__dirname, '../../static/js/menu.js'), 'utf8');

function entorno({ conMenu = true } = {}) {
  const atributos = { 'aria-expanded': 'false' };
  const clases = new Set();
  const oyentes = {};
  const cambios = {};
  let foco = 0;
  const boton = {
    getAttribute: nombre => atributos[nombre], setAttribute: (nombre, valor) => { atributos[nombre] = valor; },
    addEventListener: (nombre, fn) => { oyentes['boton:' + nombre] = fn; }, focus: () => foco++,
    contains: objetivo => objetivo === boton,
  };
  const menu = { classList: { add: c => clases.add(c), remove: c => clases.delete(c) }, contains: objetivo => objetivo === menu };
  runInNewContext(codigo, {
    document: {
      querySelector: selector => (conMenu ? { '[data-menu-boton]': boton, '[data-menu]': menu }[selector] : null),
      addEventListener: (nombre, fn) => { oyentes['doc:' + nombre] = fn; },
    },
    window: { matchMedia: () => ({ addEventListener: (nombre, fn) => { cambios[nombre] = fn; } }) },
  });
  return { atributos, clases, oyentes, cambios, foco: () => foco, boton, menu };
}

test('el botón abre y vuelve a cerrar el menú', () => {
  const e = entorno();
  e.oyentes['boton:click']();
  assert.equal(e.atributos['aria-expanded'], 'true');
  assert.ok(e.clases.has('nav-abierto'));
  e.oyentes['boton:click']();
  assert.equal(e.atributos['aria-expanded'], 'false');
  assert.ok(!e.clases.has('nav-abierto'));
});

test('Escape cierra el menú abierto y devuelve el foco al botón; cerrado no hace nada', () => {
  const e = entorno();
  e.oyentes['doc:keydown']({ key: 'Escape' });
  assert.equal(e.foco(), 0);
  e.oyentes['boton:click']();
  e.oyentes['doc:keydown']({ key: 'Tab' });
  assert.equal(e.atributos['aria-expanded'], 'true');
  e.oyentes['doc:keydown']({ key: 'Escape' });
  assert.equal(e.atributos['aria-expanded'], 'false');
  assert.equal(e.foco(), 1);
});

test('tocar fuera lo cierra; tocar dentro del menú o en el botón no', () => {
  const e = entorno();
  e.oyentes['boton:click']();
  e.oyentes['doc:click']({ target: e.menu });
  e.oyentes['doc:click']({ target: e.boton });
  assert.equal(e.atributos['aria-expanded'], 'true');
  e.oyentes['doc:click']({ target: {} });
  assert.equal(e.atributos['aria-expanded'], 'false');
});

test('al ensanchar la ventana el menú se reinicia; al achicarla no se toca', () => {
  const e = entorno();
  e.oyentes['boton:click']();
  e.cambios.change({ matches: true });
  assert.equal(e.atributos['aria-expanded'], 'true');
  e.cambios.change({ matches: false });
  assert.equal(e.atributos['aria-expanded'], 'false');
  assert.ok(!e.clases.has('nav-abierto'));
});

test('sin botón o sin menú en la página no falla', () => {
  assert.doesNotThrow(() => entorno({ conMenu: false }));
});
