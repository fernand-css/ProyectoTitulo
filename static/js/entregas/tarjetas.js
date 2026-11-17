/*
  Tarjetas compactas de «Mis entregas» y «Rutas» (spec 09, enmienda del 2026-11-15, RF-09-16 y RF-09-18).

  - Sin JavaScript, cada tarjeta muestra todo su detalle y no hay botón. Aquí se muestra «Expandir» y el detalle
    queda oculto; varias tarjetas se pueden abrir a la vez.
  - El botón tiene aria-expanded y aria-controls; al pulsarlo cambia a «Contraer» y el foco se queda en él.
  - El mapa pequeño del domicilio se carga recién la primera vez que se expande su tarjeta, sin capturar el
    desplazamiento de la página. Sus datos son solo latitud, longitud y precisión (nunca el RUT).
  - Recuerda en sessionStorage, dentro de try/catch, las tarjetas abiertas del día; si no hay almacenamiento,
    simplemente empiezan cerradas.
  Este archivo no hace solicitudes propias (las teselas las pide Leaflet al proveedor del mapa base).
*/
(function (global) {
  "use strict";

  var TEXTOS = {
    expandir: "Expandir",
    contraer: "Contraer",
    sinMapa: "No se pudo cargar el mapa. Las coordenadas están en el texto de la tarjeta.",
  };

  function clave(dia) { return "entregas-tarjetas-abiertas:" + dia; }

  function leerAbiertas(almacen, dia) {
    try {
      var valor = JSON.parse(almacen.getItem(clave(dia)) || "[]");
      return Array.isArray(valor) ? valor.map(String) : [];
    } catch (error) {
      return [];
    }
  }

  function guardarAbiertas(almacen, dia, ids) {
    try {
      almacen.setItem(clave(dia), JSON.stringify(ids));
    } catch (error) {
      // sin almacenamiento (modo privado o bloqueado): no se recuerda, y no pasa nada
    }
  }

  function mostrarAviso(aviso, texto) {
    if (!aviso) return;
    aviso.textContent = texto || "";
    aviso.hidden = !texto;
  }

  function cargarMapa(tarjeta, entorno) {
    var contenedor = tarjeta.querySelector("[data-mapa-tarjeta]");
    if (!contenedor || contenedor.getAttribute("data-cargado") === "si") return null;
    contenedor.setAttribute("data-cargado", "si");
    var aviso = entorno.documento.getElementById(contenedor.getAttribute("data-aviso"));
    var espera = contenedor.querySelector(".mapa-tarjeta-espera");
    if (espera) espera.parentNode.removeChild(espera);
    if (!entorno.L || !entorno.mapas || !entorno.teselas) {
      mostrarAviso(aviso, TEXTOS.sinMapa);
      contenedor.hidden = true;
      return null;
    }
    var precision = contenedor.getAttribute("data-precision");
    var datos = {
      lat: Number(contenedor.getAttribute("data-latitud")),
      lon: Number(contenedor.getAttribute("data-longitud")),
      precision: precision === null ? null : Number(precision),
      teselas: entorno.teselas,
    };
    try {
      return entorno.mapas.dibujarPunto(entorno.L, entorno.documento, contenedor, datos, aviso, true);
    } catch (error) {
      mostrarAviso(aviso, TEXTOS.sinMapa);
      return null;
    }
  }

  function fijar(tarjeta, abierta, entorno) {
    var boton = tarjeta.querySelector("[data-expandir]");
    var detalle = tarjeta.querySelector("[data-detalle]");
    if (!boton || !detalle) return;
    boton.setAttribute("aria-expanded", abierta ? "true" : "false");
    var texto = boton.querySelector("[data-expandir-texto]");
    if (texto) texto.textContent = abierta ? TEXTOS.contraer : TEXTOS.expandir;
    detalle.hidden = !abierta;
    tarjeta.classList.toggle("visita-abierta", abierta);
    if (abierta) {
      var dibujado = cargarMapa(tarjeta, entorno);
      if (!dibujado) {
        var existente = tarjeta.mapaTarjeta;
        if (existente && existente.mapa && existente.mapa.invalidateSize) existente.mapa.invalidateSize();
      } else {
        tarjeta.mapaTarjeta = dibujado;
      }
    }
  }

  function abiertas(documento) {
    return Array.prototype.filter.call(documento.querySelectorAll("[data-compacta]"), function (tarjeta) {
      var boton = tarjeta.querySelector("[data-expandir]");
      return boton && boton.getAttribute("aria-expanded") === "true";
    }).map(function (tarjeta) { return tarjeta.getAttribute("data-intento"); });
  }

  function preparar(documento, entorno) {
    entorno = entorno || {};
    entorno.documento = documento;
    var dia = entorno.dia || "";
    var almacen = entorno.almacen || null;
    var recordadas = almacen ? leerAbiertas(almacen, dia) : [];
    var tarjetas = documento.querySelectorAll("[data-compacta]");
    Array.prototype.forEach.call(tarjetas, function (tarjeta) {
      var boton = tarjeta.querySelector("[data-expandir]");
      if (!boton || !tarjeta.querySelector("[data-detalle]")) return;
      boton.hidden = false;
      fijar(tarjeta, recordadas.indexOf(tarjeta.getAttribute("data-intento")) !== -1, entorno);
      boton.addEventListener("click", function () {
        fijar(tarjeta, boton.getAttribute("aria-expanded") !== "true", entorno);
        if (almacen) guardarAbiertas(almacen, dia, abiertas(documento));
      });
    });
    return tarjetas.length;
  }

  var api = { TEXTOS: TEXTOS, leerAbiertas: leerAbiertas, guardarAbiertas: guardarAbiertas, fijar: fijar, preparar: preparar };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else if (global.document) {
    global.TarjetasEntregas = api;
    var iniciar = function () {
      var documento = global.document;
      var fuente = documento.getElementById("datos-teselas");
      var teselas = null;
      try { teselas = fuente ? JSON.parse(fuente.textContent) : null; } catch (error) { teselas = null; }
      var almacen = null;
      try { almacen = global.sessionStorage; } catch (error) { almacen = null; }
      var hoy = new Date();
      preparar(documento, {
        L: global.L, mapas: global.MapaEntregas, teselas: teselas, almacen: almacen,
        dia: hoy.getFullYear() + "-" + (hoy.getMonth() + 1) + "-" + hoy.getDate(),
      });
    };
    if (global.document.readyState === "loading") global.document.addEventListener("DOMContentLoaded", iniciar);
    else iniciar();
  }
})(typeof window !== "undefined" ? window : globalThis);
