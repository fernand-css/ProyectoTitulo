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
  const tareas = new Map(), sockets = [], solicitudes = [], eventos = {}, locuciones = [], tonos = [], eventosVoz = {};
  let voces = opciones.voces || [{lang: 'es-CL', name: 'Voz sintética chilena'}], enVoz = null, cancelaciones = 0;
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
    addEventListener: (nombre, fn) => { eventosVoz[nombre] = fn; },
    speak(locucion) {
      assert.equal(enVoz, null, 'No superponer locuciones');
      const registro = {texto: locucion.text, voz: locucion.voice, rate: locucion.rate, cuando: ahora,
        visual: elementos['sala-aviso'].textContent, fin: null, locucion};
      locuciones.push(registro); enVoz = registro;
      if (!opciones.vozBloqueada) registro.timer = programar(() => {
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
    estadoUrl: '/turnos/sala/estado/', WebSocket: opciones.sinWebSocket ? undefined : Socket,
    AbortController, performance: {now: () => ahora},
    speechSynthesis: opciones.sinSintesis ? undefined : sintesis,
    SpeechSynthesisUtterance: class { constructor(text) { this.text = text; } },
    AudioContext: opciones.sinAudio ? undefined : Audio,
    setTimeout: (fn, ms) => programar(fn, ms), clearTimeout: id => tareas.delete(id),
    setInterval: (fn, ms) => programar(fn, ms, true), clearInterval: id => tareas.delete(id),
    addEventListener: (nombre, fn) => { eventos[nombre] = fn; },
    fetch: async (url, datos) => {
      solicitudes.push({url, datos, cuando: ahora});
      return opciones.fetch ? opciones.fetch(url, datos) : {ok: true, json: async () => opciones.respaldo || estado()};
    },
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
  async function respaldo() {
    sockets[0].fallar(); await avanzar(1000);
    sockets[1].fallar(); await avanzar(2000);
    sockets[2].fallar(); await vaciarPromesas();
  }
  async function activar() {
    elementos['sala-activar-sonido'].click(); await vaciarPromesas(); await avanzar(1000);
  }
  return {elementos, sockets, solicitudes, cliente, avanzar, respaldo, eventos, tareas, activar, locuciones, tonos,
    cambiarVoces: nuevas => { voces = nuevas; eventosVoz.voiceschanged?.(); }, cancelaciones: () => cancelaciones};
}

test('pinta estado inicial, conserva el historial y conecta por ws o wss al mismo host', () => {
  for (const https of [false, true]) {
    const a = anuncio();
    const e = entorno({https, inicial: estado({recientes: [a], ultimo_id: 1})});
    assert.equal(e.sockets[0].url, `${https ? 'wss' : 'ws'}://sala.example/ws/sala/`);
    assert.equal(e.elementos['sala-ultimo'].textContent, frase(a));
    assert.match(e.elementos['sala-espera'].textContent, /2 personas en espera23/);
    assert.match(e.elementos['sala-ventanillas'].textContent, /Disponible/);
    assert.equal(e.solicitudes.length, 0);
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

test('tras tres fallos consulta solo GET cada segundo con no-store y sin credenciales', async () => {
  const e = entorno(); await e.respaldo();
  assert.equal(e.solicitudes.length, 1);
  await e.avanzar(1000); assert.equal(e.solicitudes.length, 2);
  await e.avanzar(1000); assert.equal(e.solicitudes.length, 3);
  for (const {url, datos} of e.solicitudes) {
    assert.equal(url, '/turnos/sala/estado/'); assert.equal(datos.method, undefined);
    assert.equal(datos.cache, 'no-store'); assert.equal(datos.credentials, 'omit');
  }
  assert.match(e.elementos['sala-conexion'].textContent, /respaldo/);
});

test('respaldo actualiza llamados y no repite el recibido por el canal', async () => {
  const e = entorno({respaldo: estado({recientes: [anuncio(2)]})});
  e.sockets[0].mensaje(estado({recientes: [anuncio(1)]}));
  await e.respaldo();
  assert.equal(e.elementos['sala-ultimo'].dataset.anuncioId, '2');
  const escrituras = e.elementos['sala-ultimo'].escrituras;
  await e.avanzar(1000);
  assert.equal(e.elementos['sala-ultimo'].escrituras, escrituras);
});

test('recuperar el canal cancela respaldo y reinicia la espera de reconexión', async () => {
  const e = entorno(); await e.respaldo(); await e.avanzar(3000);
  const s = e.sockets.at(-1); s.mensaje(estado());
  const solicitudes = e.solicitudes.length;
  await e.avanzar(1000); assert.equal(e.solicitudes.length, solicitudes);
  s.fallar(); const conexiones = e.sockets.length;
  await e.avanzar(1000); assert.equal(e.sockets.length, conexiones + 1);
});

test('respuesta HTTP pendiente no pisa un estado recuperado por WebSocket', async () => {
  let resolver;
  const e = entorno({fetch: () => new Promise(resolve => { resolver = resolve; })});
  await e.respaldo(); await e.avanzar(3000);
  e.sockets.at(-1).mensaje(estado({recientes: [anuncio(3)]}));
  resolver({ok: true, json: async () => estado({recientes: [anuncio(2)]})}); await vaciarPromesas();
  assert.equal(e.elementos['sala-ultimo'].dataset.anuncioId, '3');
  assert.match(e.elementos['sala-conexion'].textContent, /en vivo/);
});

test('caída total conserva el contenido y pide acercarse a la ventanilla', async () => {
  const e = entorno({inicial: estado({recientes: [anuncio(1)]}), fetch: async () => { throw Error('caída'); }});
  await e.respaldo();
  assert.equal(e.elementos['sala-ultimo'].dataset.anuncioId, '1');
  assert.match(e.elementos['sala-conexion'].textContent, /desactualizada.*Acércate a la ventanilla/);
});

test('respaldo no superpone solicitudes y aborta una bloqueada a los cinco segundos', async () => {
  const e = entorno({fetch: (_, datos) => new Promise((_, reject) => {
    datos.signal.addEventListener('abort', () => reject(Error('abortar')));
  })});
  await e.respaldo(); await e.avanzar(4999);
  assert.equal(e.solicitudes.length, 1);
  await e.avanzar(1001); assert.equal(e.solicitudes[0].datos.signal.aborted, true);
  assert.ok(e.solicitudes.length >= 2);
});

test('sin WebSocket usa HTTP y recupera errores de consulta', async () => {
  let consultas = 0;
  const e = entorno({sinWebSocket: true, fetch: async () => {
    if (++consultas === 1) return {ok: false};
    return {ok: true, json: async () => estado({recientes: [anuncio(4)]})};
  }});
  await vaciarPromesas(); assert.match(e.elementos['sala-conexion'].textContent, /Sin conexión/);
  await e.avanzar(1000); assert.equal(e.elementos['sala-ultimo'].dataset.anuncioId, '4');
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

test('cerrar la página cancela solicitudes, temporizadores y conexión', async () => {
  const e = entorno({fetch: (_, datos) => new Promise((_, reject) => {
    datos.signal.addEventListener('abort', () => reject(Error('abortar')));
  })});
  await e.respaldo(); e.eventos.pagehide(); await vaciarPromesas();
  const solicitudes = e.solicitudes.length, conexiones = e.sockets.length;
  await e.avanzar(60000);
  assert.equal(e.solicitudes.length, solicitudes); assert.equal(e.sockets.length, conexiones);
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

test('respaldo y regreso al WebSocket no duplican avisos hablados', async () => {
  const e = entorno({respaldo: estado({recientes: [anuncio(1)]})});
  e.sockets[0].mensaje(estado()); await e.activar(); await e.respaldo();
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
  assert.equal(e.solicitudes.length, 0);
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
