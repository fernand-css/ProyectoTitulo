// Contrato del menú principal: plegar la columna lateral (con memoria) y la hoja «Más» del celular.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { runInNewContext } = require('node:vm');
const codigo = readFileSync(join(__dirname, '../../static/js/menu.js'), 'utf8');

function entorno({ conPlegar = true, conMas = true, guardado = null, almacenamiento = true, abierta = false } = {}) {
  const raizAtributos = {};
  const botonAtributos = { 'aria-expanded': 'true', 'aria-label': 'Plegar el menú' };
  const oyentes = {};
  const hoja = {};
  const cambios = {};
  const memoria = { valor: guardado, escrituras: [] };
  let foco = 0;
  const boton = {
    getAttribute: nombre => botonAtributos[nombre],
    setAttribute: (nombre, valor) => { botonAtributos[nombre] = valor; },
    addEventListener: (nombre, fn) => { oyentes['boton:' + nombre] = fn; },
  };
  const resumen = { focus: () => foco++ };
  const mas = {
    open: abierta,
    querySelector: selector => (selector === 'summary' ? resumen : null),
    contains: objetivo => objetivo === mas || objetivo === hoja,
    addEventListener: (nombre, fn) => { oyentes['mas:' + nombre] = fn; },
  };
  const raiz = {
    getAttribute: nombre => (nombre in raizAtributos ? raizAtributos[nombre] : null),
    setAttribute: (nombre, valor) => { raizAtributos[nombre] = valor; },
    removeAttribute: nombre => { delete raizAtributos[nombre]; },
  };
  const localStorage = almacenamiento
    ? {
        getItem: () => memoria.valor,
        setItem: (clave, valor) => { memoria.valor = valor; memoria.escrituras.push([clave, valor]); },
        removeItem: clave => { memoria.valor = null; memoria.escrituras.push([clave, null]); },
      }
    : { getItem: () => { throw new Error('bloqueado'); }, setItem: () => { throw new Error('bloqueado'); }, removeItem: () => { throw new Error('bloqueado'); } };
  runInNewContext(codigo, {
    document: {
      documentElement: raiz,
      querySelector: selector => ({ '[data-menu-plegar]': conPlegar ? boton : null, '[data-mas]': conMas ? mas : null }[selector]),
      addEventListener: (nombre, fn) => { oyentes['doc:' + nombre] = fn; },
    },
    window: { localStorage, matchMedia: consulta => ({ consulta, addEventListener: (nombre, fn) => { cambios[nombre] = fn; } }) },
  });
  return { raizAtributos, botonAtributos, oyentes, memoria, mas, hoja, cambios, foco: () => foco };
}

test('el botón pliega y despliega la columna y recuerda la elección', () => {
  const e = entorno();
  assert.equal(e.botonAtributos['aria-expanded'], 'true');
  e.oyentes['boton:click']();
  assert.equal(e.raizAtributos['data-menu'], 'plegado');
  assert.equal(e.botonAtributos['aria-expanded'], 'false');
  assert.equal(e.botonAtributos['aria-label'], 'Desplegar el menú');
  assert.deepEqual(e.memoria.escrituras.at(-1), ['farmacia.menu', 'plegado']);
  e.oyentes['boton:click']();
  assert.ok(!('data-menu' in e.raizAtributos));
  assert.equal(e.botonAtributos['aria-expanded'], 'true');
  assert.equal(e.botonAtributos['aria-label'], 'Plegar el menú');
  assert.deepEqual(e.memoria.escrituras.at(-1), ['farmacia.menu', null]);
});

test('al cargar aplica la elección guardada y deja el botón en el estado correcto', () => {
  const e = entorno({ guardado: 'plegado' });
  assert.equal(e.raizAtributos['data-menu'], 'plegado');
  assert.equal(e.botonAtributos['aria-expanded'], 'false');
  assert.equal(e.botonAtributos['aria-label'], 'Desplegar el menú');
});

test('un valor guardado desconocido no pliega el menú', () => {
  const e = entorno({ guardado: 'otra-cosa' });
  assert.ok(!('data-menu' in e.raizAtributos));
  assert.equal(e.botonAtributos['aria-expanded'], 'true');
});

test('sin almacenamiento el menú se pliega igual, solo en esta visita', () => {
  const e = entorno({ almacenamiento: false });
  assert.doesNotThrow(() => e.oyentes['boton:click']());
  assert.equal(e.raizAtributos['data-menu'], 'plegado');
  assert.equal(e.botonAtributos['aria-expanded'], 'false');
});

test('Escape cierra la hoja abierta y devuelve el foco a «Más»; cerrada no hace nada', () => {
  const e = entorno();
  e.oyentes['doc:keydown']({ key: 'Escape' });
  assert.equal(e.foco(), 0);
  e.mas.open = true;
  e.oyentes['doc:keydown']({ key: 'Tab' });
  assert.equal(e.mas.open, true);
  e.oyentes['doc:keydown']({ key: 'Escape' });
  assert.equal(e.mas.open, false);
  assert.equal(e.foco(), 1);
});

test('tocar fuera cierra la hoja sin mover el foco; tocar dentro no', () => {
  const e = entorno({ abierta: true });
  e.oyentes['doc:click']({ target: e.hoja });
  e.oyentes['doc:click']({ target: e.mas });
  assert.equal(e.mas.open, true);
  e.oyentes['doc:click']({ target: {} });
  assert.equal(e.mas.open, false);
  assert.equal(e.foco(), 0);
});

test('elegir una opción cierra la hoja; tocar un texto de la hoja no', () => {
  const e = entorno({ abierta: true });
  e.oyentes['mas:click']({ target: { closest: () => null } });
  assert.equal(e.mas.open, true);
  e.oyentes['mas:click']({ target: { closest: selector => (selector === 'a' ? {} : null) } });
  assert.equal(e.mas.open, false);
});

test('si el foco sale de la hoja se cierra; si queda dentro o no va a ningún lado, no', () => {
  const e = entorno({ abierta: true });
  e.oyentes['mas:focusout']({ relatedTarget: e.hoja });
  e.oyentes['mas:focusout']({ relatedTarget: null });
  assert.equal(e.mas.open, true);
  e.oyentes['mas:focusout']({ relatedTarget: {} });
  assert.equal(e.mas.open, false);
});

test('al ensanchar la ventana la hoja se cierra; al achicarla no se toca', () => {
  const e = entorno({ abierta: true });
  e.cambios.change({ matches: false });
  assert.equal(e.mas.open, true);
  e.cambios.change({ matches: true });
  assert.equal(e.mas.open, false);
});

test('sin botón o sin hoja en la página no falla y cada parte funciona sola', () => {
  assert.doesNotThrow(() => entorno({ conPlegar: false, conMas: false }));
  const soloMas = entorno({ conPlegar: false });
  soloMas.mas.open = true;
  soloMas.oyentes['doc:keydown']({ key: 'Escape' });
  assert.equal(soloMas.mas.open, false);
  const soloPlegar = entorno({ conMas: false });
  soloPlegar.oyentes['boton:click']();
  assert.equal(soloPlegar.raizAtributos['data-menu'], 'plegado');
});
