const {test} = require('node:test');
const assert = require('node:assert/strict');
const {crearSala, frase} = require('../../static/js/sala.js');

class Nodo {
  constructor(etiqueta = '') {
    this.etiqueta = etiqueta; this.children = []; this.dataset = {}; this.attributes = {};
    this.valor = ''; this.escrituras = 0; this.reemplazos = 0; this.eventos = {};
  }
  get textContent() { return this.valor + this.children.map(n => n.textContent).join(''); }
  set textContent(texto) { this.valor = texto; this.children = []; this.escrituras++; }
  append(...nodos) { this.children.push(...nodos); }
  replaceChildren(...nodos) { this.valor = ''; this.children = nodos; this.reemplazos++; }
  setAttribute(nombre, valor) { this.attributes[nombre] = valor; }
  addEventListener(nombre, fn) { this.eventos[nombre] = fn; }
  click() { if (!this.disabled) this.eventos.click?.(); }
}
const anuncio = (id = 1, extra = {}) => ({id, numero: id + 20, ventanilla: 1, accion: 'llamado', instante: '2026-11-03T12:00:00-03:00', ...extra});
const estado = (extra = {}) => ({tipo: 'estado', ahora: '2026-11-03T12:00:00-03:00', fecha: '2026-11-03', ultimo_id: 0,
  ventanillas: [{numero: 1, estado: 'disponible', llamado: null, desde: null}], recientes: [],
  espera: {cantidad: 2, numeros: [2, 3], restantes: 0}, ...extra});
const vaciarPromesas = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };

function entorno(opciones = {}) {
  let ahora = 0, siguiente = 1;
  const tareas = new Map(), sockets = [], eventos = {}, locuciones = [], tonos = [], eventosVoz = {};
  let voces = opciones.voces || [{lang: 'es-CL', name: 'Voz sintética chilena'}], enVoz = null, cancelaciones = 0;
  let pausada = Boolean(opciones.vozPausada), reanudaciones = 0;
  const elementos = Object.fromEntries(['ultimo', 'ventanillas', 'recientes', 'espera', 'reloj', 'conexion', 'aviso', 'sonido', 'activar-sonido', 'probar-sonido']
    .map(nombre => ['sala-' + nombre, new Nodo()]));
  elementos['sala-estado-inicial'] = new Nodo('script');
  elementos['sala-estado-inicial'].textContent = JSON.stringify(opciones.inicial || estado());
  const programar = (fn, demora, repetir = false) => {
    const id = siguiente++; tareas.set(id, {fn, cuando: ahora + demora, demora, repetir}); return id;
  };
  class Socket {
    constructor(url) { this.url = url; this.creado = ahora; this.cerrado = false; sockets.push(this); }
    mensaje(datos) { this.onmessage?.({data: typeof datos === 'string' ? datos : JSON.stringify(datos)}); }
    fallar() { this.onerror?.(); this.onclose?.(); }
    close() { this.cerrado = true; this.onclose?.(); }
  }
  const sintesis = {
    getVoices: () => voces,
    resume() { pausada = false; reanudaciones++; },
    addEventListener: (nombre, fn) => { eventosVoz[nombre] = fn; },
    speak(locucion) {
      assert.equal(enVoz, null, 'No superponer locuciones');
      const registro = {texto: locucion.text, voz: locucion.voice, rate: locucion.rate, cuando: ahora,
        visual: elementos['sala-aviso'].textContent, fin: null, locucion};
      locuciones.push(registro); enVoz = registro;
      if (!opciones.vozBloqueada && !pausada) registro.timer = programar(() => {
        enVoz = null; registro.fin = ahora;
        if (opciones.errorVoz) locucion.onerror?.({error: opciones.errorVoz}); else locucion.onend?.();
      }, 1000);
    },
    cancel() {
      cancelaciones++;
      if (enVoz) {
        const registro = enVoz; enVoz = null; tareas.delete(registro.timer);
        registro.fin = ahora; registro.locucion.onerror?.({error: 'interrupted'});
      }
    },
  };
  class Audio {
    constructor() { this.state = 'suspended'; this.destination = {}; }
    get currentTime() { return ahora / 1000; }
    resume() {
      if (opciones.audioBloqueado) return new Promise(() => {});
      if (opciones.errorAudio) return Promise.reject(Error('audio no disponible'));
      this.state = 'running'; return Promise.resolve();
    }
    close() { this.state = 'closed'; return Promise.resolve(); }
    createOscillator() {
      const tono = {frequency: {}, connect() {}, disconnect() {},
        start: cuando => { tonos.push({cuando: cuando * 1000, frecuencia: tono.frequency.value}); },
        stop(cuando) {
          tareas.delete(this.timer);
          this.timer = programar(() => { tono.onended?.(); }, cuando === undefined ? 0 : Math.max(0, cuando * 1000 - ahora));
        }};
      return tono;
    }
    createGain() {
      return {gain: {setValueAtTime() {}, linearRampToValueAtTime() {}}, connect() {}, disconnect() {}};
    }
  }
  const e = {
    document: {getElementById: id => elementos[id], createElement: etiqueta => new Nodo(etiqueta),
      createTextNode: texto => { const n = new Nodo('#text'); n.textContent = texto; return n; }},
    location: {href: opciones.https ? 'https://sala.example/turnos/sala/' : 'http://sala.example/turnos/sala/',
      protocol: opciones.https ? 'https:' : 'http:'},
    WebSocket: opciones.sinWebSocket ? undefined : Socket,
    performance: {now: () => ahora},
    speechSynthesis: opciones.sinSintesis ? undefined : sintesis,
    SpeechSynthesisUtterance: class { constructor(text) { this.text = text; } },
    AudioContext: opciones.sinAudio ? undefined : Audio,
    setTimeout: (fn, ms) => programar(fn, ms), clearTimeout: id => tareas.delete(id),
    setInterval: (fn, ms) => programar(fn, ms, true), clearInterval: id => tareas.delete(id),
    addEventListener: (nombre, fn) => { eventos[nombre] = fn; },
  };
  const cliente = crearSala(e);
  async function avanzar(ms) {
    const fin = ahora + ms;
    for (;;) {
      const pendiente = [...tareas].filter(([, t]) => t.cuando <= fin).sort((a, b) => a[1].cuando - b[1].cuando || a[0] - b[0])[0];
      if (!pendiente) break;
      const [id, tarea] = pendiente; ahora = tarea.cuando;
      if (tarea.repetir) tarea.cuando += tarea.demora; else tareas.delete(id);
      tarea.fn(); await vaciarPromesas();
    }
    ahora = fin; await vaciarPromesas();
  }
  async function caidas() {
    sockets[0].fallar(); await avanzar(1000);
    sockets[1].fallar(); await avanzar(2000);
    sockets[2].fallar(); await vaciarPromesas();
  }
  async function activar() {
    elementos['sala-activar-sonido'].click(); await vaciarPromesas(); await avanzar(1000);
  }
  return {elementos, sockets, cliente, avanzar, caidas, eventos, tareas, activar, locuciones, tonos,
    cambiarVoces: nuevas => { voces = nuevas; eventosVoz.voiceschanged?.(); }, cancelaciones: () => cancelaciones,
    reanudaciones: () => reanudaciones};
}

test('pinta estado inicial, conserva el historial y conecta por ws o wss al mismo host', () => {
  for (const https of [false, true]) {
    const a = anuncio();
    const e = entorno({https, inicial: estado({recientes: [a], ultimo_id: 1})});
    assert.equal(e.sockets[0].url, `${https ? 'wss' : 'ws'}://sala.example/ws/sala/`);
    assert.equal(e.elementos['sala-ultimo'].textContent, frase(a));
    assert.match(e.elementos['sala-espera'].textContent, /2 personas en espera23/);
    assert.match(e.elementos['sala-ventanillas'].textContent, /Disponible/);
  }
});

test('estado en vivo actualiza ventanillas, espera y recientes sin recargar', () => {
  const e = entorno();
  e.sockets[0].mensaje(estado({recientes: [anuncio()], ultimo_id: 1,
    ventanillas: [{numero: 1, estado: 'llamado', llamado: 21}, {numero: 2, estado: 'sin_atencion', llamado: null}],
    espera: {cantidad: 43, numeros: Array.from({length: 40}, (_, i) => i + 2), restantes: 3}}));
  assert.match(e.elementos['sala-conexion'].textContent, /Conectada en vivo/);
  assert.match(e.elementos['sala-ventanillas'].textContent, /Número 21Ventanilla 2Sin atención/);
  assert.match(e.elementos['sala-espera'].textContent, /y 3 más/);
  assert.equal(e.elementos['sala-espera'].children[1].children.length, 40);
});

test('anuncios se incorporan una vez, incluso con id menor que el cursor', () => {
  const e = entorno(); const s = e.sockets[0]; s.mensaje(estado());
  s.mensaje({tipo: 'anuncio', ...anuncio(8)});
  const reemplazos = e.elementos['sala-recientes'].reemplazos;
  s.mensaje({tipo: 'anuncio', ...anuncio(8)});
  assert.equal(e.elementos['sala-recientes'].reemplazos, reemplazos);
  s.mensaje({tipo: 'anuncio', ...anuncio(7)});
  assert.equal(e.elementos['sala-recientes'].children.length, 2);
  assert.equal(e.elementos['sala-ultimo'].dataset.anuncioId, '8');
  assert.match(e.elementos['sala-ventanillas'].textContent, /Número 28/);
});

test('estado seguido de anuncio duplicado no vuelve a pintar el aviso', () => {
  const a = anuncio(); const e = entorno(); const s = e.sockets[0];
  s.mensaje(estado({recientes: [a], ultimo_id: a.id}));
  const escrituras = e.elementos['sala-ultimo'].escrituras;
  s.mensaje({tipo: 'anuncio', ...a});
  assert.equal(e.elementos['sala-ultimo'].escrituras, escrituras);
});

test('solo muestra seis recientes, y un cierre conserva el historial', () => {
  const e = entorno(); const s = e.sockets[0];
  s.mensaje(estado({recientes: Array.from({length: 20}, (_, i) => anuncio(i + 1)), ultimo_id: 20}));
  assert.equal(e.elementos['sala-recientes'].children.length, 6);
  assert.equal(e.elementos['sala-ultimo'].dataset.anuncioId, '20');
  s.mensaje(estado({recientes: [anuncio(20)], ventanillas: [{numero: 1, estado: 'disponible'}]}));
  assert.match(e.elementos['sala-ventanillas'].textContent, /Disponible/);
  assert.equal(e.elementos['sala-ultimo'].dataset.anuncioId, '20');
});

test('reconecta con esperas de uno a diez segundos sin duplicar por error y cierre', async () => {
  const e = entorno();
  for (let i = 0; i < 12; i++) {
    const s = e.sockets.at(-1); s.fallar();
    const numero = e.sockets.length, espera = Math.min(i + 1, 10) * 1000;
    await e.avanzar(espera - 1); assert.equal(e.sockets.length, numero);
    await e.avanzar(1); assert.equal(e.sockets.length, numero + 1);
  }
});

test('tras varias caídas recupera el canal y vuelve a reintentar si se cae de nuevo', async () => {
  const e = entorno(); await e.caidas(); await e.avanzar(3000);
  const s = e.sockets.at(-1); s.mensaje(estado());
  assert.match(e.elementos['sala-conexion'].textContent, /en vivo/);
  s.fallar(); const conexiones = e.sockets.length;
  await e.avanzar(1000); assert.equal(e.sockets.length, conexiones + 1);
});

test('caída total conserva el contenido y pide acercarse a la ventanilla', async () => {
  const e = entorno({inicial: estado({recientes: [anuncio(1)]})});
  await e.caidas();
  assert.equal(e.elementos['sala-ultimo'].dataset.anuncioId, '1');
  assert.match(e.elementos['sala-conexion'].textContent, /desactualizada.*Acércate a la ventanilla/);
});

test('sin WebSocket lo dice en texto, conserva el contenido y no intenta conectar', async () => {
  const e = entorno({sinWebSocket: true, inicial: estado({recientes: [anuncio(4)]})});
  await e.avanzar(60000);
  assert.match(e.elementos['sala-conexion'].textContent, /no admite la conexión en vivo/);
  assert.equal(e.elementos['sala-ultimo'].dataset.anuncioId, '4');
  assert.equal(e.sockets.length, 0);
});

test('si pasan treinta segundos sin estado ni latido cierra y reconecta', async () => {
  const e = entorno(); const s = e.sockets[0]; s.mensaje(estado());
  await e.avanzar(29000); assert.equal(s.cerrado, false);
  await e.avanzar(1000); assert.equal(s.cerrado, true);
  assert.match(e.elementos['sala-conexion'].textContent, /Sin conexión/);
  await e.avanzar(1000); assert.equal(e.sockets.length, 2);
});

test('latidos mantienen la conexión y corrigen el reloj con hora del servidor', async () => {
  const e = entorno(); const s = e.sockets[0]; s.mensaje(estado());
  for (let i = 1; i <= 3; i++) {
    await e.avanzar(15000);
    s.mensaje({tipo: 'latido', ahora: `2026-11-03T12:00:${String(i * 15).padStart(2, '0')}-03:00`});
  }
  assert.equal(s.cerrado, false);
  assert.equal(e.elementos['sala-reloj'].dateTime, '2026-11-03T15:00:45.000Z');
});

test('reloj avanza desde el servidor con tiempo monotónico, sin usar el reloj local', async () => {
  const e = entorno(); await e.avanzar(2000);
  assert.equal(e.elementos['sala-reloj'].dateTime, '2026-11-03T15:00:02.000Z');
  assert.match(e.elementos['sala-reloj'].textContent, /12:00:02/);
});

test('medianoche chilena limpia la jornada anterior aun sin conexión', async () => {
  const e = entorno({inicial: estado({ahora: '2026-11-03T23:59:59-03:00', recientes: [anuncio()]})});
  await e.avanzar(1000);
  assert.equal(e.elementos['sala-ultimo'].dataset.anuncioId, '');
  assert.match(e.elementos['sala-espera'].textContent, /Nadie en espera/);
  e.sockets[0].mensaje(estado({recientes: [anuncio()]}));
  assert.equal(e.elementos['sala-ultimo'].dataset.anuncioId, '');
});

test('ignora anuncios de jornadas anteriores y admite ids nuevos de la jornada siguiente', () => {
  const e = entorno(); const s = e.sockets[0]; s.mensaje(estado());
  s.mensaje({tipo: 'anuncio', ...anuncio(1, {instante: '2026-11-02T12:00:00-03:00'})});
  assert.equal(e.elementos['sala-ultimo'].dataset.anuncioId, '');
  s.mensaje({tipo: 'anuncio', ...anuncio(2, {instante: '2026-11-04T12:00:00-03:00'})});
  assert.equal(e.elementos['sala-ultimo'].dataset.anuncioId, '2');
});

test('datos inválidos del canal conservan lo mostrado y fuerzan recuperación', () => {
  for (const datos of ['{invalido', {tipo: 'estado'}, {tipo: 'anuncio', id: 1}, {tipo: 'desconocido'}]) {
    const e = entorno({inicial: estado({recientes: [anuncio()]})});
    e.sockets[0].mensaje(datos);
    assert.equal(e.elementos['sala-ultimo'].dataset.anuncioId, '1');
    assert.equal(e.sockets[0].cerrado, true);
  }
});

test('eventos de un socket anterior no modifican una conexión nueva', async () => {
  const e = entorno(); const viejo = e.sockets[0]; viejo.fallar(); await e.avanzar(1000);
  e.sockets[1].mensaje(estado({recientes: [anuncio(2)]}));
  viejo.mensaje(estado({recientes: [anuncio(1)]})); viejo.fallar();
  assert.equal(e.elementos['sala-ultimo'].dataset.anuncioId, '2');
  assert.match(e.elementos['sala-conexion'].textContent, /en vivo/);
});

test('cerrar la página cancela temporizadores y conexión', async () => {
  const e = entorno();
  await e.caidas(); e.eventos.pagehide(); await vaciarPromesas();
  const conexiones = e.sockets.length;
  await e.avanzar(60000);
  assert.equal(e.sockets.length, conexiones);
  assert.equal(e.tareas.size, 0); assert.ok(e.sockets.every(s => s.cerrado));
});

test('un anuncio tardío no vuelve a ocupar una ventanilla cuya atención ya terminó', () => {
  const e = entorno(); const s = e.sockets[0];
  s.mensaje(estado({recientes: [anuncio(8)], ventanillas: [{numero: 1, estado: 'disponible'}]}));
  s.mensaje({tipo: 'anuncio', ...anuncio(7)});
  assert.match(e.elementos['sala-ventanillas'].textContent, /Disponible/);
  assert.equal(e.elementos['sala-recientes'].children.length, 2);
});

test('volver con el historial del navegador reactiva el reloj y recupera estado sin perder deduplicación', async () => {
  const e = entorno(); e.sockets[0].mensaje(estado({recientes: [anuncio(1)]}));
  e.eventos.pagehide(); await e.avanzar(10000);
  e.eventos.pageshow({persisted: true});
  assert.equal(e.sockets.length, 2);
  e.sockets[1].mensaje(estado({recientes: [anuncio(2), anuncio(1)]}));
  const reemplazos = e.elementos['sala-recientes'].reemplazos;
  e.sockets[1].mensaje({tipo: 'anuncio', ...anuncio(1)});
  assert.equal(e.elementos['sala-recientes'].reemplazos, reemplazos);
  await e.avanzar(1000);
  assert.equal(e.elementos['sala-reloj'].dateTime, '2026-11-03T15:00:01.000Z');
});

const avisosHablados = e => e.locuciones.filter(l => !l.texto.startsWith('Prueba de sonido'));

test('sin gesto no hay tono ni voz y el historial no se reproduce al activar', async () => {
  const e = entorno({inicial: estado({recientes: [anuncio(1)]})});
  e.sockets[0].mensaje(estado({recientes: [anuncio(2), anuncio(1)]}));
  assert.match(e.elementos['sala-sonido'].textContent, /^Sonido desactivado/);
  assert.equal(e.elementos['sala-activar-sonido'].hidden, false);
  assert.equal(e.locuciones.length, 0); assert.equal(e.tonos.length, 0);
  e.elementos['sala-activar-sonido'].click();
  assert.equal(e.locuciones.length, 1, 'La prueba se solicita dentro del gesto, sin esperar resume');
  await vaciarPromesas(); await e.avanzar(2000);
  assert.match(e.elementos['sala-sonido'].textContent, /^Sonido activado/);
  assert.equal(avisosHablados(e).length, 0);
  assert.equal(e.elementos['sala-probar-sonido'].hidden, false);
});

test('llamado y rellamado dicen exactamente la frase visual dos veces con pausa de 1,5 s', async () => {
  const e = entorno(); const s = e.sockets[0]; s.mensaje(estado()); await e.activar();
  for (const a of [anuncio(1), anuncio(2, {accion: 'rellamado'})]) {
    const inicio = e.locuciones.length;
    s.mensaje({tipo: 'anuncio', ...a});
    assert.equal(e.elementos['sala-aviso'].textContent, frase(a));
    assert.match(e.elementos['sala-ventanillas'].textContent, /Aviso en curso/);
    assert.equal(e.elementos['sala-probar-sonido'].disabled, true);
    await e.avanzar(449); assert.equal(e.locuciones.length, inicio);
    await e.avanzar(1); assert.equal(e.locuciones.at(-1).texto, frase(a));
    await e.avanzar(1000 + 1499); assert.equal(e.locuciones.length, inicio + 1);
    await e.avanzar(1); assert.equal(e.locuciones.length, inicio + 2);
    await e.avanzar(1000);
    const dos = e.locuciones.slice(inicio);
    assert.deepEqual(dos.map(l => l.texto), [frase(a), frase(a)]);
    assert.ok(dos.every(l => l.visual === l.texto && l.rate === 0.9));
    assert.equal(dos[1].cuando - dos[0].fin, 1500);
    assert.equal(e.elementos['sala-aviso'].hidden, true);
  }
  assert.deepEqual(e.tonos.slice(-4).map(t => t.frecuencia), [880, 1174, 880, 1174]);
});

test('fila no interrumpe el aviso actual, conserva cinco pendientes y descarta el más antiguo', async () => {
  const e = entorno(); const s = e.sockets[0]; s.mensaje(estado()); await e.activar();
  for (let id = 1; id <= 7; id++) s.mensaje({tipo: 'anuncio', ...anuncio(id)});
  assert.match(e.elementos['sala-recientes'].textContent, /Número 22/);
  await e.avanzar(25000);
  assert.deepEqual(avisosHablados(e).map(l => l.texto), [1, 3, 4, 5, 6, 7].flatMap(id => [frase(anuncio(id)), frase(anuncio(id))]));
  assert.ok(e.locuciones.every((l, i, todas) => i === 0 || l.cuando >= todas[i - 1].fin));
});

test('un lote de seis perdidos conserva los cinco más recientes y todos siguen visibles', async () => {
  const e = entorno(); const s = e.sockets[0]; s.mensaje(estado()); await e.activar();
  s.fallar(); await e.avanzar(1000);
  e.sockets[1].mensaje(estado({ahora: '2026-11-03T12:00:02-03:00',
    recientes: [6, 5, 4, 3, 2, 1].map(id => anuncio(id))}));
  assert.equal(e.elementos['sala-recientes'].children.length, 6);
  await e.avanzar(21000);
  assert.deepEqual(avisosHablados(e).map(l => l.texto), [2, 3, 4, 5, 6].flatMap(id => [frase(anuncio(id)), frase(anuncio(id))]));
});

test('anuncio de más de 60 s no se habla y uno exactamente de 60 s se completa', async () => {
  const e = entorno(); const s = e.sockets[0]; s.mensaje(estado()); await e.activar();
  s.mensaje({tipo: 'anuncio', ...anuncio(1, {instante: '2026-11-03T11:59:00-03:00'})});
  s.mensaje({tipo: 'anuncio', ...anuncio(2, {instante: '2026-11-03T11:59:01-03:00'})});
  await e.avanzar(4000);
  assert.deepEqual(avisosHablados(e).map(l => l.texto), [frase(anuncio(2)), frase(anuncio(2))]);
  assert.match(e.elementos['sala-recientes'].textContent, /Número 21/);
});

test('pequeña diferencia con el reloj del servidor no hace perder un aviso recién confirmado', async () => {
  const e = entorno(); const s = e.sockets[0]; s.mensaje(estado()); await e.activar();
  s.mensaje({tipo: 'anuncio', ...anuncio(1, {instante: '2026-11-03T12:00:01.010-03:00'})});
  await e.avanzar(4000); assert.equal(avisosHablados(e).length, 2);
});

test('reconexión a los 20 s habla solo el perdido vigente, sin repetir el ya dicho', async () => {
  const e = entorno(); const s = e.sockets[0]; s.mensaje(estado()); await e.activar();
  s.mensaje({tipo: 'anuncio', ...anuncio(1)}); await e.avanzar(4000);
  s.fallar(); await e.avanzar(20000);
  e.sockets.at(-1).mensaje(estado({ahora: '2026-11-03T12:00:25-03:00', recientes: [anuncio(2), anuncio(1)]}));
  await e.avanzar(4000);
  assert.deepEqual(avisosHablados(e).map(l => l.texto), [1, 1, 2, 2].map(id => frase(anuncio(id))));
});

test('reconectar tras caídas no duplica avisos hablados', async () => {
  const e = entorno();
  e.sockets[0].mensaje(estado()); await e.activar(); await e.caidas(); await e.avanzar(3000);
  e.sockets.at(-1).mensaje(estado({recientes: [anuncio(1)]}));
  await e.avanzar(4000);
  e.sockets.at(-1).mensaje(estado({recientes: [anuncio(1)]}));
  await e.avanzar(4000);
  assert.equal(avisosHablados(e).length, 2);
});

test('prefiere es-CL y luego otra voz española, nunca usa voz de otro idioma', async () => {
  for (const voces of [[{lang: 'en-US'}, {lang: 'es-ES'}, {lang: 'es-CL'}], [{lang: 'en-US'}, {lang: 'es-MX'}]]) {
    const e = entorno({voces}); e.sockets[0].mensaje(estado()); await e.activar();
    assert.equal(e.locuciones[0].voz.lang, voces.at(-1).lang);
  }
});

test('sin voz española avisa en texto y conserva tono y aviso visual', async () => {
  const e = entorno({voces: [{lang: 'en-US'}]}); const s = e.sockets[0]; s.mensaje(estado());
  await e.activar(); const tonos = e.tonos.length;
  s.mensaje({tipo: 'anuncio', ...anuncio(1)});
  assert.equal(e.elementos['sala-aviso'].textContent, frase(anuncio(1)));
  await e.avanzar(2000);
  assert.equal(e.locuciones.length, 0); assert.equal(e.tonos.length, tonos + 2);
  assert.match(e.elementos['sala-sonido'].textContent, /No hay voz en español/);
});

test('voiceschanged permite usar una voz española que se carga después de abrir', async () => {
  const e = entorno({voces: []}); const s = e.sockets[0]; s.mensaje(estado()); await e.activar();
  e.cambiarVoces([{lang: 'es-CL'}]);
  assert.doesNotMatch(e.elementos['sala-sonido'].textContent, /No hay voz/);
  s.mensaje({tipo: 'anuncio', ...anuncio(1)}); await e.avanzar(4000);
  assert.equal(avisosHablados(e).length, 2);
});

test('Probar sonido funciona localmente y no interrumpe un llamado', async () => {
  const e = entorno(); e.sockets[0].mensaje(estado()); await e.activar();
  e.sockets[0].mensaje({tipo: 'anuncio', ...anuncio(1)});
  e.elementos['sala-probar-sonido'].click(); await e.avanzar(4000);
  assert.equal(e.locuciones.filter(l => l.texto.startsWith('Prueba')).length, 1);
  e.elementos['sala-probar-sonido'].click(); await vaciarPromesas(); await e.avanzar(1000);
  assert.equal(e.locuciones.filter(l => l.texto.startsWith('Prueba')).length, 2);
});

test('rechazo de voz por el navegador muestra sonido desactivado y permite reactivarlo', async () => {
  const e = entorno({errorVoz: 'not-allowed'}); await e.activar();
  assert.match(e.elementos['sala-sonido'].textContent, /^Sonido desactivado.*No se pudo reproducir la voz/);
  assert.equal(e.elementos['sala-activar-sonido'].hidden, false);
  assert.equal(e.elementos['sala-activar-sonido'].disabled, false);
});

test('sin APIs de sonido no finge activación y conserva el contenido visual', async () => {
  const e = entorno({sinAudio: true, sinSintesis: true}); await e.activar();
  e.sockets[0].mensaje(estado({recientes: [anuncio(1)]}));
  assert.match(e.elementos['sala-sonido'].textContent, /^Sonido desactivado/);
  assert.match(e.elementos['sala-sonido'].textContent, /No se puede emitir el tono/);
  assert.equal(e.elementos['sala-ultimo'].dataset.anuncioId, '1');
});

test('fallo de audio sin voz española no muestra una activación que no pudo realizar', async () => {
  const e = entorno({voces: [], errorAudio: true}); await e.activar();
  assert.match(e.elementos['sala-sonido'].textContent, /^Sonido desactivado/);
  assert.equal(e.tonos.length, 0); assert.equal(e.locuciones.length, 0);
});

test('medianoche cancela el aviso anterior y la fila sin pronunciar su segunda repetición', async () => {
  const e = entorno({inicial: estado({ahora: '2026-11-03T23:59:57-03:00'})});
  e.sockets[0].mensaje(estado({ahora: '2026-11-03T23:59:57-03:00'})); await e.activar();
  e.sockets[0].mensaje({tipo: 'anuncio', ...anuncio(1, {instante: '2026-11-03T23:59:58-03:00'})});
  e.sockets[0].mensaje({tipo: 'anuncio', ...anuncio(2, {instante: '2026-11-03T23:59:58-03:00'})});
  await e.avanzar(6000);
  assert.equal(avisosHablados(e).length, 1);
  assert.equal(e.elementos['sala-aviso'].hidden, true);
  assert.equal(e.elementos['sala-ultimo'].dataset.anuncioId, '');
});

test('salir cancela voz, tono, fila y temporizadores sin reanudar anuncios antiguos al volver', async () => {
  const e = entorno(); e.sockets[0].mensaje(estado()); await e.activar();
  e.sockets[0].mensaje({tipo: 'anuncio', ...anuncio(1)});
  await e.avanzar(500); e.eventos.pagehide(); await vaciarPromesas(); await e.avanzar(6000);
  assert.equal(e.tareas.size, 0); assert.equal(e.elementos['sala-aviso'].hidden, true);
  assert.equal(avisosHablados(e).length, 1);
  assert.match(e.elementos['sala-sonido'].textContent, /^Sonido desactivado/);
  e.eventos.pageshow({persisted: true}); e.sockets.at(-1).mensaje(estado({recientes: [anuncio(1)]}));
  await e.activar(); await e.avanzar(4000);
  assert.equal(avisosHablados(e).length, 1);
});

test('aviso que caduca esperando no se pronuncia, pero permanece visible', async () => {
  const e = entorno(); const s = e.sockets[0]; s.mensaje(estado()); await e.activar();
  s.mensaje({tipo: 'anuncio', ...anuncio(1)});
  s.mensaje({tipo: 'anuncio', ...anuncio(2, {instante: '2026-11-03T11:59:02-03:00'})});
  await e.avanzar(8000);
  assert.deepEqual(avisosHablados(e).map(l => l.texto), [frase(anuncio(1)), frase(anuncio(1))]);
  assert.match(e.elementos['sala-recientes'].textContent, /Número 22/);
});

test('una síntesis que no notifica fin se cancela tras 15 s y la fila sigue avanzando', async () => {
  const opciones = {};
  const e = entorno(opciones); const s = e.sockets[0]; s.mensaje(estado()); await e.activar();
  opciones.vozBloqueada = true;
  s.mensaje({tipo: 'anuncio', ...anuncio(1)});
  s.mensaje({tipo: 'anuncio', ...anuncio(2)});
  await e.avanzar(16000);
  assert.deepEqual(avisosHablados(e).map(l => l.texto), [frase(anuncio(1)), frase(anuncio(2))]);
  assert.ok(e.cancelaciones() >= 1);
  assert.match(e.elementos['sala-sonido'].textContent, /No se pudo reproducir la voz/);
  e.eventos.pagehide(); await vaciarPromesas(); await e.avanzar(1000);
  assert.equal(e.tareas.size, 0);
});

test('la activación muestra prueba en curso hasta que termina, sin anunciar éxito anticipado', async () => {
  const e = entorno();
  e.elementos['sala-activar-sonido'].click();
  assert.match(e.elementos['sala-sonido'].textContent, /^Probando sonido/);
  await vaciarPromesas(); await e.avanzar(1000);
  assert.match(e.elementos['sala-sonido'].textContent, /^Sonido activado/);
});

test('activar reanuda una síntesis pausada para que la prueba y los llamados se reproduzcan', async () => {
  const e = entorno({vozPausada: true}); const s = e.sockets[0]; s.mensaje(estado());
  await e.activar();
  assert.ok(e.reanudaciones() >= 1);
  s.mensaje({tipo: 'anuncio', ...anuncio(1)}); await e.avanzar(4000);
  assert.equal(avisosHablados(e).length, 2);
});

test('si el navegador no termina de activar audio, libera el botón y permite reintentar', async () => {
  const e = entorno({voces: [], audioBloqueado: true});
  e.elementos['sala-activar-sonido'].click(); await vaciarPromesas(); await e.avanzar(6000);
  assert.equal(e.elementos['sala-activar-sonido'].hidden, false);
  assert.equal(e.elementos['sala-activar-sonido'].disabled, false);
  assert.match(e.elementos['sala-sonido'].textContent, /^Sonido desactivado/);
  e.eventos.pagehide(); await vaciarPromesas(); await e.avanzar(1000);
  assert.equal(e.tareas.size, 0);
});

test('si fallan voz y tono, no informa que el sonido está activado', async () => {
  const e = entorno({errorVoz: 'synthesis-failed', errorAudio: true}); await e.activar();
  assert.match(e.elementos['sala-sonido'].textContent, /^Sonido desactivado/);
  assert.equal(e.elementos['sala-activar-sonido'].hidden, false);
  assert.equal(e.elementos['sala-activar-sonido'].disabled, false);
});

test('sin estado inicial del canal sale de Conectando tras cinco segundos y reintenta', async () => {
  const e = entorno(); await e.avanzar(5000);
  assert.equal(e.sockets[0].cerrado, true);
  assert.match(e.elementos['sala-conexion'].textContent, /Sin conexión/);
  await e.avanzar(1000); assert.equal(e.sockets.length, 2);
});

test('el arranque en el navegador ata los temporizadores a window', async () => {
  const vm = require('node:vm');
  const fs = require('node:fs');
  const path = require('node:path');
  const contexto = vm.createContext({});
  const g = vm.runInContext('globalThis', contexto);
  // Como en el navegador: invocar un temporizador como método de otro objeto es un error.
  const estricto = nombre => function () {
    'use strict';
    if (this !== undefined && this !== g) throw new TypeError(`'${nombre}' called on an object that does not implement interface Window.`);
    return 1;
  };
  for (const nombre of ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval']) g[nombre] = estricto(nombre);
  const nodos = Object.fromEntries(['ultimo', 'ventanillas', 'recientes', 'espera', 'reloj', 'conexion', 'aviso', 'sonido', 'activar-sonido', 'probar-sonido', 'estado-inicial']
    .map(nombre => ['sala-' + nombre, new Nodo()]));
  nodos['sala-estado-inicial'].textContent = JSON.stringify(estado());
  g.window = g;
  g.location = {href: 'http://sala.example/turnos/sala/', protocol: 'http:'};
  g.WebSocket = class { close() {} };
  g.addEventListener = () => {};
  g.performance = {now: () => 0};
  g.document = {
    getElementById: id => nodos[id], createElement: etiqueta => new Nodo(etiqueta),
    createTextNode: texto => { const n = new Nodo('#text'); n.textContent = texto; return n; }};
  const codigo = fs.readFileSync(path.join(__dirname, '../../static/js/sala.js'), 'utf8');
  assert.doesNotThrow(() => vm.runInContext(codigo, contexto));
});
