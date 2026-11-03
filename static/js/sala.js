/* Pantalla pública: solo lectura y memoria de esta visita, sin datos de pacientes. */
(function () {
  "use strict";

  function frase(anuncio) {
    return (anuncio.accion === "rellamado" ? "Nuevamente, número " : "Número ") +
      anuncio.numero + ", ventanilla " + anuncio.ventanilla;
  }

  function crearSonido(e) {
    const pendientes = new Set();
    const osciladores = new Set();
    let activado = false, ocupado = false, contexto = null, voz = null, actual = null;
    let fila = [], generacion = 0, falloVoz = false, falloTono = false;
    function mostrarEstado() {
      let mensaje = activado ? "Sonido activado." : "Sonido desactivado.";
      if (!voz) mensaje += " No hay voz en español en este equipo; se mantienen el tono y el aviso visual.";
      else if (falloVoz) mensaje += " No se pudo reproducir la voz. Activa o prueba el sonido nuevamente.";
      if (falloTono) mensaje += " No se puede emitir el tono en este navegador.";
      if (e.estado.textContent !== mensaje) e.estado.textContent = mensaje;
      e.activar.hidden = activado;
      e.activar.disabled = ocupado;
      e.probar.hidden = !activado;
      e.probar.disabled = ocupado || fila.length > 0;
    }
    function buscarVoz() {
      const voces = e.sintesis && e.Locucion ? e.sintesis.getVoices() : [];
      voz = voces.find(v => v.lang.toLowerCase().replace("_", "-") === "es-cl") ||
        voces.find(v => /^es(?:-|$)/i.test(v.lang.replace("_", "-"))) || null;
      mostrarEstado();
    }
    function esperar(ms) {
      return new Promise(resolve => {
        const terminar = () => { e.clearTimeout(timer); pendientes.delete(terminar); resolve(); };
        const timer = e.setTimeout(terminar, ms);
        pendientes.add(terminar);
      });
    }
    function decir(texto, seleccionada) {
      if (!seleccionada) return Promise.resolve(false);
      return new Promise(resolve => {
        let terminada = false;
        const terminar = exito => {
          if (terminada) return;
          terminada = true;
          e.clearTimeout(timer);
          pendientes.delete(cancelar);
          resolve(exito);
        };
        const cancelar = () => terminar(false);
        const timer = e.setTimeout(() => {
          falloVoz = true;
          terminar(false);
          e.sintesis.cancel();
          mostrarEstado();
        }, 15000);
        pendientes.add(cancelar);
        try {
          const locucion = new e.Locucion(texto);
          locucion.voice = seleccionada;
          locucion.lang = seleccionada.lang;
          locucion.rate = 0.9;
          locucion.onend = () => terminar(true);
          locucion.onerror = evento => {
            if (terminada) return;
            falloVoz = true;
            if (evento.error === "not-allowed") activado = false;
            terminar(false);
            mostrarEstado();
          };
          e.sintesis.speak(locucion);
        } catch (_) {
          falloVoz = true;
          terminar(false);
          mostrarEstado();
        }
      });
    }
    async function tono() {
      try {
        if (!contexto || contexto.state !== "running") throw new Error("tono");
        const inicio = contexto.currentTime;
        [880, 1174].forEach((frecuencia, indice) => {
          const oscilador = contexto.createOscillator();
          const ganancia = contexto.createGain();
          const desde = inicio + indice * 0.18;
          oscilador.frequency.value = frecuencia;
          ganancia.gain.setValueAtTime(0, desde);
          ganancia.gain.linearRampToValueAtTime(0.06, desde + 0.02);
          ganancia.gain.linearRampToValueAtTime(0, desde + 0.16);
          oscilador.connect(ganancia);
          ganancia.connect(contexto.destination);
          osciladores.add(oscilador);
          oscilador.onended = () => {
            osciladores.delete(oscilador); oscilador.disconnect(); ganancia.disconnect();
          };
          oscilador.start(desde);
          oscilador.stop(desde + 0.17);
        });
        falloTono = false;
      } catch (_) { falloTono = true; }
      mostrarEstado();
      await esperar(450);
    }
    function vigente(a) {
      const edad = e.ahora() - Date.parse(a.instante);
      return Number.isFinite(edad) && edad <= 60000;
    }
    async function procesar() {
      if (!activado || ocupado) return;
      while (fila.length && !vigente(fila[0])) fila.shift();
      if (!fila.length) { mostrarEstado(); return; }
      const turno = generacion;
      actual = fila.shift();
      ocupado = true;
      e.alCambiar(actual);
      mostrarEstado();
      const seleccionada = voz;
      const texto = frase(actual);
      await tono();
      if (turno !== generacion) return;
      if (seleccionada) {
        const exito = await decir(texto, seleccionada);
        if (turno !== generacion) return;
        if (exito) {
          await esperar(1500);
          if (turno !== generacion) return;
          await decir(texto, seleccionada);
        }
      } else { await esperar(1500); }
      if (turno !== generacion) return;
      actual = null;
      ocupado = false;
      e.alCambiar(null);
      mostrarEstado();
      procesar();
    }
    function encolar(anuncios) {
      if (!activado) return;
      fila.push(...anuncios.filter(vigente));
      if (fila.length > 5) fila.splice(0, fila.length - 5);
      procesar();
    }
    function probar() {
      if (ocupado) return;
      buscarVoz();
      falloVoz = false;
      try { if (!contexto && e.AudioContext) contexto = new e.AudioContext(); }
      catch (_) { falloTono = true; }
      if (!contexto && !voz) {
        falloTono = true;
        mostrarEstado();
        return;
      }
      const turno = generacion;
      activado = true;
      ocupado = true;
      mostrarEstado();
      // speak se invoca dentro del gesto, sin esperar la promesa de resume.
      const locucion = decir("Prueba de sonido de la pantalla de sala", voz);
      let reanudar;
      try { reanudar = contexto ? contexto.resume() : Promise.resolve(); }
      catch (_) { reanudar = Promise.reject(new Error("audio")); }
      const pruebaTono = Promise.resolve(reanudar).catch(() => {
        if (turno !== generacion) return;
        falloTono = true;
        if (!voz) activado = false;
      }).then(() => turno === generacion ? tono() : undefined);
      Promise.all([locucion, pruebaTono]).then(() => {
        if (turno !== generacion) return;
        ocupado = false;
        mostrarEstado();
        procesar();
      });
    }
    function limpiar() {
      generacion++;
      fila = [];
      for (const cancelar of [...pendientes]) cancelar();
      if (e.sintesis) e.sintesis.cancel();
      for (const oscilador of [...osciladores]) {
        try { oscilador.stop(); } catch (_) { /* Ya finalizó. */ }
        oscilador.disconnect();
      }
      osciladores.clear();
      actual = null;
      ocupado = false;
      e.alCambiar(null);
      mostrarEstado();
    }
    function detener() {
      limpiar();
      activado = false;
      if (contexto) contexto.close().catch(() => {});
      contexto = null;
      mostrarEstado();
    }
    e.activar.addEventListener("click", probar);
    e.probar.addEventListener("click", probar);
    if (e.sintesis) e.sintesis.addEventListener("voiceschanged", buscarVoz);
    buscarVoz();
    return {encolar, limpiar, detener, get actual() { return actual; }};
  }

  function crearSala(e) {
    const d = e.document;
    const inicial = d.getElementById("sala-estado-inicial");
    if (!inicial) return;
    const elementos = {};
    ["ultimo", "ventanillas", "recientes", "espera", "reloj", "conexion", "aviso", "sonido", "activar-sonido", "probar-sonido"].forEach(nombre => {
      elementos[nombre] = d.getElementById("sala-" + nombre);
    });
    const vistos = new Set();
    const ultimosPorVentanilla = new Map();
    const formatoHora = new Intl.DateTimeFormat("es-CL", {timeZone: "America/Santiago", hour: "2-digit", minute: "2-digit"});
    const formatoReloj = new Intl.DateTimeFormat("es-CL", {timeZone: "America/Santiago", dateStyle: "full", timeStyle: "medium"});
    const formatoFecha = new Intl.DateTimeFormat("en", {timeZone: "America/Santiago", year: "numeric", month: "2-digit", day: "2-digit"});
    let estado = null, socket = null, conectado = false, detenido = false;
    let fallos = 0, reintento = null, respaldo = null, consulta = null, epoca = 0;
    let servidor = null, referencia = 0, recibido = e.performance.now();
    let sonido;

    function texto(nodo, valor) {
      if (nodo.textContent !== valor) nodo.textContent = valor;
    }
    function nodo(etiqueta, contenido) {
      const elemento = d.createElement(etiqueta);
      if (contenido !== undefined) elemento.textContent = contenido;
      return elemento;
    }
    function positivo(numero) { return Number.isSafeInteger(numero) && numero > 0; }
    function anuncioValido(a) {
      return a && positivo(a.id) && positivo(a.numero) && positivo(a.ventanilla) &&
        ["llamado", "rellamado"].includes(a.accion) && Number.isFinite(Date.parse(a.instante));
    }
    function estadoValido(s) {
      return s && s.tipo === "estado" && /^\d{4}-\d{2}-\d{2}$/.test(s.fecha) &&
        Number.isFinite(Date.parse(s.ahora)) && Array.isArray(s.recientes) && s.recientes.every(anuncioValido) &&
        Array.isArray(s.ventanillas) && s.ventanillas.every(v => positivo(v.numero) &&
          ["llamado", "disponible", "sin_atencion"].includes(v.estado) && (v.estado !== "llamado" || positivo(v.llamado))) &&
        s.espera && Number.isSafeInteger(s.espera.cantidad) && s.espera.cantidad >= 0 &&
        Number.isSafeInteger(s.espera.restantes) && s.espera.restantes >= 0 &&
        Array.isArray(s.espera.numeros) && s.espera.numeros.every(positivo);
    }
    function sincronizar(ahora) {
      if (Number.isFinite(Date.parse(ahora))) {
        servidor = Date.parse(ahora);
        referencia = e.performance.now();
      }
    }
    function ahoraServidor() {
      return servidor === null ? null : servidor + e.performance.now() - referencia;
    }
    function pintar() {
      if (!estado) return;
      const ultimo = estado.recientes[0];
      if (ultimo && elementos.ultimo.textContent !== frase(ultimo)) {
        const rotulo = nodo("span", ultimo.accion === "rellamado" ? "Nuevamente, número " : "Número ");
        rotulo.className = "sala-rotulo";
        const numero = nodo("strong", String(ultimo.numero)); numero.className = "sala-numero";
        const coma = nodo("span", ","); coma.className = "sr-only";
        const destino = nodo("span"); destino.className = "sala-destino";
        destino.append(d.createTextNode(" ventanilla "), nodo("strong", String(ultimo.ventanilla)));
        elementos.ultimo.replaceChildren(rotulo, numero, coma, destino);
      } else if (!ultimo && elementos.ultimo.textContent !== "Aún no hay llamados hoy.") {
        const vacio = nodo("p", "Aún no hay llamados hoy."); vacio.className = "sala-vacio";
        elementos.ultimo.replaceChildren(vacio);
      }
      elementos.ultimo.dataset.anuncioId = ultimo ? String(ultimo.id) : "";
      const tarjetas = estado.ventanillas.map(v => {
        const tarjeta = nodo("article");
        tarjeta.className = "sala-ventanilla";
        tarjeta.dataset.ventanilla = String(v.numero);
        const contenido = nodo("p", v.estado === "llamado" ? "Número " + v.llamado :
          (v.estado === "disponible" ? "Disponible" : "Sin atención"));
        if (v.estado === "llamado") contenido.className = "sala-turno";
        tarjeta.append(nodo("h3", "Ventanilla " + v.numero), contenido);
        if (sonido && sonido.actual && sonido.actual.ventanilla === v.numero) {
          tarjeta.className += " sala-ventanilla-sonando";
          const marca = nodo("p", "Aviso en curso"); marca.className = "sala-marca-aviso";
          tarjeta.append(marca);
        }
        return tarjeta;
      });
      elementos.ventanillas.replaceChildren(...(tarjetas.length ? tarjetas : [nodo("p", "No hay ventanillas disponibles.")]));
      const recientes = estado.recientes.slice(0, 6).map(a => {
        const item = nodo("li");
        const hora = nodo("time", formatoHora.format(new Date(a.instante)));
        hora.dateTime = a.instante;
        item.append(d.createTextNode(frase(a) + " · "), hora);
        return item;
      });
      elementos.recientes.replaceChildren(...(recientes.length ? recientes : [nodo("li", "Aún no hay llamados hoy.")]));
      if (!estado.espera.cantidad) {
        elementos.espera.replaceChildren(nodo("p", "Nadie en espera."));
      } else {
        const cantidad = nodo("p", estado.espera.cantidad + (estado.espera.cantidad === 1 ? " persona en espera" : " personas en espera"));
        const lista = nodo("ul");
        lista.setAttribute("aria-label", "Números en espera");
        lista.append(...estado.espera.numeros.slice(0, 40).map(n => nodo("li", String(n))));
        elementos.espera.replaceChildren(cantidad, lista);
        if (estado.espera.restantes) elementos.espera.append(nodo("p", "y " + estado.espera.restantes + " más"));
      }
    }
    function cambiarJornada(fecha) {
      if (!estado || fecha === estado.fecha) return;
      vistos.clear();
      ultimosPorVentanilla.clear();
      if (sonido) sonido.limpiar();
      estado = {...estado, fecha, recientes: [], ultimo_id: 0, espera: {cantidad: 0, numeros: [], restantes: 0},
        ventanillas: estado.ventanillas.map(v => ({...v, estado: "sin_atencion", llamado: null, desde: null}))};
    }
    function pintarReloj() {
      const ahora = ahoraServidor();
      if (ahora === null) return;
      const fecha = new Date(ahora);
      const partes = Object.fromEntries(formatoFecha.formatToParts(fecha).map(p => [p.type, p.value]));
      const jornada = partes.year + "-" + partes.month + "-" + partes.day;
      if (estado && jornada > estado.fecha) {
        cambiarJornada(jornada);
        pintar();
      }
      texto(elementos.reloj, formatoReloj.format(fecha));
      elementos.reloj.dateTime = fecha.toISOString();
    }
    function aplicarEstado(datos) {
      if (!estadoValido(datos)) return false;
      if (estado && datos.fecha < estado.fecha) return true; // Respuesta anterior a medianoche.
      cambiarJornada(datos.fecha);
      const nuevos = estado ? datos.recientes.filter(a => !vistos.has(a.id)).sort((a, b) => a.id - b.id) : [];
      datos.recientes.forEach(a => {
        vistos.add(a.id);
        ultimosPorVentanilla.set(a.ventanilla, Math.max(ultimosPorVentanilla.get(a.ventanilla) || 0, a.id));
      });
      estado = {...datos, recientes: [...datos.recientes].sort((a, b) => b.id - a.id)};
      sincronizar(datos.ahora);
      pintar();
      pintarReloj();
      sonido.encolar(nuevos);
      return true;
    }
    function aplicarAnuncio(a) {
      if (!anuncioValido(a) || !estado) return false;
      const partes = Object.fromEntries(formatoFecha.formatToParts(new Date(a.instante)).map(p => [p.type, p.value]));
      const fecha = partes.year + "-" + partes.month + "-" + partes.day;
      if (fecha < estado.fecha || vistos.has(a.id)) return true;
      cambiarJornada(fecha);
      vistos.add(a.id);
      estado.recientes = [a, ...estado.recientes].sort((a, b) => b.id - a.id).slice(0, 20);
      estado.ultimo_id = Math.max(estado.ultimo_id || 0, a.id);
      if (a.id > (ultimosPorVentanilla.get(a.ventanilla) || 0)) {
        ultimosPorVentanilla.set(a.ventanilla, a.id);
        estado.ventanillas = estado.ventanillas.map(v => v.numero === a.ventanilla ?
          {...v, estado: "llamado", llamado: a.numero, desde: a.instante} : v);
      }
      pintar();
      sonido.encolar([a]);
      return true;
    }
    function aviso(mensaje) { texto(elementos.conexion, mensaje); }
    function cancelarConsulta() {
      epoca++;
      if (consulta) consulta.abort();
    }
    async function consultar() {
      if (detenido || conectado || consulta) return;
      const controlador = new e.AbortController();
      consulta = controlador;
      const version = epoca;
      const limite = e.setTimeout(() => controlador.abort(), 5000);
      try {
        const respuesta = await e.fetch(e.estadoUrl, {
          cache: "no-store", credentials: "omit", signal: controlador.signal, headers: {Accept: "application/json"},
        });
        if (!respuesta.ok || respuesta.redirected) throw new Error("estado");
        const datos = await respuesta.json();
        if (detenido || conectado || epoca !== version) return;
        if (!aplicarEstado(datos)) throw new Error("estado");
        aviso("Conexión de respaldo. La pantalla se actualiza cada segundo.");
      } catch (_) {
        if (!detenido && !conectado && epoca === version) {
          aviso("Sin conexión. La información puede estar desactualizada. Acércate a la ventanilla.");
        }
      } finally {
        e.clearTimeout(limite);
        if (consulta === controlador) consulta = null;
      }
    }
    function iniciarRespaldo() {
      if (respaldo !== null || detenido) return;
      respaldo = e.setInterval(consultar, 1000);
      consultar();
    }
    function perder(actual) {
      if (detenido || (actual && socket !== actual)) return;
      const anterior = socket;
      socket = null;
      conectado = false;
      if (anterior) anterior.close();
      fallos++;
      aviso("Sin conexión. Reintentando. La información puede estar desactualizada.");
      if (fallos >= 3) iniciarRespaldo();
      if (e.WebSocket && reintento === null) {
        reintento = e.setTimeout(() => { reintento = null; conectar(); }, Math.min(fallos, 10) * 1000);
      }
    }
    function conectar() {
      if (detenido) return;
      if (!e.WebSocket) { fallos = 2; perder(null); return; }
      recibido = e.performance.now();
      try {
        const url = new URL("/ws/sala/", e.location.href);
        url.protocol = e.location.protocol === "https:" ? "wss:" : "ws:";
        const actual = new e.WebSocket(url.href);
        socket = actual;
        actual.onmessage = evento => {
          if (detenido || socket !== actual) return;
          try {
            const datos = JSON.parse(evento.data);
            let valido = false;
            if (datos.tipo === "estado") {
              valido = aplicarEstado(datos);
              if (valido) {
                conectado = true;
                fallos = 0;
                cancelarConsulta();
                if (respaldo !== null) e.clearInterval(respaldo);
                respaldo = null;
                aviso("Conectada en vivo.");
              }
            } else if (datos.tipo === "anuncio" && conectado) {
              valido = aplicarAnuncio(datos);
            } else if (datos.tipo === "latido" && conectado && Number.isFinite(Date.parse(datos.ahora))) {
              sincronizar(datos.ahora);
              pintarReloj();
              valido = true;
            }
            if (!valido) throw new Error("mensaje");
            recibido = e.performance.now();
          } catch (_) { perder(actual); }
        };
        actual.onclose = () => perder(actual);
        actual.onerror = () => perder(actual);
      } catch (_) { perder(null); }
    }
    sonido = crearSonido({
      estado: elementos.sonido, activar: elementos["activar-sonido"], probar: elementos["probar-sonido"],
      sintesis: e.speechSynthesis, Locucion: e.SpeechSynthesisUtterance, AudioContext: e.AudioContext,
      setTimeout: e.setTimeout, clearTimeout: e.clearTimeout, ahora: ahoraServidor,
      alCambiar: anuncio => {
        elementos.aviso.hidden = !anuncio;
        texto(elementos.aviso, anuncio ? frase(anuncio) : "");
        pintar();
      },
    });
    try { aplicarEstado(JSON.parse(inicial.textContent)); } catch (_) { /* Conservar el HTML hasta recibir estado. */ }
    aviso("Conectando con la sala…");
    let reloj;
    function iniciarReloj() {
      reloj = e.setInterval(() => {
        pintarReloj();
        if (socket && e.performance.now() - recibido >= 30000) perder(socket);
      }, 1000);
    }
    iniciarReloj();
    conectar();
    function detener() {
      detenido = true;
      sonido.detener();
      cancelarConsulta();
      e.clearInterval(reloj);
      if (respaldo !== null) e.clearInterval(respaldo);
      if (reintento !== null) e.clearTimeout(reintento);
      if (socket) socket.close();
      socket = null;
    }
    e.addEventListener("pagehide", detener);
    e.addEventListener("pageshow", evento => {
      if (!evento.persisted || !detenido) return;
      detenido = false;
      fallos = 0;
      reintento = respaldo = consulta = null;
      aviso("Reconectando con la sala…");
      pintarReloj();
      iniciarReloj();
      conectar();
    });
    return {detener};
  }

  if (typeof module !== "undefined" && module.exports) module.exports = {crearSala, frase};
  if (typeof window !== "undefined" && typeof document !== "undefined") {
    crearSala({document, location: window.location, WebSocket: window.WebSocket,
      estadoUrl: document.currentScript.dataset.estadoUrl,
      speechSynthesis: window.speechSynthesis, SpeechSynthesisUtterance: window.SpeechSynthesisUtterance,
      AudioContext: window.AudioContext || window.webkitAudioContext,
      fetch: window.fetch.bind(window), AbortController: window.AbortController,
      performance: window.performance, setTimeout, clearTimeout, setInterval, clearInterval,
      addEventListener: window.addEventListener.bind(window)});
  }
})();
