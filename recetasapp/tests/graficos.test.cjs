// Contrato de la ayuda de los gráficos de Recetas: aparece con el puntero o el foco, dice lo que dice data-tip
// (sin interpretarlo como HTML), se cierra con Escape o al salir el mouse y se queda a la vista con el dedo.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { runInNewContext } = require('node:vm');
const codigo = readFileSync(join(__dirname, '../../static/js/graficos.js'), 'utf8');

function entorno({ ancho = 600, anchoCuadro = 120 } = {}) {
  const oyentesFigura = {};
  const oyentesDocumento = {};
  const hijos = [];
  const marca = (texto) => ({
    getAttribute: (nombre) => (nombre === 'data-tip' ? texto : null),
    closest: (selector) => (selector === '[data-tip]' ? marca_ : null),
    getBoundingClientRect: () => ({ left: 200, top: 80, width: 40 }),
  });
  const marca_ = marca('lunes 2 de noviembre: 3 entregas');
  const otra = { closest: () => null, getBoundingClientRect: () => ({ left: 0, top: 0, width: 0 }) };
  let bajoElPunto = marca_;
  const figura = {
    appendChild: (nodo) => { hijos.push(nodo); },
    contains: (nodo) => nodo === marca_ || nodo === otra || hijos.includes(nodo),
    getBoundingClientRect: () => ({ left: 100, top: 50, width: ancho }),
    addEventListener: (nombre, fn) => { oyentesFigura[nombre] = fn; },
  };
  const documento = {
    createElement: () => ({
      attrs: {}, style: {}, hidden: false, textContent: '', className: '',
      offsetWidth: anchoCuadro, offsetHeight: 30,
      setAttribute(nombre, valor) { this.attrs[nombre] = valor; },
    }),
    querySelectorAll: (selector) => (selector === '[data-grafico]' ? [figura] : []),
    elementFromPoint: () => bajoElPunto,
    addEventListener: (nombre, fn) => { oyentesDocumento[nombre] = fn; },
  };
  runInNewContext(codigo, { document: documento });
  return {
    cuadro: hijos[0], figura: oyentesFigura, documento: oyentesDocumento, marca: marca_, otra,
    bajo: (nodo) => { bajoElPunto = nodo; },
  };
}

test('crea un único cuadro de ayuda oculto, con rol tooltip', () => {
  const { cuadro } = entorno();
  assert.equal(cuadro.className, 'grafico-tip');
  assert.equal(cuadro.attrs.role, 'tooltip');
  assert.equal(cuadro.hidden, true);
});

test('el puntero sobre una marca muestra su texto junto al puntero', () => {
  const { cuadro, figura } = entorno();
  figura.pointermove({ clientX: 300, clientY: 200, target: null });
  assert.equal(cuadro.hidden, false);
  assert.equal(cuadro.textContent, 'lunes 2 de noviembre: 3 entregas');
  assert.equal(cuadro.style.left, '212px'); // 300 - 100 + 12
  assert.equal(cuadro.style.top, '108px'); // 200 - 50 - 30 - 12
});

test('el texto se escribe como texto y nunca como HTML', () => {
  const { cuadro, figura, marca } = entorno();
  marca.getAttribute = () => '<img src=x onerror=alert(1)>';
  figura.pointermove({ clientX: 300, clientY: 200, target: null });
  assert.equal(cuadro.textContent, '<img src=x onerror=alert(1)>');
  assert.equal('innerHTML' in cuadro, false);
});

test('si no cabe a la derecha pasa al otro lado del puntero', () => {
  const { cuadro, figura } = entorno({ ancho: 400, anchoCuadro: 120 });
  figura.pointermove({ clientX: 480, clientY: 200, target: null }); // 480 - 100 + 12 + 120 > 400
  assert.equal(cuadro.style.left, '248px'); // 480 - 100 - 12 - 120
});

test('sin marca bajo el punto, el cuadro se oculta', () => {
  const { cuadro, figura, bajo, otra } = entorno();
  figura.pointermove({ clientX: 300, clientY: 200, target: null });
  bajo(otra);
  figura.pointermove({ clientX: 10, clientY: 10, target: null });
  assert.equal(cuadro.hidden, true);
});

test('el mouse oculta al salir, pero con el dedo queda a la vista', () => {
  const { cuadro, figura } = entorno();
  figura.pointerdown({ clientX: 300, clientY: 200, pointerType: 'touch', target: null });
  figura.pointerleave({ pointerType: 'touch' });
  assert.equal(cuadro.hidden, false);
  figura.pointerleave({ pointerType: 'mouse' });
  assert.equal(cuadro.hidden, true);
});

test('tocar fuera del gráfico, Escape y quitar el foco lo ocultan', () => {
  const { cuadro, figura, documento, otra } = entorno();
  const afuera = { id: 'afuera' };
  figura.pointerdown({ clientX: 300, clientY: 200, pointerType: 'touch', target: null });
  documento.pointerdown({ target: afuera });
  assert.equal(cuadro.hidden, true);
  figura.pointerdown({ clientX: 300, clientY: 200, pointerType: 'touch', target: null });
  documento.pointerdown({ target: otra }); // dentro de la figura: no oculta
  assert.equal(cuadro.hidden, false);
  documento.keydown({ key: 'Escape' });
  assert.equal(cuadro.hidden, true);
  figura.focusin({ target: otra });
  assert.equal(cuadro.hidden, true); // sin data-tip no muestra nada
  figura.focusin({ target: { closest: () => ({ getAttribute: () => 'Vigentes: 3 (50 %)', getBoundingClientRect: () => ({ left: 150, top: 120, width: 80 }) }) } });
  assert.equal(cuadro.textContent, 'Vigentes: 3 (50 %)');
  assert.equal(cuadro.hidden, false);
  figura.focusout({});
  assert.equal(cuadro.hidden, true);
});
