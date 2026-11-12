/*
  «Ir a esta parada» (spec 09, RF-09-09). Pide la ubicación solo con el gesto de «Mostrar mi posición» y la sigue
  (watchPosition) hasta «Detener» o hasta salir u ocultar la página. Con cada posición muestra la distancia en
  línea recta y la dirección en ocho rumbos, y mueve el punto en el mapa si lo hay.

  La posición vive solo en este navegador: el módulo no hace solicitudes de red (sin fetch, XMLHttpRequest,
  sendBeacon ni WebSocket) y no guarda nada. La región aria-live recibe el aviso al iniciar, al pulsar
  «Leer distancia» y al quedar a menos de 100 m; el texto visible se actualiza siempre. Sin contexto seguro, sin
  permiso o sin posición, lo explica con texto; el enlace a la app de navegación y las coordenadas siguen ahí.
*/
(function (global) {
  "use strict";

  var RADIO_TIERRA_M = 6371000;
  var CERCA_M = 100;
  var LEJOS_M = 150; // para volver a avisar «cerca» hay que alejarse primero de este umbral
  var RUMBOS = ["norte", "noreste", "este", "sureste", "sur", "suroeste", "oeste", "noroeste"];
  var TEXTOS = {
    sinContexto: "Este navegador no permite usar la ubicación aquí: se necesita una conexión segura (HTTPS). Usa el enlace a tu app de navegación o las coordenadas.",
    sinPermiso: "No diste permiso para usar la ubicación. Usa el enlace a tu app de navegación o las coordenadas.",
    sinPosicion: "No pudimos obtener tu posición. Inténtalo al aire libre o usa el enlace a tu app de navegación.",
    esperando: "Aún buscamos tu posición. Si tarda, revisa que la ubicación esté activa en el celular.",
    iniciando: "Buscando tu posición. La guía se actualiza mientras avanzas; pulsa «Detener» para terminar.",
    detenido: "Seguimiento detenido. Tu posición no se guardó.",
    sinDatos: "Todavía no tenemos tu posición.",
  };

  function radianes(grados) {
    return (grados * Math.PI) / 180;
  }

  function distanciaM(desde, hasta) {
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

  // Rumbo inicial desde la posición hacia la parada, en ocho direcciones.
  function rumbo(desde, hasta) {
    var lat1 = radianes(desde.lat);
    var lat2 = radianes(hasta.lat);
    var dLon = radianes(hasta.lon - desde.lon);
    var y = Math.sin(dLon) * Math.cos(lat2);
    var x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);
    var grados = ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
    return RUMBOS[Math.round(grados / 45) % 8];
  }

  function texto(numero, metros, direccion, precision) {
    if (metros < CERCA_M) return "Estás a menos de 100 m de la parada " + numero + ".";
    var detalle = Number.isFinite(precision) ? " (precisión ±" + Math.round(precision) + " m)" : "";
    return "La parada " + numero + " está a " + formatearDistancia(metros) + " hacia el " + direccion + detalle + ".";
  }

  /*
    Guía de una parada. `entorno` trae las dependencias (así se prueba con dobles):
    destino {lat, lon, numero}; navegador; ventana; documento; elementos {estado, anuncio, iniciar, leer, detener};
    y, opcional, mapa {actualizar(lat, lon, precision)}.
  */
  function crearGuia(entorno) {
    var destino = entorno.destino;
    var el = entorno.elementos;
    var seguimiento = null;
    var ultimo = null;
    var cerca = false;
    var alternar = false;

    function anunciar(mensaje) {
      // Un espacio duro alternado obliga al lector de pantalla a repetir un aviso igual al anterior.
      alternar = !alternar;
      el.anuncio.textContent = mensaje + (alternar ? "" : " ");
    }

    function mostrar(mensaje) {
      el.estado.textContent = mensaje;
    }

    function botones(activo) {
      el.iniciar.disabled = activo;
      el.leer.disabled = !activo;
      el.detener.disabled = !activo;
    }

    function disponible() {
      return Boolean(entorno.ventana.isSecureContext && entorno.navegador && entorno.navegador.geolocation);
    }

    function textoActual() {
      return ultimo ? texto(destino.numero, ultimo.metros, ultimo.rumbo, ultimo.precision) : TEXTOS.sinDatos;
    }

    function alPosicionar(posicion) {
      var coords = posicion.coords;
      var aqui = { lat: coords.latitude, lon: coords.longitude };
      ultimo = { metros: distanciaM(aqui, destino), rumbo: rumbo(aqui, destino), precision: coords.accuracy };
      mostrar(textoActual());
      if (entorno.mapa) entorno.mapa.actualizar(aqui.lat, aqui.lon, coords.accuracy);
      if (ultimo.metros < CERCA_M && !cerca) {
        cerca = true;
        anunciar(textoActual());
      } else if (ultimo.metros >= LEJOS_M) {
        cerca = false;
      }
    }

    function alFallar(error) {
      var codigo = error && error.code;
      if (codigo === 1) {
        detener(true);
        mostrar(TEXTOS.sinPermiso);
        anunciar(TEXTOS.sinPermiso);
      } else if (codigo === 3) {
        mostrar(TEXTOS.esperando);
      } else {
        mostrar(TEXTOS.sinPosicion);
        anunciar(TEXTOS.sinPosicion);
      }
    }

    function iniciar() {
      if (!disponible()) {
        mostrar(TEXTOS.sinContexto);
        anunciar(TEXTOS.sinContexto);
        return;
      }
      if (seguimiento !== null) return;
      cerca = false;
      botones(true);
      mostrar(TEXTOS.iniciando);
      anunciar(TEXTOS.iniciando);
      seguimiento = entorno.navegador.geolocation.watchPosition(alPosicionar, alFallar, {
        enableHighAccuracy: true, maximumAge: 5000, timeout: 30000,
      });
    }

    function leer() {
      anunciar(textoActual());
    }

    function detener(silencioso) {
      if (seguimiento !== null) {
        entorno.navegador.geolocation.clearWatch(seguimiento);
        seguimiento = null;
        if (silencioso !== true) mostrar(TEXTOS.detenido);
      }
      botones(false);
    }

    el.iniciar.addEventListener("click", iniciar);
    el.leer.addEventListener("click", leer);
    el.detener.addEventListener("click", function () { detener(); });
    entorno.ventana.addEventListener("pagehide", function () { detener(true); });
    entorno.documento.addEventListener("visibilitychange", function () {
      if (entorno.documento.visibilityState === "hidden") detener(true);
    });
    if (!disponible()) mostrar(TEXTOS.sinContexto);

    return {
      iniciar: iniciar,
      leer: leer,
      detener: detener,
      siguiendo: function () { return seguimiento !== null; },
    };
  }

  var api = {
    TEXTOS: TEXTOS,
    distanciaM: distanciaM,
    formatearDistancia: formatearDistancia,
    rumbo: rumbo,
    texto: texto,
    crearGuia: crearGuia,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GuiaParada = api;
    global.document.addEventListener("DOMContentLoaded", function () {
      var documento = global.document;
      var fuente = documento.getElementById("datos-ir-a");
      if (!fuente) return;
      var datos = JSON.parse(fuente.textContent);
      var mapas = (global.MapaEntregas && global.MapaEntregas.mapas) || {};
      crearGuia({
        destino: { lat: datos.lat, lon: datos.lon, numero: datos.numero },
        navegador: global.navigator,
        ventana: global,
        documento: documento,
        mapa: mapas.ir_a || null,
        elementos: {
          estado: documento.getElementById("guia-estado"),
          anuncio: documento.getElementById("guia-anuncio"),
          iniciar: documento.getElementById("guia-iniciar"),
          leer: documento.getElementById("guia-leer"),
          detener: documento.getElementById("guia-detener"),
        },
      });
    });
  }
})(typeof window !== "undefined" ? window : globalThis);
