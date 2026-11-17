/*
  «Ir a esta parada» por camino (spec 09, enmienda del 2026-11-15, RF-09-23, que reemplaza a RF-09-09 en lo que se
  le oponga). Pide la ubicación solo con el gesto de «Mostrar mi posición» y la sigue (watchPosition) hasta
  «Detener» o hasta salir de la página; al ocultarla se pausa sin borrar el tramo y se reanuda al volver. Con tramo.js pide a Django el tramo por camino hasta la parada y
  muestra su distancia («La parada 3 está a 1,2 km por camino»); el mapa dibuja ese tramo. Ya no hay línea recta,
  distancia en línea recta ni rumbo.

  La posición viaja a Django solo para calcular el tramo; no se guarda. La región aria-live recibe el aviso al
  iniciar, al pulsar «Leer distancia» y al quedar a menos de 100 m por camino; el texto visible se actualiza
  siempre. Sin contexto seguro, sin permiso, sin posición, sin señal o sin OSRM, lo explica con texto y no muestra
  distancia; el enlace a la app de navegación y las coordenadas siguen ahí.
*/
(function (global) {
  "use strict";

  var CERCA_M = 100;
  var LEJOS_M = 150; // para volver a avisar «cerca» hay que alejarse primero de este umbral
  var TEXTOS = {
    sinDatos: "Todavía no tenemos el tramo por camino.",
  };

  function formatear(metros) {
    var tramo = global.TramoEntregas || (typeof require === "function" ? require("./tramo.js") : null);
    return tramo.formatearDistancia(metros);
  }

  function texto(numero, metros) {
    if (metros < CERCA_M) return "Estás a menos de 100 m por camino de la parada " + numero + ".";
    return "La parada " + numero + " está a " + formatear(metros) + " por camino.";
  }

  /*
    Guía de una parada. `entorno` trae las dependencias (así se prueba con dobles): destino {intento, numero};
    crearSeguimiento(op) (de tramo.js, ya con geo, cliente y reloj); ventana; documento;
    elementos {estado, anuncio, iniciar, leer, detener}; y, opcional, mapa {actualizar, dibujarTramo, limpiar,
    limpiarTramo}.
  */
  function crearGuia(entorno) {
    var destino = entorno.destino;
    var el = entorno.elementos;
    var metros = null;
    var cerca = false;
    var alternar = false;

    function anunciar(mensaje) {
      // Un espacio duro alternado obliga al lector de pantalla a repetir un aviso igual al anterior.
      alternar = !alternar;
      el.anuncio.textContent = mensaje + (alternar ? "" : " ");
    }

    function mostrar(mensaje) { el.estado.textContent = mensaje; }

    function botones(activo) {
      el.iniciar.disabled = activo;
      el.leer.disabled = !activo;
      el.detener.disabled = !activo;
    }

    function textoActual() { return metros === null ? TEXTOS.sinDatos : texto(destino.numero, metros); }

    var seguimiento = entorno.crearSeguimiento({
      destino: function () { return destino.intento; },
      avisos: {
        inicio: function (mensaje) { cerca = false; botones(true); mostrar(mensaje); anunciar(mensaje); },
        posicion: function (p) { if (entorno.mapa) entorno.mapa.actualizar(p.lat, p.lon, p.precision); },
        tramo: function (resultado) {
          metros = resultado.distancia_m;
          if (entorno.mapa) entorno.mapa.dibujarTramo(resultado.geometria);
          mostrar(textoActual());
          if (metros < CERCA_M && !cerca) {
            cerca = true;
            anunciar(textoActual());
          } else if (metros >= LEJOS_M) {
            cerca = false;
          }
        },
        error: function (mensaje) {
          metros = null;
          if (entorno.mapa) entorno.mapa.limpiarTramo();
          mostrar(mensaje);
          anunciar(mensaje);
          if (!seguimiento || !seguimiento.siguiendo()) botones(false);
        },
        espera: function (mensaje) { mostrar(mensaje); },
        fin: function (mensaje) {
          metros = null;
          if (entorno.mapa) entorno.mapa.limpiar();
          botones(false);
          if (mensaje) mostrar(mensaje);
        },
      },
    });

    el.iniciar.addEventListener("click", function () { seguimiento.iniciar(); });
    el.leer.addEventListener("click", function () { anunciar(textoActual()); });
    el.detener.addEventListener("click", function () { seguimiento.detener(); });
    entorno.ventana.addEventListener("pagehide", function () { seguimiento.detener(true); });
    // Oculta (otra pestaña o ventana minimizada): pausa sin borrar el tramo; al volver, sigue sola.
    entorno.documento.addEventListener("visibilitychange", function () {
      if (entorno.documento.visibilityState === "hidden") seguimiento.pausar();
      else seguimiento.reanudar();
    });
    botones(false);

    return {
      iniciar: function () { return seguimiento.iniciar(); },
      leer: function () { anunciar(textoActual()); },
      detener: function (silencioso) { seguimiento.detener(silencioso); },
      siguiendo: function () { return seguimiento.siguiendo(); },
    };
  }

  var api = { TEXTOS: TEXTOS, CERCA_M: CERCA_M, texto: texto, crearGuia: crearGuia };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GuiaParada = api;
    var arrancar = function () {
      var documento = global.document;
      var fuente = documento.getElementById("datos-ir-a");
      var T = global.TramoEntregas;
      if (!fuente || !T) return;
      var datos = JSON.parse(fuente.textContent);
      var mapas = (global.MapaEntregas && global.MapaEntregas.mapas) || {};
      var csrf = function () {
        var campo = documento.querySelector("[name=csrfmiddlewaretoken]");
        return campo ? campo.value : "";
      };
      var cliente = T.crearCliente({
        fetch: global.fetch.bind(global), AbortController: global.AbortController, urlTramo: datos.url_tramo,
        urlCercana: "", csrf: csrf, enLinea: function () { return global.navigator.onLine; },
      });
      crearGuia({
        destino: { intento: datos.intento, numero: datos.numero },
        ventana: global,
        documento: documento,
        mapa: mapas.ir_a || null,
        crearSeguimiento: function (op) {
          op.geo = global.navigator.geolocation;
          op.seguro = Boolean(global.isSecureContext);
          op.cliente = cliente;
          op.ahora = function () { return Date.now(); };
          return T.crearSeguimiento(op);
        },
        elementos: {
          estado: documento.getElementById("guia-estado"),
          anuncio: documento.getElementById("guia-anuncio"),
          iniciar: documento.getElementById("guia-iniciar"),
          leer: documento.getElementById("guia-leer"),
          detener: documento.getElementById("guia-detener"),
        },
      });
    };
    if (global.document.readyState === "loading") global.document.addEventListener("DOMContentLoaded", arrancar);
    else arrancar();
  }
})(typeof window !== "undefined" ? window : globalThis);
