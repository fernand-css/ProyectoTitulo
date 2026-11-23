/*
  Mapas del reparto (spec 09): la ruta del encargado y de «Rutas» (RF-09-08, RF-09-21 y RF-09-24), el mapa pequeño
  del domicilio y de la tarjeta (RF-09-11 y RF-09-18) y el destino de «Ir a esta parada» (RF-09-23, con ir_a.js).

  - Leaflet se sirve desde static/vendor; las teselas las pide el navegador al proveedor configurado, con un
    referente reducido al origen del sitio («strict-origin»), sin la ruta de la página.
  - Los datos llegan en un json_script, sin RUT. Los textos del resumen se arman con textContent, nunca con HTML.
  - Número, estado y tipo se dicen con texto y forma; los marcadores se alcanzan con el teclado y tienen nombre.
  - Desde la enmienda del 2026-11-15 no hay línea del recorrido completo. En «Mapa», el encargado puede mostrar su
    posición: se dibuja solo el tramo por camino hasta la próxima parada o la que elija, y «Sugerir parada más
    cercana» la destaca con forma y texto (tramo.js pide ambos a Django). En «Rutas» solo hay marcadores.
  - Si el mapa base no carga, los marcadores siguen y un texto lo avisa; la lista es la alternativa.
  Este archivo solo hace dos solicitudes, a Django: mover la parada sugerida al primer lugar y (con tramo.js) el
  tramo y la parada más cercana.
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

  /*
    Zoom con Ctrl + rueda (corrección del 2026-11-16): la rueda sola sigue desplazando la página, para no quedar
    atrapado en el mapa al bajar por la lista; con Ctrl (o el gesto de pellizcar del panel táctil, que el
    navegador envía como rueda con Ctrl) el giro llega al zoom de rueda de Leaflet, que evita el zoom de la
    página. Se filtra en la fase de captura del contenedor, antes que el manejador de Leaflet.
  */
  function soloConCtrl(evento) {
    if (!evento.ctrlKey) evento.stopImmediatePropagation();
  }

  function zoomConCtrl(contenedor) {
    if (contenedor && contenedor.addEventListener) contenedor.addEventListener("wheel", soloConCtrl, true);
  }

  // `extra` agrega opciones de Leaflet: el mapa pequeño de la tarjeta no se arrastra ni se acerca con los dedos,
  // para no capturar el desplazamiento de la página (RF-09-18); se acerca y se aleja con sus botones o con
  // Ctrl + rueda. `scrollWheelZoom: true` en `extra` deja la rueda sola acercar (el diálogo «Usar mapa»).
  function crearMapa(L, contenedor, teselas, aviso, extra) {
    var opciones = { keyboard: true, scrollWheelZoom: true, zoomControl: true };
    Object.keys(extra || {}).forEach(function (clave) { opciones[clave] = extra[clave]; });
    if (!extra || extra.scrollWheelZoom !== true) zoomConCtrl(contenedor);
    var mapa = L.map(contenedor, opciones);
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

  function iconoCercana(L, parada) {
    return L.divIcon({ className: "marcador marcador-parada marcador-cercana", html: "<span>" + Number(parada.numero) + "</span>", iconSize: [48, 48], iconAnchor: [24, 24], popupAnchor: [0, -24] });
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
  function resumenParada(documento, parada, conTramo) {
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
    enlace(documento, enlaces, parada.url_domicilio, "Detalles del domicilio");
    caja.appendChild(enlaces);
    if (conTramo) {
      var boton = documento.createElement("button");
      boton.type = "button";
      boton.className = "boton boton-secundario";
      boton.setAttribute("data-trazar", String(parada.intento));
      boton.textContent = "Trazar tramo hasta aquí";
      caja.appendChild(boton);
    }
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
    enlace(documento, enlaces, registrada.url_domicilio, "Detalles del domicilio");
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

  // Mapa de una ruta: CESFAM, paradas numeradas y registradas de hoy, sin línea del recorrido completo. Para el
  // encargado, devuelve además cómo dibujar su posición, el tramo por camino y la parada destacada.
  function dibujarRuta(L, documento, contenedor, datos, aviso) {
    var mapa = crearMapa(L, contenedor, datos.teselas, aviso);
    var puntos = [[datos.origen.lat, datos.origen.lon]];
    var marcadores = { paradas: [], registradas: [] };
    var porIntento = {};
    var conTramo = Boolean(datos.url_tramo);
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
      marcador.bindPopup(resumenParada(documento, parada, conTramo)).addTo(mapa);
      marcadores.paradas.push(marcador);
      porIntento[parada.intento] = { marcador: marcador, parada: parada };
      puntos.push([parada.lat, parada.lon]);
    });
    encuadrar(mapa, puntos);
    var yo = null;
    var precision = null;
    var tramo = null;
    var destacada = null;
    var encuadradoPara = null;
    return {
      mapa: mapa,
      marcadores: marcadores,
      mostrarPosicion: function (lat, lon, metros) {
        var aqui = [lat, lon];
        if (!yo) {
          precision = L.circle(aqui, { radius: metros || 0, className: "circulo-precision", interactive: false }).addTo(mapa);
          yo = nombrar(L.circleMarker(aqui, { radius: 9, className: "mi-posicion", interactive: false }), "Tu posición").addTo(mapa);
        } else {
          yo.setLatLng(aqui);
          precision.setLatLng(aqui);
          precision.setRadius(metros || 0);
        }
      },
      // Línea continua del tramo por camino (no punteada: no es línea recta). Al cambiar de destino encuadra la
      // posición, el tramo y la parada, para no perder el contexto; al recalcular el mismo destino no mueve la vista.
      dibujarTramo: function (geometria, intento) {
        if (tramo) tramo.setLatLngs(geometria);
        else tramo = L.polyline(geometria, { className: "linea-tramo", weight: 6, interactive: false }).addTo(mapa);
        if (mapa.fitBounds && intento !== encuadradoPara) {
          var puntos = geometria.slice();
          if (yo && yo.getLatLng) puntos.push(yo.getLatLng());
          if (porIntento[intento]) puntos.push([porIntento[intento].parada.lat, porIntento[intento].parada.lon]);
          if (puntos.length > 1) mapa.fitBounds(puntos, { padding: [48, 48], maxZoom: 16 });
          encuadradoPara = intento;
        }
      },
      limpiar: function () {
        encuadradoPara = null;
        if (tramo) { mapa.removeLayer(tramo); tramo = null; }
        if (yo) { mapa.removeLayer(yo); mapa.removeLayer(precision); yo = null; precision = null; }
        this.quitarDestacada();
      },
      limpiarTramo: function () {
        if (tramo) { mapa.removeLayer(tramo); tramo = null; }
      },
      destacar: function (intento) {
        this.quitarDestacada();
        var elegido = porIntento[intento];
        if (!elegido) return false;
        elegido.marcador.setIcon(iconoCercana(L, elegido.parada));
        var elemento = elegido.marcador.getElement && elegido.marcador.getElement();
        if (elemento) elemento.setAttribute("aria-label", nombreParada(elegido.parada) + ", la más cercana por camino");
        destacada = elegido;
        return true;
      },
      quitarDestacada: function () {
        if (!destacada) return;
        destacada.marcador.setIcon(iconoParada(L, destacada.parada));
        var elemento = destacada.marcador.getElement && destacada.marcador.getElement();
        if (elemento) elemento.setAttribute("aria-label", nombreParada(destacada.parada));
        destacada = null;
      },
    };
  }

  // Mapa pequeño del domicilio: el punto y su círculo de precisión, sin interacción de edición.
  var FIJO = { dragging: false, touchZoom: false, doubleClickZoom: false, boxZoom: false, tap: false };

  function dibujarPunto(L, documento, contenedor, datos, aviso, fijo) {
    var mapa = crearMapa(L, contenedor, datos.teselas, aviso, fijo ? FIJO : null);
    nombrar(L.marker([datos.lat, datos.lon], { icon: iconoPunto(L), keyboard: true }), "Ubicación del domicilio").addTo(mapa);
    if (datos.precision) {
      L.circle([datos.lat, datos.lon], { radius: datos.precision, className: "circulo-precision", interactive: false }).addTo(mapa);
    }
    mapa.setView([datos.lat, datos.lon], 16);
    return { mapa: mapa };
  }

  // Destino de «Ir a esta parada»; ir_a.js mueve después «mi posición», su precisión y el tramo por camino.
  function dibujarDestino(L, documento, contenedor, datos, aviso) {
    var mapa = crearMapa(L, contenedor, datos.teselas, aviso);
    var destino = [datos.lat, datos.lon];
    nombrar(L.marker(destino, { icon: iconoDestino(L, datos.numero), keyboard: true }), "Parada " + datos.numero + ", destino").addTo(mapa);
    mapa.setView(destino, 15);
    var yo = null;
    var precision = null;
    var tramo = null;
    var encuadrado = false;
    return {
      mapa: mapa,
      actualizar: function (lat, lon, metros) {
        var aqui = [lat, lon];
        if (!yo) {
          precision = L.circle(aqui, { radius: metros || 0, className: "circulo-precision", interactive: false }).addTo(mapa);
          yo = nombrar(L.circleMarker(aqui, { radius: 9, className: "mi-posicion", interactive: false }), "Tu posición").addTo(mapa);
        } else {
          yo.setLatLng(aqui);
          precision.setLatLng(aqui);
          precision.setRadius(metros || 0);
        }
      },
      dibujarTramo: function (geometria) {
        if (tramo) tramo.setLatLngs(geometria);
        else tramo = L.polyline(geometria, { className: "linea-tramo", weight: 6, interactive: false }).addTo(mapa);
        if (!encuadrado && geometria.length > 1) {
          var puntos = geometria.concat([destino]);
          if (yo && yo.getLatLng) puntos.push(yo.getLatLng());
          mapa.fitBounds(puntos, { padding: [40, 40], maxZoom: 16 });
          encuadrado = true;
        }
      },
      limpiar: function () {
        if (tramo) { mapa.removeLayer(tramo); tramo = null; }
        if (yo) { mapa.removeLayer(yo); mapa.removeLayer(precision); yo = null; precision = null; }
        encuadrado = false;
      },
      limpiarTramo: function () {
        if (tramo) { mapa.removeLayer(tramo); tramo = null; }
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

  var CLAVE_ANUNCIO = "entregas-anuncio-mapa";
  var TEXTOS_GUIA = {
    sinPosicionCercana: "Para sugerir la parada más cercana necesitas activar tu ubicación con «Mi posición».",
    yaPrimera: "Ya es tu próxima parada.",
    movida: "Parada movida al primer lugar. Tu orden de hoy quedó guardado.",
    sinParadas: "No hay paradas con coordenadas para trazar un tramo.",
  };

  function textoTramo(resultado) {
    return "Parada " + resultado.numero + ": " + resultado.distancia_texto + " por camino.";
  }

  function textoCercana(resultado) {
    return "La más cercana por camino es la parada " + resultado.numero + ", a " + resultado.distancia_texto + ".";
  }

  function leerAnuncio(almacen) {
    try {
      var texto = almacen.getItem(CLAVE_ANUNCIO);
      almacen.removeItem(CLAVE_ANUNCIO);
      return texto || "";
    } catch (error) {
      return "";
    }
  }

  /*
    Controles del «Mapa» del encargado (RF-09-21 y RF-09-22): «Mostrar mi posición», «Detener», «Sugerir parada
    más cercana», «Trazar tramo hasta aquí» y «Mover al siguiente lugar». `entorno`: dibujo (de dibujarRuta),
    datos, seguimiento (tramo.js), cliente, elementos {estado, anuncio, mostrar, detener, cercana, mover y, desde
    el 2026-11-22, caja y cerrar}, mover(intento, version) → Promise, almacen, recargar.
    La X (`cerrar`) oculta la caja del mensaje: las distancias que se actualizan solas siguen escribiéndose sin
    abrirla, y cualquier aviso nuevo (inicio, error, sugerencia, fin) la vuelve a mostrar.
  */
  function prepararGuia(documento, entorno) {
    var datos = entorno.datos;
    var el = entorno.elementos;
    var destino = datos.paradas.length ? datos.paradas[0].intento : null;
    var sugerida = null;
    var sugerencia = ""; // el texto de la parada sugerida se mantiene junto al del tramo hasta cambiar de destino
    var alternar = false;
    var cerrado = false;

    function mostrarCaja() { if (el.caja) el.caja.hidden = cerrado || !el.estado.textContent; }
    function mostrarTexto(texto) { el.estado.textContent = texto; mostrarCaja(); }
    function anunciar(texto) {
      alternar = !alternar;
      el.anuncio.textContent = texto + (alternar ? "" : " ");
      cerrado = false;
      mostrarCaja();
    }
    function botones(siguiendo) {
      el.mostrar.disabled = siguiendo;
      el.detener.disabled = !siguiendo;
    }
    function ocultarMover() { el.mover.hidden = true; sugerida = null; }

    var seguimiento = entorno.crearSeguimiento({
      destino: function () { return destino; },
      avisos: {
        inicio: function (texto) { botones(true); mostrarTexto(texto); anunciar(texto); },
        posicion: function (p) { entorno.dibujo.mostrarPosicion(p.lat, p.lon, p.precision); },
        tramo: function (resultado) {
          entorno.dibujo.dibujarTramo(resultado.geometria, resultado.intento);
          mostrarTexto((sugerencia ? sugerencia + " " : "") + textoTramo(resultado));
        },
        error: function (texto) {
          entorno.dibujo.limpiarTramo();
          mostrarTexto(texto);
          anunciar(texto);
          if (!seguimiento || !seguimiento.siguiendo()) botones(false);
        },
        espera: function (texto) { mostrarTexto(texto); },
        fin: function (texto) {
          sugerencia = "";
          entorno.dibujo.limpiar();
          ocultarMover();
          botones(false);
          if (texto) { mostrarTexto(texto); anunciar(texto); }
        },
      },
    });

    function trazarHasta(intento) {
      destino = intento;
      sugerencia = "";
      if (!seguimiento.siguiendo()) seguimiento.iniciar();
      else seguimiento.recalcular();
    }

    el.mostrar.addEventListener("click", function () {
      if (destino === null) { mostrarTexto(TEXTOS_GUIA.sinParadas); anunciar(TEXTOS_GUIA.sinParadas); }
      seguimiento.iniciar();
    });
    el.detener.addEventListener("click", function () { seguimiento.detener(); });
    el.cercana.addEventListener("click", function () {
      var posicion = seguimiento.posicion();
      if (!posicion) { mostrarTexto(TEXTOS_GUIA.sinPosicionCercana); anunciar(TEXTOS_GUIA.sinPosicionCercana); return; }
      entorno.cliente.pedirCercana(posicion).then(function (resultado) {
        if (resultado.descartada) return;
        if (!resultado.ok) {
          entorno.dibujo.quitarDestacada();
          ocultarMover();
          mostrarTexto(resultado.mensaje);
          anunciar(resultado.mensaje);
          return;
        }
        entorno.dibujo.destacar(resultado.intento);
        var texto = textoCercana(resultado);
        if (resultado.es_primera) {
          texto += " " + TEXTOS_GUIA.yaPrimera;
          ocultarMover();
        } else {
          sugerida = resultado;
          el.mover.hidden = false;
        }
        mostrarTexto(texto);
        anunciar(texto);
        sugerencia = texto;
        destino = resultado.intento;
        seguimiento.recalcular();
      });
    });
    el.mover.addEventListener("click", function () {
      if (!sugerida) return;
      var elegida = sugerida;
      el.mover.disabled = true;
      entorno.mover(elegida.intento, elegida.version).then(function (resultado) {
        el.mover.disabled = false;
        if (!resultado.ok) { mostrarTexto(resultado.mensaje); anunciar(resultado.mensaje); return; }
        try { entorno.almacen.setItem(CLAVE_ANUNCIO, TEXTOS_GUIA.movida); } catch (error) { /* sin almacenamiento */ }
        mostrarTexto(TEXTOS_GUIA.movida);
        anunciar(TEXTOS_GUIA.movida);
        entorno.recargar();
      });
    });
    documento.addEventListener("click", function (evento) {
      var boton = evento.target && evento.target.closest ? evento.target.closest("[data-trazar]") : null;
      if (!boton) return;
      // En el mapa a pantalla completa la lista vive en el panel «Paradas»: se cierra para ver el tramo.
      var panel = boton.closest("details");
      if (panel) panel.open = false;
      trazarHasta(Number(boton.getAttribute("data-trazar")));
    });
    if (entorno.ventana) entorno.ventana.addEventListener("pagehide", function () { seguimiento.detener(true); });
    // Oculta (otra pestaña o ventana minimizada): pausa sin borrar el tramo ni la posición; al volver, sigue sola.
    documento.addEventListener("visibilitychange", function () {
      if (documento.visibilityState === "hidden") seguimiento.pausar();
      else seguimiento.reanudar();
    });
    if (el.cerrar && el.caja) {
      el.cerrar.hidden = false;
      el.cerrar.addEventListener("click", function () {
        cerrado = true;
        mostrarCaja();
        var foco = el.mostrar.disabled ? el.detener : el.mostrar;
        if (foco && typeof foco.focus === "function") foco.focus();
      });
    }
    if (el.panel) el.panel.hidden = false; // sin JavaScript el panel y «Trazar tramo hasta aquí» no aparecen
    Array.prototype.forEach.call(documento.querySelectorAll("button[data-trazar]"), function (b) { b.hidden = false; });
    var pendiente = entorno.almacen ? leerAnuncio(entorno.almacen) : "";
    if (pendiente) { mostrarTexto(pendiente); anunciar(pendiente); }
    botones(false);
    return { seguimiento: seguimiento, trazarHasta: trazarHasta, destino: function () { return destino; } };
  }

  /*
    Menú de tres barras del «Mapa» (2026-11-22): el botón muestra u oculta las pestañas a su derecha. Se cierra
    con Escape (devuelve el foco al botón), al tocar fuera y al elegir una pestaña. Sin JavaScript el botón no
    aparece y las pestañas quedan a la vista.
  */
  function prepararMenu(documento) {
    var raiz = documento.querySelector("[data-mapa-menu]");
    if (!raiz) return null;
    var boton = raiz.querySelector("[data-mapa-menu-boton]");
    var lista = raiz.querySelector("[data-mapa-menu-lista]");
    if (!boton || !lista) return null;
    function abrir(abierto) {
      lista.hidden = !abierto;
      boton.setAttribute("aria-expanded", abierto ? "true" : "false");
    }
    boton.hidden = false;
    abrir(false);
    boton.addEventListener("click", function () { abrir(lista.hidden); });
    documento.addEventListener("keydown", function (evento) {
      if (evento.key === "Escape" && !lista.hidden) { abrir(false); boton.focus(); }
    });
    documento.addEventListener("click", function (evento) {
      if (!lista.hidden && evento.target && !raiz.contains(evento.target)) abrir(false);
    });
    return { abrir: abrir, boton: boton, lista: lista };
  }

  var api = {
    AVISO_TESELAS: AVISO_TESELAS,
    TEXTOS_GUIA: TEXTOS_GUIA,
    CLAVE_ANUNCIO: CLAVE_ANUNCIO,
    textoTramo: textoTramo,
    textoCercana: textoCercana,
    prepararGuia: prepararGuia,
    prepararMenu: prepararMenu,
    POLITICA_REFERENTE: POLITICA_REFERENTE,
    atribucion: atribucion,
    opcionesTeselas: opcionesTeselas,
    nombreParada: nombreParada,
    nombreRegistrada: nombreRegistrada,
    resumenParada: resumenParada,
    dibujarRuta: dibujarRuta,
    dibujarPunto: dibujarPunto,
    crearMapa: crearMapa,
    nombrar: nombrar,
    iconoPunto: iconoPunto,
    FIJO: FIJO,
    dibujarDestino: dibujarDestino,
    iniciar: iniciar,
  };

  function csrfDe(documento) {
    var campo = documento.querySelector("[name=csrfmiddlewaretoken]");
    return campo ? campo.value : "";
  }

  function nuevaOperacion() {
    if (global.crypto && typeof global.crypto.randomUUID === "function") return global.crypto.randomUUID();
    return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, function (c) {
      return (c ^ (global.crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16);
    });
  }

  // En la página, la guía del encargado necesita tramo.js; en «Rutas» (consulta) no hay controles.
  function arrancarGuia(documento, mapas) {
    var fuente = documento.getElementById("datos-mapa");
    var guia = documento.querySelector("[data-guia-mapa]");
    if (!fuente || !guia || !mapas.ruta || !global.TramoEntregas) return null;
    var datos = JSON.parse(fuente.textContent);
    if (!datos.url_tramo) return null;
    var T = global.TramoEntregas;
    var cliente = T.crearCliente({
      fetch: global.fetch.bind(global), AbortController: global.AbortController, urlTramo: datos.url_tramo,
      urlCercana: datos.url_cercana, csrf: function () { return csrfDe(documento); },
      enLinea: function () { return global.navigator.onLine; },
    });
    var almacen = null;
    try { almacen = global.sessionStorage; } catch (error) { almacen = null; }
    return prepararGuia(documento, {
      datos: datos, dibujo: mapas.ruta, cliente: cliente, ventana: global, almacen: almacen,
      crearSeguimiento: function (op) {
        op.geo = global.navigator.geolocation;
        op.seguro = Boolean(global.isSecureContext);
        op.cliente = cliente;
        op.ahora = function () { return Date.now(); };
        return T.crearSeguimiento(op);
      },
      recargar: function () { global.location.reload(); },
      mover: function (intento, version) {
        var cuerpo = new global.FormData();
        cuerpo.set("intento", String(intento));
        cuerpo.set("destino", "1");
        cuerpo.set("version", String(version));
        cuerpo.set("operacion_id", nuevaOperacion());
        if (global.navigator.onLine === false) return Promise.resolve({ ok: false, mensaje: "Sin conexión: no se guardó el cambio de orden." });
        return global.fetch(datos.url_mover, {
          method: "POST", body: cuerpo, credentials: "same-origin",
          headers: { Accept: "application/json", "X-CSRFToken": csrfDe(documento) },
        }).then(function (respuesta) {
          return respuesta.json().then(function (r) { return r.ok ? r : { ok: false, mensaje: r.error || "No pudimos guardar el orden." }; });
        }, function () { return { ok: false, mensaje: "Sin conexión: no se guardó el cambio de orden." }; });
      },
      elementos: {
        estado: documento.getElementById("mapa-guia-estado"),
        anuncio: documento.getElementById("mapa-guia-anuncio"),
        mostrar: documento.getElementById("mapa-mostrar"),
        detener: documento.getElementById("mapa-detener"),
        cercana: documento.getElementById("mapa-cercana"),
        mover: documento.getElementById("mapa-mover"),
        caja: documento.getElementById("mapa-guia-caja"),
        cerrar: documento.getElementById("mapa-guia-cerrar"),
        panel: guia,
      },
    });
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.MapaEntregas = api;
    var arrancar = function () {
      global.MapaEntregas.mapas = iniciar(global.document, global.L);
      global.MapaEntregas.guia = arrancarGuia(global.document, global.MapaEntregas.mapas);
      global.MapaEntregas.menu = prepararMenu(global.document);
    };
    if (global.document.readyState === "loading") {
      global.document.addEventListener("DOMContentLoaded", arrancar);
    } else {
      arrancar();
    }
  }
})(typeof window !== "undefined" ? window : globalThis);
