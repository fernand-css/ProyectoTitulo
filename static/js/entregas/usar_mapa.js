/*
  «Usar mapa» del formulario del domicilio (spec 09, enmienda del 2026-11-15, RF-09-25).

  - Abre un diálogo modal (<dialog> con showModal) con un mapa que se mueve y se acerca libremente.
  - Se centra en las coordenadas del formulario, marcadas, si son válidas; si no, en el CESFAM.
  - Tocar o hacer clic marca un punto (otro toque lo reemplaza). Con teclado, el mapa se mueve con las flechas y
    «Marcar el centro del mapa» marca el punto bajo la mira central.
  - «Usar este punto» copia la latitud y la longitud con 6 decimales a sus campos, vacía «Precisión (metros)» y
    cierra. «Cancelar», Esc o la X cierran sin cambios. El foco vuelve al botón que lo abrió.
  - Nada se guarda aquí: el domicilio se guarda con «Guardar domicilio» y, como todo cambio de coordenadas, queda
    pendiente de verificar. Sin JavaScript (o sin <dialog> o Leaflet), el botón no aparece.
  Este archivo no hace solicitudes propias (las teselas las pide Leaflet al proveedor del mapa base).
*/
(function (global) {
  "use strict";

  var TEXTOS = {
    sinPunto: "Aún no marcas un punto.",
    marcado: function (lat, lon) { return "Punto marcado: " + lat + ", " + lon + ". Pulsa «Usar este punto» para copiarlo."; },
    copiado: function (lat, lon) {
      return "Coordenadas copiadas del mapa: " + lat + ", " + lon + ". Escribe la precisión si la conoces y guarda el domicilio.";
    },
  };

  function numero(texto) {
    if (texto == null) return NaN;
    var limpio = String(texto).trim().replace(",", ".");
    if (!limpio || !/^-?\d+(\.\d+)?$/.test(limpio)) return NaN;
    return Number(limpio);
  }

  // Centro del mapa al abrir: el punto del formulario si es válido (y entonces va marcado); si no, el CESFAM.
  function centroInicial(latitudTexto, longitudTexto, origen) {
    var lat = numero(latitudTexto);
    var lon = numero(longitudTexto);
    if (isFinite(lat) && isFinite(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
      return { lat: lat, lon: lon, marcado: true };
    }
    return { lat: origen.lat, lon: origen.lon, marcado: false };
  }

  function seis(valor) { return Number(valor).toFixed(6); }

  function avisarCambio(campo, Evento) {
    ["input", "change"].forEach(function (tipo) {
      try { campo.dispatchEvent(new Evento(tipo, { bubbles: true })); } catch (error) { /* navegador antiguo */ }
    });
  }

  /*
    `entorno`: L (Leaflet), mapas (MapaEntregas: crearMapa, nombrar, iconoPunto), datos {origen, teselas} y
    Evento (constructor de eventos). Devuelve el control del diálogo o null si falta algo (el botón sigue oculto).
  */
  function preparar(documento, entorno) {
    var dialogo = documento.querySelector("[data-usar-mapa]");
    var abrirBoton = documento.querySelector("[data-usar-mapa-abrir]");
    var formulario = documento.querySelector("[data-domicilio-form]");
    if (!dialogo || !abrirBoton || !formulario || typeof dialogo.showModal !== "function" || !entorno.L || !entorno.mapas) {
      return null;
    }
    var L = entorno.L;
    var contenedor = dialogo.querySelector("[data-usar-mapa-mapa]");
    var estado = dialogo.querySelector("[data-usar-mapa-estado]");
    var usarBoton = dialogo.querySelector("[data-usar-mapa-usar]");
    var resultado = documento.querySelector("[data-usar-mapa-resultado]");
    var aviso = documento.getElementById("aviso-usar-mapa");
    var mapa = null;
    var marcador = null;
    var elegido = null;

    function campo(nombre) { return formulario.querySelector("[name=" + nombre + "]"); }

    function marcar(lat, lon) {
      elegido = { lat: seis(lat), lon: seis(lon) };
      if (marcador) marcador.setLatLng([lat, lon]);
      else marcador = entorno.mapas.nombrar(L.marker([lat, lon], { icon: entorno.mapas.iconoPunto(L), keyboard: false }), "Punto marcado").addTo(mapa);
      usarBoton.disabled = false;
      estado.textContent = TEXTOS.marcado(elegido.lat, elegido.lon);
    }

    function limpiarMarca() {
      if (marcador && mapa) mapa.removeLayer(marcador);
      marcador = null;
      elegido = null;
      usarBoton.disabled = true;
      estado.textContent = TEXTOS.sinPunto;
    }

    // El foco vuelve al botón al cerrar, sin esperar el evento `close` (llega después, o no llega en una pestaña
    // en segundo plano, y el foco quedaba en el mapa del diálogo cerrado).
    function cerrar() {
      if (dialogo.open) dialogo.close();
      abrirBoton.focus();
    }

    function abrir() {
      dialogo.showModal();
      var centro = centroInicial(campo("latitud").value, campo("longitud").value, entorno.datos.origen);
      if (!mapa) {
        mapa = entorno.mapas.crearMapa(L, contenedor, entorno.datos.teselas, aviso, { scrollWheelZoom: true });
        mapa.on("click", function (evento) { marcar(evento.latlng.lat, evento.latlng.lng); });
      } else if (mapa.invalidateSize) {
        mapa.invalidateSize();
      }
      limpiarMarca();
      mapa.setView([centro.lat, centro.lon], centro.marcado ? 17 : 14);
      if (centro.marcado) marcar(centro.lat, centro.lon);
      contenedor.focus();
    }

    abrirBoton.hidden = false;
    abrirBoton.addEventListener("click", abrir);
    dialogo.addEventListener("close", function () { abrirBoton.focus(); });
    dialogo.addEventListener("cancel", function (evento) { evento.preventDefault(); cerrar(); }); // Esc
    dialogo.querySelector("[data-usar-mapa-cerrar]").addEventListener("click", cerrar);
    dialogo.querySelector("[data-usar-mapa-cancelar]").addEventListener("click", cerrar);
    dialogo.querySelector("[data-usar-mapa-centro]").addEventListener("click", function () {
      var centro = mapa.getCenter();
      marcar(centro.lat, centro.lng);
    });
    usarBoton.addEventListener("click", function () {
      if (!elegido) return;
      var latitud = campo("latitud");
      var longitud = campo("longitud");
      var precision = campo("precision_metros");
      latitud.value = elegido.lat;
      longitud.value = elegido.lon;
      if (precision) precision.value = "";
      [latitud, longitud, precision].forEach(function (c) { if (c) avisarCambio(c, entorno.Evento); });
      if (resultado) resultado.textContent = TEXTOS.copiado(elegido.lat, elegido.lon);
      cerrar();
    });

    return { abrir: abrir, cerrar: cerrar, marcar: marcar, elegido: function () { return elegido; } };
  }

  var api = { TEXTOS: TEXTOS, centroInicial: centroInicial, seis: seis, preparar: preparar };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else if (global.document) {
    var iniciar = function () {
      var fuente = global.document.getElementById("datos-usar-mapa");
      if (!fuente) return;
      preparar(global.document, {
        L: global.L, mapas: global.MapaEntregas, datos: JSON.parse(fuente.textContent), Evento: global.Event,
      });
    };
    if (global.document.readyState === "loading") global.document.addEventListener("DOMContentLoaded", iniciar);
    else iniciar();
  }
})(typeof window !== "undefined" ? window : globalThis);
