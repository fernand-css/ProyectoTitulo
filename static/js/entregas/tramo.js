/*
  Tramo por camino desde la posición del encargado (spec 09, enmienda del 2026-11-15, RF-09-21 a RF-09-23 y
  RF-09-26). Lo comparten la pestaña «Mapa» (mapa.js) y «Ir a esta parada» (ir_a.js).

  - La posición se pide al navegador solo con el gesto «Mostrar mi posición» y se sigue (watchPosition) hasta
    «Detener» o hasta salir de la página. Al ocultarla (otra pestaña o ventana minimizada) el seguimiento se pausa
    sin borrar el tramo ni la posición y se reanuda solo al volver (corrección del 2026-11-16).
  - Para el tramo, la posición viaja a Django por POST (con CSRF), solo en esa solicitud; Django consulta a su OSRM
    y nunca la guarda. El navegador no conoce la dirección de OSRM. No se usa la línea recta para mostrar nada:
    la distancia que se ve es la del tramo por camino.
  - El tramo se recalcula al moverse más de 150 m con al menos 20 s desde el cálculo anterior; cerca de la parada
    (último tramo de menos de 500 m), al moverse más de 30 m con al menos 10 s. Si un cálculo falla, se reintenta
    pasados 20 s.
  - Un número de solicitud y AbortController descartan las respuestas que llegan fuera de orden.
  - Sin señal, sin OSRM, sin permiso o sin contexto seguro, todo se dice con texto.
*/
(function (global) {
  "use strict";

  var RADIO_TIERRA_M = 6371000;
  var UMBRALES = {
    lejos: { metros: 150, ms: 20000 },
    cerca: { metros: 30, ms: 10000 },
    tramoCorto: 500,
    reintentoMs: 20000,
  };
  var TEXTOS = {
    sinContexto: "Este navegador no permite usar la ubicación aquí: se necesita una conexión segura (HTTPS). Sigue el orden de la lista o usa tu app de navegación.",
    sinGeo: "Este navegador no puede obtener la ubicación. Sigue el orden de la lista o usa tu app de navegación.",
    sinPermiso: "No diste permiso para usar la ubicación. Sin él no podemos calcular el tramo; sigue el orden de la lista o usa tu app de navegación.",
    sinPosicion: "No pudimos obtener tu posición. Inténtalo al aire libre o sigue el orden de la lista.",
    esperando: "Aún buscamos tu posición. Si tarda, revisa que la ubicación esté activa en el celular.",
    iniciando: "Buscando tu posición. El tramo se actualiza mientras avanzas; pulsa «Detener» para terminar.",
    detenido: "Seguimiento detenido. Tu posición no se guardó.",
    sinRed: "Sin conexión: no se pudo calcular el tramo. Sigue el orden de la lista.",
    sinRedCercana: "Sin conexión: no se pudo calcular la parada más cercana.",
    fallo: "No se pudo calcular el tramo. Sigue el orden de la lista.",
  };

  function radianes(grados) { return (grados * Math.PI) / 180; }

  // Solo para decidir si el encargado se movió lo suficiente; nunca se muestra.
  function movimientoM(desde, hasta) {
    var lat1 = radianes(desde.lat);
    var lat2 = radianes(hasta.lat);
    var dLat = lat2 - lat1;
    var dLon = radianes(hasta.lon - desde.lon);
    var h = Math.pow(Math.sin(dLat / 2), 2) + Math.cos(lat1) * Math.cos(lat2) * Math.pow(Math.sin(dLon / 2), 2);
    return 2 * RADIO_TIERRA_M * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  // Bajo 1 km, en metros redondeados a 10 m; desde 1 km, en km con un decimal y coma decimal.
  function formatearDistancia(metros) {
    var redondeado = Math.round(metros / 10) * 10;
    if (redondeado < 1000) return redondeado + " m";
    return (metros / 1000).toFixed(1).replace(".", ",") + " km";
  }

  // `anterior` es el último cálculo {lat, lon, t, distancia_m} (o un intento fallido, sin distancia).
  function debeRecalcular(anterior, actual, ahora) {
    if (!anterior) return true;
    var transcurrido = ahora - anterior.t;
    if (anterior.fallido) return transcurrido >= UMBRALES.reintentoMs;
    var umbral = anterior.distancia_m < UMBRALES.tramoCorto ? UMBRALES.cerca : UMBRALES.lejos;
    return movimientoM(anterior, actual) > umbral.metros && transcurrido >= umbral.ms;
  }

  function interpretar(status, cuerpo, porDefecto) {
    if (status === 200 && cuerpo && typeof cuerpo.intento === "number") {
      var resultado = { ok: true };
      Object.keys(cuerpo).forEach(function (clave) { resultado[clave] = cuerpo[clave]; });
      return resultado;
    }
    var mensaje = cuerpo && typeof cuerpo.error === "string" && cuerpo.error ? cuerpo.error : porDefecto;
    return { ok: false, mensaje: mensaje, status: status };
  }

  /*
    Cliente de Django: `pedirTramo(intento, posicion)` y `pedirCercana(posicion)`. Cada uno cancela su solicitud
    anterior y descarta respuestas viejas (resultado `{ok: false, descartada: true}`).
  */
  function crearCliente(entorno) {
    var numeros = { tramo: 0, cercana: 0 };
    var controles = { tramo: null, cercana: null };

    function pedir(tipo, url, cuerpo, sinRed) {
      if (entorno.enLinea && entorno.enLinea() === false) return Promise.resolve({ ok: false, mensaje: sinRed, sinRed: true });
      numeros[tipo] += 1;
      var numero = numeros[tipo];
      if (controles[tipo]) controles[tipo].abort();
      controles[tipo] = entorno.AbortController ? new entorno.AbortController() : null;
      var opciones = {
        method: "POST", credentials: "same-origin", body: JSON.stringify(cuerpo),
        headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": entorno.csrf() },
      };
      if (controles[tipo]) opciones.signal = controles[tipo].signal;
      return Promise.resolve()
        .then(function () { return entorno.fetch(url, opciones); })
        .then(function (respuesta) {
          return respuesta.json().then(
            function (datos) { return interpretar(respuesta.status, datos, TEXTOS.fallo); },
            function () { return interpretar(respuesta.status, null, TEXTOS.fallo); });
        }, function () { return { ok: false, mensaje: sinRed, sinRed: true }; })
        .then(function (resultado) {
          if (numero !== numeros[tipo]) return { ok: false, descartada: true };
          return resultado;
        });
    }

    return {
      pedirTramo: function (intento, posicion) {
        return pedir("tramo", entorno.urlTramo, { intento: intento, latitud: posicion.lat, longitud: posicion.lon }, TEXTOS.sinRed);
      },
      pedirCercana: function (posicion) {
        return pedir("cercana", entorno.urlCercana, { latitud: posicion.lat, longitud: posicion.lon }, TEXTOS.sinRedCercana);
      },
      abortar: function () {
        numeros.tramo += 1;
        numeros.cercana += 1;
        ["tramo", "cercana"].forEach(function (tipo) { if (controles[tipo]) controles[tipo].abort(); controles[tipo] = null; });
      },
    };
  }

  /*
    Seguimiento de la posición con recálculo del tramo. `op`: geo (navigator.geolocation), seguro (bool), cliente,
    ahora(), destino() → id de la visita o null, y avisos {inicio, posicion, tramo, error, fin}.
  */
  function crearSeguimiento(op) {
    var vigilancia = null;
    var pausado = false;
    var posicion = null;
    var ultimo = null;

    function avisar(nombre, dato) { if (op.avisos && op.avisos[nombre]) op.avisos[nombre](dato); }

    function calcular() {
      var destino = op.destino();
      if (!posicion || destino == null) return Promise.resolve(null);
      var desde = { lat: posicion.lat, lon: posicion.lon };
      var hora = op.ahora();
      ultimo = { lat: desde.lat, lon: desde.lon, t: hora, fallido: true };
      return op.cliente.pedirTramo(destino, desde).then(function (resultado) {
        if (resultado.descartada || vigilancia === null) return null;
        if (resultado.ok) {
          ultimo = { lat: desde.lat, lon: desde.lon, t: hora, distancia_m: resultado.distancia_m };
          avisar("tramo", resultado);
        } else {
          avisar("error", resultado.mensaje);
        }
        return resultado;
      });
    }

    function alPosicionar(lectura) {
      var coords = lectura.coords;
      posicion = { lat: coords.latitude, lon: coords.longitude, precision: coords.accuracy };
      avisar("posicion", posicion);
      if (debeRecalcular(ultimo, posicion, op.ahora())) calcular();
    }

    function alFallar(error) {
      var codigo = error && error.code;
      if (codigo === 1) {
        detener(true);
        avisar("error", TEXTOS.sinPermiso);
      } else if (codigo === 3) {
        avisar("espera", TEXTOS.esperando);
      } else {
        avisar("error", TEXTOS.sinPosicion);
      }
    }

    function vigilar() {
      vigilancia = op.geo.watchPosition(alPosicionar, alFallar, { enableHighAccuracy: true, maximumAge: 5000, timeout: 30000 });
    }

    function iniciar() {
      if (!op.seguro) { avisar("error", TEXTOS.sinContexto); return false; }
      if (!op.geo) { avisar("error", TEXTOS.sinGeo); return false; }
      if (pausado) return reanudar();
      if (vigilancia !== null) return true;
      ultimo = null;
      vigilar();
      avisar("inicio", TEXTOS.iniciando);
      return true;
    }

    /*
      Pausa al ocultarse la página (otra pestaña o la ventana minimizada): suelta el GPS y la solicitud en curso,
      pero conserva la posición, el tramo dibujado y el último cálculo, sin avisar «fin» (corrección del
      2026-11-16). Al volver a la vista, `reanudar` sigue la posición sin pedir otra vez el gesto.
    */
    function pausar() {
      if (vigilancia === null) return false;
      op.geo.clearWatch(vigilancia);
      vigilancia = null;
      pausado = true;
      op.cliente.abortar();
      if (ultimo && ultimo.fallido) ultimo = null; // la solicitud abortada se repite al reanudar
      return true;
    }

    function reanudar() {
      if (!pausado) return false;
      pausado = false;
      vigilar();
      return true;
    }

    function detener(silencioso) {
      if (vigilancia === null && !pausado) return;
      if (vigilancia !== null) op.geo.clearWatch(vigilancia);
      vigilancia = null;
      pausado = false;
      posicion = null;
      ultimo = null;
      op.cliente.abortar();
      avisar("fin", silencioso === true ? "" : TEXTOS.detenido);
    }

    return {
      iniciar: iniciar,
      detener: detener,
      pausar: pausar,
      reanudar: reanudar,
      pausado: function () { return pausado; },
      // Pausado sigue contando como activo: «Detener» queda disponible y los botones no cambian.
      siguiendo: function () { return vigilancia !== null || pausado; },
      posicion: function () { return posicion; },
      // Cambiar de destino calcula al tiro, sin esperar a moverse.
      recalcular: function () { ultimo = null; return calcular(); },
    };
  }

  var api = {
    UMBRALES: UMBRALES, TEXTOS: TEXTOS, movimientoM: movimientoM, formatearDistancia: formatearDistancia,
    debeRecalcular: debeRecalcular, interpretar: interpretar, crearCliente: crearCliente, crearSeguimiento: crearSeguimiento,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.TramoEntregas = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
