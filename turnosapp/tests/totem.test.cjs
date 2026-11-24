// Contrato del tótem sin impresión: vuelve solo al inicio, «Necesito más tiempo» amplía el plazo
// y «Volver al tótem» envía el formulario de finalizar.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { runInNewContext } = require('node:vm');
const codigo = readFileSync(join(__dirname, '../../static/js/totem.js'), 'utf8');

function entorno({vigente = true, resultado = true} = {}) {
  const ampliar = {};
  const envio = {};
  let reloj = 0, limpiezas = 0, intervalo;
  const solicitudes = [];
  const final = {requestSubmit: () => limpiezas++, addEventListener: (nombre, fn) => { envio[nombre] = fn; }};
  const aviso = {hidden: !resultado};
  const cuenta = {textContent: ''};
  // La frase visible se arma como en resultado.html, con la cuenta dentro.
  const frase = {get textContent() { return `Esta pantalla vuelve al inicio en ${cuenta.textContent} segundos.`; }};
  const anuncio = {textContent: ''};
  const panel = {
    hidden: false,
    dataset: {segundos: resultado ? '20' : '120', continuar: '/turnos/totem/continuar/', inicio: '/turnos/totem/'},
    hasAttribute: nombre => nombre === 'data-resultado' && resultado,
    addEventListener() {},
    querySelector(selector) {
      return ({'[data-finalizar]': final, '[data-aviso]': aviso, '[data-cuenta]': cuenta,
        '[data-frase]': resultado ? frase : null, '[data-anuncio]': resultado ? anuncio : null,
        '[data-ampliar]': {addEventListener: (nombre, fn) => { ampliar[nombre] = fn; }}})[selector] || null;
    }
  };
  runInNewContext(codigo, {
    document: {querySelector: () => panel}, window: {addEventListener() {}},
    Date: {now: () => reloj}, setInterval: fn => { intervalo = fn; }, FormData: class {},
    fetch: async (url, opciones) => { solicitudes.push([url, opciones.method]); return {ok: vigente}; },
  });
  return {
    panel, aviso, cuenta, anuncio, solicitudes,
    avanzar(ms) { reloj += ms; intervalo(); },
    ampliar: () => ampliar.click(),
    volver: () => envio.submit(),
    limpiezas: () => limpiezas,
  };
}

test('El código no imprime ni escucha el diálogo de impresión', () => {
  assert.doesNotMatch(codigo, /print/);
  assert.doesNotMatch(codigo, /(localStorage|sessionStorage)\./);
});

test('El resultado muestra la cuenta y vuelve solo al inicio a los 20 s', () => {
  const caso = entorno();
  caso.avanzar(1000);
  assert.equal(caso.aviso.hidden, false);
  assert.equal(caso.cuenta.textContent, '19');
  caso.avanzar(18000);
  assert.equal(caso.limpiezas(), 0);
  caso.avanzar(1000);
  assert.equal(caso.limpiezas(), 1);
  assert.equal(caso.panel.hidden, true);
  caso.avanzar(5000);
  assert.equal(caso.limpiezas(), 1, 'Envía el formulario oculto una sola vez');
});

test('«Necesito más tiempo» reinicia los 20 s sin ocultar la franja', async () => {
  const caso = entorno();
  caso.avanzar(15000);
  await caso.ampliar();
  assert.deepEqual(caso.solicitudes, [['/turnos/totem/continuar/', 'POST']]);
  assert.equal(caso.aviso.hidden, false);
  assert.equal(caso.cuenta.textContent, '20');
  caso.avanzar(19000);
  assert.equal(caso.limpiezas(), 0);
  caso.avanzar(1000);
  assert.equal(caso.limpiezas(), 1);
});

test('Lo que se anuncia al pedir más tiempo es la misma frase de la franja', async () => {
  const caso = entorno();
  assert.equal(caso.anuncio.textContent, '', 'La cuenta que baja no se anuncia cada segundo');
  caso.avanzar(3000);
  assert.equal(caso.anuncio.textContent, '');
  await caso.ampliar();
  assert.equal(caso.anuncio.textContent, 'Esta pantalla vuelve al inicio en 20 segundos.');
  caso.avanzar(4000);
  await caso.ampliar();
  // El mismo texto otra vez no se leería: cambia solo un espacio duro al final.
  assert.equal(caso.anuncio.textContent, 'Esta pantalla vuelve al inicio en 20 segundos.\u00a0');
  assert.equal(caso.anuncio.textContent.trim(), 'Esta pantalla vuelve al inicio en 20 segundos.');
});

test('«Volver al tótem» oculta el número de inmediato y la cuenta ya no reenvía', () => {
  const caso = entorno();
  caso.avanzar(2000);
  caso.volver();  // El navegador envía el formulario de finalizar; el código solo oculta.
  assert.equal(caso.panel.hidden, true);
  assert.equal(caso.limpiezas(), 0, 'No vuelve a enviar: el envío ya está en curso');
  caso.avanzar(30000);
  assert.equal(caso.limpiezas(), 0, 'La cuenta no envía otra vez el formulario');
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

// Formato del RUT (2026-11-23): el último carácter es el dígito verificador; el guion y los puntos se ponen solos.
function conTeclado(valorInicial = '') {
  const eventos = {};
  const input = {
    value: valorInicial, maxLength: 12, selectionStart: valorInicial.length, selectionEnd: valorInicial.length,
    addEventListener: (nombre, fn) => { eventos[nombre] = fn; },
    setSelectionRange(a, b) { this.selectionStart = a; this.selectionEnd = b; },
    focus() {},
  };
  let clic;
  const teclado = {hidden: true, addEventListener: (nombre, fn) => { clic = fn; }};
  const ayuda = {hidden: true};
  const panel = {
    hidden: false, dataset: {segundos: '120'}, hasAttribute: () => false, addEventListener() {},
    querySelector(selector) {
      return ({'[name=rut]': input, '.totem-teclado': teclado, '[data-finalizar]': {addEventListener() {}},
        '[data-aviso]': {hidden: true}, '[data-ampliar]': {addEventListener() {}}})[selector] || null;
    },
    querySelectorAll: selector => selector === '[data-solo-js]' ? [ayuda] : [],
  };
  runInNewContext(codigo, {
    document: {querySelector: () => panel}, window: {addEventListener() {}},
    Date: {now: () => 0}, setInterval() {}, FormData: class {}, fetch: async () => ({ok: true}),
  });
  const pulsar = (atributos) => clic({target: {closest: () => ({
    hasAttribute: nombre => nombre in atributos, dataset: atributos,
  })}});
  return {
    input, teclado, ayuda,
    teclas(texto) { for (const tecla of texto) pulsar({tecla}); },
    borrar: () => pulsar({'data-borrar': ''}),
    limpiar: () => pulsar({'data-limpiar': ''}),
    cursor(lugar) { input.selectionStart = input.selectionEnd = lugar; },
    escribirFisico(valor, cursor = valor.length) { input.value = valor; this.cursor(cursor); eventos.input(); },
  };
}

test('El teclado en pantalla pone el guion y los puntos mientras se escribe', () => {
  const caso = conTeclado();
  assert.equal(caso.teclado.hidden, false);
  assert.equal(caso.ayuda.hidden, false, 'La ayuda «se ponen solos» solo aparece con JavaScript');
  ['1', '1-2', '12-3', '123-4', '1.234-5', '12.345-6', '123.456-7', '1.234.567-8'].forEach((esperado, i) => {
    caso.teclas('12345678'[i]);
    assert.equal(caso.input.value, esperado);
  });
  caso.teclas('5');
  assert.equal(caso.input.value, '12.345.678-5');
  assert.equal(caso.input.selectionStart, 12);
  caso.teclas('9');
  assert.equal(caso.input.value, '12.345.678-5', 'No pasa de 8 cifras más el dígito verificador');
});

test('La K va al final como dígito verificador', () => {
  const caso = conTeclado();
  caso.teclas('6000000K');
  assert.equal(caso.input.value, '6.000.000-K');
  const otro = conTeclado();
  otro.teclas('1K2');
  assert.equal(otro.input.value, '1-2', 'Una K que no queda al final se descarta');
});

test('«Borrar» quita el último número y no solo el guion o un punto', () => {
  const caso = conTeclado();
  caso.teclas('123456785');
  caso.borrar();
  assert.equal(caso.input.value, '1.234.567-8');
  caso.cursor(9);  // justo después del guion de «1.234.567-8»
  caso.borrar();
  assert.equal(caso.input.value, '123.456-8', 'Borra el 7 que está antes del guion');
  caso.limpiar();
  assert.equal(caso.input.value, '');
  caso.borrar();
  assert.equal(caso.input.value, '');
});

test('Una tecla en medio del RUT se inserta donde está el cursor', () => {
  const caso = conTeclado();
  caso.teclas('12345685');
  caso.cursor(8);  // «1.234.56|8-5»: después del 6
  caso.teclas('7');
  assert.equal(caso.input.value, '12.345.678-5');
  assert.equal(caso.input.selectionStart, 9, 'El cursor queda después del 7');
});

test('Con teclado físico o al pegar también se da formato', () => {
  const caso = conTeclado();
  caso.escribirFisico('123456785');
  assert.equal(caso.input.value, '12.345.678-5');
  caso.escribirFisico(' 12345678-k ');
  assert.equal(caso.input.value, '12.345.678-K');
  caso.escribirFisico('0012-3');
  assert.equal(caso.input.value, '12-3', 'Sin ceros a la izquierda');
  caso.escribirFisico('1.2345-6', 4);  // cursor después del «3»
  assert.equal(caso.input.value, '12.345-6');
  assert.equal(caso.input.selectionStart, 4);
});
