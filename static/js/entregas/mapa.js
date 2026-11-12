/*
  Mapas del reparto (spec 09): la ruta del encargado y de «Rutas» (RF-09-08), el mapa pequeño del domicilio
  (RF-09-11) y el destino de «Ir a esta parada» (RF-09-09, que completa ir_a.js).

  - Leaflet se sirve desde static/vendor; las teselas las pide el navegador al proveedor configurado, con un
    referente reducido al origen del sitio («strict-origin»), sin la ruta de la página.
  - Los datos llegan en un json_script, sin RUT. Los textos del resumen se arman con textContent, nunca con HTML.
  - Número, estado y tipo se dicen con texto y forma; los marcadores se alcanzan con el teclado y tienen nombre.
  - Si el mapa base no carga, los marcadores y la línea siguen y un texto lo avisa; la lista es la alternativa.
  Este archivo no hace solicitudes propias: no usa fetch, XMLHttpRequest ni sendBeacon.
*/
(function (global) {
  "use strict";

  var AVISO_TESELAS = "No se pudo cargar el mapa base. Los puntos y la lista siguen disponibles.";
  var AVISO_SIN_LEAFLET = "No se pudo cargar el mapa. La lista tiene toda la información.";
  var POLITICA_REFERENTE = "strict-origin";

  function escapar(texto) {
    return String(texto == null ? "" : texto).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[c];
    });
  }

  // La atribución se configura como texto; con OpenStreetMap enlaza a su página de derechos de autor.
  function atribucion(teselas) {
    var texto = escapar(teselas.atribucion);
    if (/^https:\/\/([a-z0-9-]+\.)*openstreetmap\.org\//i.test(teselas.url)) {
      return "<a href=\"https://www.openstreetmap.org/copyright\" rel=\"noopener noreferrer\" target=\"_blank\">" + texto + "</a>";
    }
    return texto;
  }

  function opcionesTeselas(teselas) {
    return { maxZoom: teselas.zoom_maximo, attribution: atribucion(teselas), referrerPolicy: POLITICA_REFERENTE };
  }

  function mostrarAviso(aviso, texto) {
    if (!aviso) return;
    aviso.textContent = texto || "";
    aviso.hidden = !texto;
  }

  // Capa base con aviso: cuenta las teselas fallidas de cada carga y avisa al terminar o al primer error.
  function capaBase(L, mapa, teselas, aviso) {
    var capa = L.tileLayer(teselas.url, opcionesTeselas(teselas));
    var errores = 0;
    capa.on("loading", function () { errores = 0; });
    capa.on("tileerror", function () {
      errores += 1;
      mostrarAviso(aviso, AVISO_TESELAS);
    });
    capa.on("load", function () { mostrarAviso(aviso, errores > 0 ? AVISO_TESELAS : ""); });
    capa.addTo(mapa);
    return capa;
  }

  function crearMapa(L, contenedor, teselas, aviso) {
    var mapa = L.map(contenedor, { keyboard: true, scrollWheelZoom: false, zoomControl: true });
    if (mapa.attributionControl && mapa.attributionControl.setPrefix) {
      mapa.attributionControl.setPrefix("<a href=\"https://leafletjs.com\" rel=\"noopener noreferrer\" target=\"_blank\">Leaflet</a>");
    }
    capaBase(L, mapa, teselas, aviso);
    return mapa;
  }

  // Nombre accesible del marcador: lo lee el lector de pantalla al llegar con el teclado.
  function nombreParada(parada) {
    var estado = parada.estado === "Pendiente" ? "pendiente" : String(parada.estado).toLowerCase();
    return "Parada " + parada.numero + ", " + estado + (parada.nueva ? ", nueva" : "");
  }

  function nombreRegistrada(registrada) {
    var texto = registrada.entregada ? "Entregada" : "No entregada" + (registrada.motivo ? ": " + registrada.motivo : "");
    return texto + ", a las " + registrada.hora + ". " + registrada.titulo;
  }

  function iconoParada(L, parada) {
    var clases = "marcador marcador-parada" + (parada.estado !== "Pendiente" ? " marcador-atrasada" : "") + (parada.nueva ? " marcador-nueva" : "");
    return L.divIcon({ className: clases, html: "<span>" + Number(parada.numero) + "</span>", iconSize: [40, 40], iconAnchor: [20, 20], popupAnchor: [0, -20] });
  }

  function iconoRegistrada(L, registrada) {
    var clase = registrada.entregada ? "marcador-entregada" : "marcador-no-entregada";
    return L.divIcon({ className: "marcador marcador-registrada " + clase, html: "<span>" + (registrada.entregada ? "✓" : "✗") + "</span>", iconSize: [32, 32], iconAnchor: [16, 16], popupAnchor: [0, -16] });
  }

  function iconoCesfam(L) {
    return L.divIcon({ className: "marcador marcador-cesfam", html: "<span>C</span>", iconSize: [36, 36], iconAnchor: [18, 18], popupAnchor: [0, -18] });
  }

  function iconoDestino(L, numero) {
    return L.divIcon({ className: "marcador marcador-parada marcador-destino", html: "<span>" + Number(numero) + "</span>", iconSize: [44, 44], iconAnchor: [22, 22] });
  }

  function iconoPunto(L) {
    return L.divIcon({ className: "marcador marcador-domicilio", html: "<span></span>", iconSize: [28, 28], iconAnchor: [14, 14] });
  }

  // El elemento del marcador recibe su nombre accesible apenas existe en la página.
  function nombrar(marcador, nombre) {
    marcador.on("add", function () {
      var elemento = marcador.getElement && marcador.getElement();
      if (elemento) {
        elemento.setAttribute("aria-label", nombre);
        elemento.setAttribute("title", nombre);
      }
    });
    return marcador;
  }

  function linea(documento, padre, texto, clase) {
    if (!texto) return null;
    var p = documento.createElement("p");
    if (clase) p.className = clase;
    p.textContent = texto;
    padre.appendChild(p);
    return p;
  }

  function enlace(documento, padre, url, texto) {
    if (!url) return;
    var a = documento.createElement("a");
    a.href = url;
    a.textContent = texto;
    padre.appendChild(a);
  }

  // Resumen del marcador: número, estado, sector, localidad, dirección y referencias, y sus enlaces.
  function resumenParada(documento, parada) {
    var caja = documento.createElement("div");
    caja.className = "mapa-resumen";
    linea(documento, caja, "Parada " + parada.numero + " · " + parada.estado + (parada.nueva ? " · Nueva" : ""), "mapa-resumen-titulo");
    linea(documento, caja, parada.titulo);
    linea(documento, caja, [parada.sector ? "Sector " + parada.sector : "", parada.localidad].filter(Boolean).join(" · "));
    linea(documento, caja, parada.direccion);
    linea(documento, caja, parada.referencias);
    var enlaces = documento.createElement("p");
    enlaces.className = "mapa-resumen-enlaces";
    enlace(documento, enlaces, parada.url_registrar, "Registrar");
    enlace(documento, enlaces, parada.url_ir, "Ir a esta parada");
    enlace(documento, enlaces, parada.url_domicilio, "Ver domicilio");
    caja.appendChild(enlaces);
    return caja;
  }

  function resumenRegistrada(documento, registrada) {
    var caja = documento.createElement("div");
    caja.className = "mapa-resumen";
    linea(documento, caja, (registrada.entregada ? "Entregada" : "No entregada") + " · " + registrada.hora, "mapa-resumen-titulo");
    linea(documento, caja, registrada.motivo ? "Motivo: " + registrada.motivo : "");
    linea(documento, caja, registrada.titulo);
    linea(documento, caja, [registrada.sector ? "Sector " + registrada.sector : "", registrada.localidad].filter(Boolean).join(" · "));
    linea(documento, caja, registrada.direccion);
    var enlaces = documento.createElement("p");
    enlaces.className = "mapa-resumen-enlaces";
    enlace(documento, enlaces, registrada.url_domicilio, "Ver domicilio");
    caja.appendChild(enlaces);
    return caja;
  }

  function encuadrar(mapa, puntos) {
    if (puntos.length === 1) {
      mapa.setView(puntos[0], 15);
    } else if (puntos.length > 1) {
      mapa.fitBounds(puntos, { padding: [32, 32], maxZoom: 16 });
    }
  }

  // Mapa de una ruta: CESFAM, paradas numeradas, registradas de hoy y la línea punteada del recorrido.
  function dibujarRuta(L, documento, contenedor, datos, aviso) {
    var mapa = crearMapa(L, contenedor, datos.teselas, aviso);
    var puntos = [[datos.origen.lat, datos.origen.lon]];
    var marcadores = { paradas: [], registradas: [] };
    L.polyline(datos.linea, { className: "linea-recorrido", dashArray: "8 10", weight: 4, interactive: false }).addTo(mapa);
    nombrar(L.marker([datos.origen.lat, datos.origen.lon], { icon: iconoCesfam(L), keyboard: true, zIndexOffset: -100 }),
      "CESFAM, inicio y fin del recorrido").bindPopup("CESFAM: inicio y fin del recorrido").addTo(mapa);
    datos.registradas.forEach(function (registrada) {
      var marcador = nombrar(L.marker([registrada.lat, registrada.lon], { icon: iconoRegistrada(L, registrada), keyboard: true }),
        nombreRegistrada(registrada));
      marcador.bindPopup(resumenRegistrada(documento, registrada)).addTo(mapa);
      marcadores.registradas.push(marcador);
      puntos.push([registrada.lat, registrada.lon]);
    });
    datos.paradas.forEach(function (parada) {
      var marcador = nombrar(L.marker([parada.lat, parada.lon], { icon: iconoParada(L, parada), keyboard: true, zIndexOffset: 100 }),
        nombreParada(parada));
      marcador.bindPopup(resumenParada(documento, parada)).addTo(mapa);
      marcadores.paradas.push(marcador);
      puntos.push([parada.lat, parada.lon]);
    });
    encuadrar(mapa, puntos);
    return { mapa: mapa, marcadores: marcadores };
  }

  // Mapa pequeño del domicilio: el punto y su círculo de precisión, sin interacción de edición.
  function dibujarPunto(L, documento, contenedor, datos, aviso) {
    var mapa = crearMapa(L, contenedor, datos.teselas, aviso);
    nombrar(L.marker([datos.lat, datos.lon], { icon: iconoPunto(L), keyboard: true }), "Ubicación del domicilio").addTo(mapa);
    if (datos.precision) {
      L.circle([datos.lat, datos.lon], { radius: datos.precision, className: "circulo-precision", interactive: false }).addTo(mapa);
    }
    mapa.setView([datos.lat, datos.lon], 16);
    return { mapa: mapa };
  }

  // Destino de «Ir a esta parada»; ir_a.js mueve después «mi posición», su precisión y la línea hasta la parada.
  function dibujarDestino(L, documento, contenedor, datos, aviso) {
    var mapa = crearMapa(L, contenedor, datos.teselas, aviso);
    var destino = [datos.lat, datos.lon];
    nombrar(L.marker(destino, { icon: iconoDestino(L, datos.numero), keyboard: true }), "Parada " + datos.numero + ", destino").addTo(mapa);
    mapa.setView(destino, 15);
    var yo = null;
    var precision = null;
    var tramo = null;
    return {
      mapa: mapa,
      actualizar: function (lat, lon, metros) {
        var aqui = [lat, lon];
        if (!yo) {
          precision = L.circle(aqui, { radius: metros || 0, className: "circulo-precision", interactive: false }).addTo(mapa);
          yo = nombrar(L.circleMarker(aqui, { radius: 9, className: "mi-posicion", interactive: false }), "Tu posición").addTo(mapa);
          tramo = L.polyline([aqui, destino], { className: "linea-recorrido", dashArray: "8 10", weight: 4, interactive: false }).addTo(mapa);
          mapa.fitBounds([aqui, destino], { padding: [32, 32], maxZoom: 17 });
        } else {
          yo.setLatLng(aqui);
          precision.setLatLng(aqui);
          precision.setRadius(metros || 0);
          tramo.setLatLngs([aqui, destino]);
        }
      },
    };
  }

  var DIBUJOS = { ruta: dibujarRuta, punto: dibujarPunto, ir_a: dibujarDestino };

  function iniciar(documento, L) {
    var resultado = {};
    var nodos = documento.querySelectorAll("[data-mapa]");
    Array.prototype.forEach.call(nodos, function (contenedor) {
      var tipo = contenedor.getAttribute("data-mapa");
      var aviso = documento.getElementById(contenedor.getAttribute("data-aviso"));
      var fuente = documento.getElementById(contenedor.getAttribute("data-datos"));
      if (!L || !DIBUJOS[tipo] || !fuente) {
        mostrarAviso(aviso, AVISO_SIN_LEAFLET);
        contenedor.hidden = true;
        return;
      }
      resultado[tipo] = DIBUJOS[tipo](L, documento, contenedor, JSON.parse(fuente.textContent), aviso);
    });
    return resultado;
  }

  var api = {
    AVISO_TESELAS: AVISO_TESELAS,
    POLITICA_REFERENTE: POLITICA_REFERENTE,
    atribucion: atribucion,
    opcionesTeselas: opcionesTeselas,
    nombreParada: nombreParada,
    nombreRegistrada: nombreRegistrada,
    resumenParada: resumenParada,
    dibujarRuta: dibujarRuta,
    dibujarPunto: dibujarPunto,
    dibujarDestino: dibujarDestino,
    iniciar: iniciar,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.MapaEntregas = api;
    var arrancar = function () { global.MapaEntregas.mapas = iniciar(global.document, global.L); };
    if (global.document.readyState === "loading") {
      global.document.addEventListener("DOMContentLoaded", arrancar);
    } else {
      arrancar();
    }
  }
})(typeof window !== "undefined" ? window : globalThis);
