/*
  Reordenar la ruta de hoy del encargado (spec 09, enmienda del 2026-11-15, RF-09-17), con código propio.

  - Flechas «Subir» y «Bajar»: sin JavaScript son un POST con recarga. Aquí se envían con fetch (Accept JSON) y la
    lista se reordena sin recargar, conservando las tarjetas abiertas (los nodos se mueven, no se reemplazan).
  - Franja de arrastre (borde derecho de cada tarjeta, oculta a los lectores de pantalla y sin foco): con mouse
    empieza al presionar; en pantallas táctiles, tras mantenerla presionada unos 300 ms (si el dedo se mueve
    antes, es desplazamiento de la página). La tarjeta sigue al puntero, un hueco muestra dónde caerá y la
    página se desplaza sola cerca de los bordes. Esc, la cancelación del puntero o soltar fuera de la lista
    cancelan sin cambios.
  - Cada guardado usa el servicio `mover_parada` (versión y operación nueva por envío). Si falla, la lista vuelve
    a como estaba y se muestra el motivo; si resulta, manda el orden que responde el servidor.
  - El resultado se anuncia en la región aria-live («Parada movida a la posición 2»).
  Las únicas solicitudes de red van a la ruta de Django que guarda el orden.
*/
(function (global) {
  "use strict";

  var TEXTOS = {
    movida: function (numero) { return "Parada movida a la posición " + numero + "."; },
    cancelado: "Movimiento cancelado; el orden no cambió.",
    sinCambios: "La parada quedó en el mismo lugar.",
    sinRed: "Sin conexión: no se guardó el cambio de orden.",
    fallo: "No pudimos guardar el orden. La lista volvió a como estaba; inténtalo nuevamente.",
    ocupado: "Espera a que termine de guardarse el cambio anterior.",
    cambioLista: "Tu lista cambió en otro dispositivo; se volverá a cargar.",
  };

  var ESPERA_TOQUE_MS = 300;
  var UMBRAL_MOVIMIENTO_PX = 10;
  var MARGEN_BORDE_PX = 72;
  var VELOCIDAD_PX = 14;

  // Máquina del arrastre, sin DOM: el adaptador mide, coloca el hueco, desplaza y devuelve. Se prueba en Node.
  function crearArrastre(adaptador, reloj, opciones) {
    opciones = opciones || {};
    var espera = opciones.esperaToque || ESPERA_TOQUE_MS;
    var umbral = opciones.umbral || UMBRAL_MOVIMIENTO_PX;
    var margen = opciones.margen || MARGEN_BORDE_PX;
    var velocidad = opciones.velocidad || VELOCIDAD_PX;
    var estado = "libre";
    var inicio = null;
    var ultimo = null;
    var temporizador = null;
    var cuadro = null;
    var indiceOriginal = -1;
    var indiceHueco = -1;

    function recolocar() {
      var y = ultimo.y;
      var indice = adaptador.centros().filter(function (centro) { return centro < y; }).length;
      if (indice !== indiceHueco) {
        indiceHueco = indice;
        adaptador.colocarHueco(indice);
      }
    }

    function bucle() {
      cuadro = null;
      if (estado !== "arrastrando") return;
      var dy = 0;
      if (ultimo.y < margen) dy = -velocidad;
      else if (ultimo.y > adaptador.alto() - margen) dy = velocidad;
      if (dy) {
        adaptador.desplazar(dy);
        recolocar();
      }
      cuadro = reloj.cuadro(bucle);
    }

    function empezar() {
      temporizador = null;
      estado = "arrastrando";
      indiceOriginal = adaptador.iniciar();
      indiceHueco = indiceOriginal;
      adaptador.seguir(ultimo.y);
      recolocar();
      cuadro = reloj.cuadro(bucle);
    }

    function terminar() {
      if (temporizador !== null) reloj.cancelar(temporizador);
      if (cuadro !== null) reloj.cancelarCuadro(cuadro);
      temporizador = null;
      cuadro = null;
      estado = "libre";
    }

    return {
      estado: function () { return estado; },
      presionar: function (punto) {
        if (estado !== "libre") return false;
        inicio = { x: punto.x, y: punto.y };
        ultimo = inicio;
        if (punto.tipo === "touch") {
          estado = "esperando";
          temporizador = reloj.programar(empezar, espera);
        } else {
          empezar();
        }
        return true;
      },
      mover: function (punto) {
        if (estado === "esperando") {
          if (Math.abs(punto.x - inicio.x) > umbral || Math.abs(punto.y - inicio.y) > umbral) terminar();
          return false; // es desplazamiento de la página
        }
        if (estado !== "arrastrando") return false;
        ultimo = { x: punto.x, y: punto.y };
        adaptador.seguir(ultimo.y);
        recolocar();
        return true;
      },
      soltar: function (punto) {
        if (estado === "esperando") { terminar(); return null; }
        if (estado !== "arrastrando") return null;
        terminar();
        if (!adaptador.dentro(punto.x, punto.y)) {
          adaptador.devolver();
          adaptador.anunciar(TEXTOS.cancelado);
          return null;
        }
        if (indiceHueco === indiceOriginal) {
          adaptador.devolver();
          adaptador.anunciar(TEXTOS.sinCambios);
          return null;
        }
        adaptador.soltarEn(indiceHueco);
        return indiceHueco;
      },
      cancelar: function () {
        if (estado === "esperando") { terminar(); return; }
        if (estado !== "arrastrando") return;
        terminar();
        adaptador.devolver();
        adaptador.anunciar(TEXTOS.cancelado);
      },
    };
  }

  function nuevaOperacion(cripto) {
    if (cripto && typeof cripto.randomUUID === "function") return cripto.randomUUID();
    var bytes = new Uint8Array(16);
    if (cripto && typeof cripto.getRandomValues === "function") cripto.getRandomValues(bytes);
    else for (var i = 0; i < 16; i += 1) bytes[i] = Math.floor(Math.random() * 256);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    var hex = Array.prototype.map.call(bytes, function (b) { return (b < 16 ? "0" : "") + b.toString(16); }).join("");
    return hex.slice(0, 8) + "-" + hex.slice(8, 12) + "-" + hex.slice(12, 16) + "-" + hex.slice(16, 20) + "-" + hex.slice(20);
  }

  function interpretar(status, cuerpo) {
    if (cuerpo && cuerpo.ok === true && Array.isArray(cuerpo.orden)) return cuerpo;
    var mensaje = cuerpo && typeof cuerpo.error === "string" && cuerpo.error ? cuerpo.error : TEXTOS.fallo;
    return { ok: false, mensaje: mensaje, conflicto: status === 409 };
  }

  // Un solo POST con Accept JSON y CSRF; sin conexión no envía nada.
  function guardar(entorno) {
    if (entorno.enLinea === false) return Promise.resolve({ ok: false, mensaje: TEXTOS.sinRed });
    var cabeceras = { Accept: "application/json" };
    if (entorno.csrf) cabeceras["X-CSRFToken"] = entorno.csrf;
    return Promise.resolve()
      .then(function () {
        return entorno.fetch(entorno.url, { method: "POST", body: entorno.cuerpo, headers: cabeceras, credentials: "same-origin" });
      })
      .then(function (respuesta) {
        return respuesta.json().then(
          function (cuerpo) { return interpretar(respuesta.status, cuerpo); },
          function () { return interpretar(respuesta.status, null); });
      }, function () { return { ok: false, mensaje: TEXTOS.sinRed }; });
  }

  // DOM ------------------------------------------------------------------------------------------------------

  function tarjetasDe(documento) {
    return Array.prototype.slice.call(documento.querySelectorAll("[data-arrastrable]"));
  }

  function contenedores(documento) {
    return Array.prototype.filter.call(
      documento.querySelectorAll("[data-ruta-paradas], [data-ruta-sin-lista]"), Boolean);
  }

  // Fotografía del orden de los nodos de cada contenedor, para volver exactamente a como estaba.
  function fotografiar(documento) {
    return contenedores(documento).map(function (padre) {
      return { padre: padre, hijos: Array.prototype.slice.call(padre.childNodes) };
    });
  }

  function restaurar(foto) {
    foto.forEach(function (parte) {
      parte.hijos.forEach(function (hijo) { parte.padre.appendChild(hijo); });
    });
  }

  function nombreDe(tarjeta) {
    var titulo = tarjeta.querySelector("h3");
    return titulo ? titulo.textContent.trim() : "";
  }

  // Rehace los rótulos de sector y localidad de la sección «Sin coordenadas» según el orden actual de sus tarjetas.
  function reagrupar(documento, sinLista) {
    Array.prototype.slice.call(sinLista.querySelectorAll("[data-grupo-sector]")).forEach(function (rotulo) {
      rotulo.parentNode.removeChild(rotulo);
    });
    var anterior = null;
    Array.prototype.slice.call(sinLista.querySelectorAll("[data-arrastrable]")).forEach(function (tarjeta) {
      var grupo = tarjeta.getAttribute("data-grupo") || "";
      if (grupo === anterior) return;
      anterior = grupo;
      var rotulo = documento.createElement("p");
      rotulo.className = "grupo-sector";
      rotulo.setAttribute("data-grupo-sector", "");
      rotulo.textContent = grupo;
      sinLista.insertBefore(rotulo, tarjeta);
    });
  }

  // Aplica el orden que manda el servidor: mueve los nodos, numera, ajusta flechas, versión, rótulo y total.
  // Las numeradas van a «Por visitar en orden»; las sin coordenadas que quedan al final, a su propia sección.
  function aplicarOrden(documento, respuesta) {
    var lista = documento.querySelector("[data-ruta-paradas]");
    var sinLista = documento.querySelector("[data-ruta-sin-lista]");
    var presentes = tarjetasDe(documento).map(function (t) { return t.getAttribute("data-intento"); }).sort();
    var enviados = respuesta.orden.map(function (p) { return String(p.intento); }).sort();
    if (!lista || presentes.join(",") !== enviados.join(",")) return false;
    var total = respuesta.orden.length;
    respuesta.orden.forEach(function (parada) {
      var tarjeta = documento.getElementById("parada-" + parada.intento);
      (parada.numerada === false && sinLista ? sinLista : lista).appendChild(tarjeta);
      var rotulos = tarjeta.querySelector("[data-rotulos]");
      var numero = tarjeta.querySelector("[data-numero]");
      if (parada.numerada !== false) {
        if (!numero && rotulos) {
          numero = documento.createElement("span");
          numero.className = "parada-numero";
          numero.setAttribute("data-numero", "");
          rotulos.insertBefore(numero, rotulos.firstChild);
        }
        if (numero) numero.textContent = "Parada " + parada.numero;
      } else if (numero) {
        numero.parentNode.removeChild(numero);
      }
      if (respuesta.manual) {
        var nueva = tarjeta.querySelector("[data-nueva]");
        if (nueva) nueva.parentNode.removeChild(nueva);
        tarjeta.classList.remove("visita-nueva");
      }
      var nombre = nombreDe(tarjeta);
      var quien = (parada.numerada !== false ? "parada " + parada.numero : "visita sin coordenadas") + ": " + nombre;
      ["subir", "bajar"].forEach(function (sentido) {
        var flecha = tarjeta.querySelector('[data-flecha="' + sentido + '"]');
        if (!flecha) return;
        flecha.hidden = sentido === "subir" ? parada.numero <= 1 : parada.numero >= total;
        var texto = flecha.querySelector("[data-flecha-nombre]");
        if (texto) texto.textContent = (sentido === "subir" ? "Subir " : "Bajar ") + quien;
      });
    });
    var vacia = lista.querySelector("[data-ruta-vacia]");
    if (vacia && lista.querySelector("[data-arrastrable]")) vacia.parentNode.removeChild(vacia);
    var seccion = documento.querySelector("[data-ruta-sin-coordenadas]");
    if (seccion) {
      var sinCoordenadas = respuesta.orden.filter(function (p) { return p.numerada === false; }).length;
      seccion.hidden = !seccion.querySelector("[data-arrastrable]");
      var sinCantidad = seccion.querySelector("[data-ruta-sin-cantidad]");
      if (sinCantidad) sinCantidad.textContent = String(sinCoordenadas);
    }
    if (sinLista) reagrupar(documento, sinLista);
    var cantidad = documento.querySelector("[data-ruta-cantidad]");
    if (cantidad) cantidad.textContent = String(respuesta.orden.filter(function (p) { return p.numerada !== false; }).length);
    Array.prototype.forEach.call(documento.querySelectorAll("[data-version], [data-restablecer] [name=version]"), function (campo) {
      campo.value = String(respuesta.version);
    });
    var restablecer = documento.querySelector("[data-restablecer]");
    if (restablecer && respuesta.manual) restablecer.hidden = false;
    reemplazar(documento, "[data-ruta-rotulo]", respuesta.rotulo);
    reemplazar(documento, "[data-ruta-resumen]", respuesta.resumen);
    return true;
  }

  // El rótulo y el total vienen dibujados por Django desde sus parciales (con su escape de HTML).
  function reemplazar(documento, selector, html) {
    var actual = documento.querySelector(selector);
    if (!actual || typeof html !== "string" || !html) return;
    var molde = documento.createElement("template");
    molde.innerHTML = html.trim();
    var nuevo = molde.content ? molde.content.firstElementChild : null;
    if (nuevo) actual.parentNode.replaceChild(nuevo, actual);
  }

  function preparar(documento, entorno) {
    var region = documento.querySelector("[data-orden-estado]");
    var ocupado = false;

    function anunciar(texto) {
      if (!region) return;
      region.textContent = "";
      region.textContent = texto;
    }

    function enviar(form, destino, foto, intento) {
      if (ocupado) { anunciar(TEXTOS.ocupado); if (foto) restaurar(foto); return Promise.resolve(null); }
      ocupado = true;
      form.querySelector("[name=operacion_id]").value = nuevaOperacion(entorno.cripto);
      var cuerpo = new entorno.FormData(form);
      cuerpo.set("destino", String(destino));
      var csrf = form.querySelector("[name=csrfmiddlewaretoken]");
      return guardar({
        fetch: entorno.fetch, url: form.getAttribute("action"), cuerpo: cuerpo,
        csrf: csrf ? csrf.value : "", enLinea: entorno.navigator ? entorno.navigator.onLine !== false : true,
      }).then(function (resultado) {
        ocupado = false;
        if (!resultado.ok) {
          if (foto) restaurar(foto);
          anunciar(resultado.mensaje);
          return resultado;
        }
        if (!aplicarOrden(documento, resultado)) {
          anunciar(TEXTOS.cambioLista);
          if (entorno.recargar) entorno.recargar();
          return resultado;
        }
        var movida = resultado.orden.filter(function (p) { return String(p.intento) === String(intento); })[0];
        anunciar(movida ? TEXTOS.movida(movida.numero) : resultado.mensaje);
        return resultado;
      });
    }

    // Flechas: la vista mueve la tarjeta al tiro y el servidor confirma el orden; el foco sigue en la flecha.
    documento.addEventListener("submit", function (evento) {
      var form = evento.target;
      if (!form || !form.hasAttribute || !form.hasAttribute("data-orden-form")) return;
      var boton = evento.submitter;
      var sentido = boton && boton.value;
      if (sentido !== "subir" && sentido !== "bajar") return; // navegador antiguo: sigue el POST con recarga
      evento.preventDefault();
      var tarjeta = form.closest("[data-arrastrable]");
      var tarjetas = tarjetasDe(documento);
      var indice = tarjetas.indexOf(tarjeta);
      var vecina = tarjetas[sentido === "subir" ? indice - 1 : indice + 1];
      var foto = fotografiar(documento);
      if (vecina) {
        if (sentido === "subir") vecina.parentNode.insertBefore(tarjeta, vecina);
        else vecina.parentNode.insertBefore(tarjeta, vecina.nextSibling);
      }
      enviar(form, sentido, foto, tarjeta.getAttribute("data-intento")).then(function () {
        if (boton && !boton.hidden) boton.focus();
        else {
          var otra = tarjeta.querySelector("[data-flecha]:not([hidden])");
          if (otra) otra.focus();
        }
      });
    });

    // Arrastre con Pointer Events sobre la franja.
    var actual = null;

    function adaptador(tarjeta, ventana) {
      var hueco = documento.createElement("div");
      var foto = null;
      var desfase = 0;
      var caja = null;
      hueco.className = "visita-hueco";
      hueco.setAttribute("aria-hidden", "true");
      return {
        iniciar: function () {
          foto = fotografiar(documento);
          caja = tarjeta.getBoundingClientRect();
          desfase = 0;
          hueco.style.height = caja.height + "px";
          tarjeta.parentNode.insertBefore(hueco, tarjeta);
          tarjeta.classList.add("visita-arrastrando");
          tarjeta.style.width = caja.width + "px";
          tarjeta.style.left = caja.left + "px";
          tarjeta.style.top = caja.top + "px";
          return tarjetasDe(documento).indexOf(tarjeta);
        },
        seguir: function (y) {
          if (!desfase) desfase = y - caja.top;
          tarjeta.style.top = (y - desfase) + "px";
        },
        centros: function () {
          return tarjetasDe(documento).filter(function (t) { return t !== tarjeta; }).map(function (t) {
            var r = t.getBoundingClientRect();
            return r.top + r.height / 2;
          });
        },
        colocarHueco: function (indice) {
          var otras = tarjetasDe(documento).filter(function (t) { return t !== tarjeta; });
          if (indice < otras.length) otras[indice].parentNode.insertBefore(hueco, otras[indice]);
          else if (otras.length) otras[otras.length - 1].parentNode.insertBefore(hueco, otras[otras.length - 1].nextSibling);
        },
        desplazar: function (dy) { ventana.scrollBy(0, dy); },
        alto: function () { return ventana.innerHeight; },
        dentro: function (x, y) {
          var zona = documento.querySelector("[data-ruta-lista]");
          var r = zona ? zona.getBoundingClientRect() : null;
          var extra = documento.querySelector("[data-ruta-sin-coordenadas]");
          var r2 = extra && !extra.hidden ? extra.getBoundingClientRect() : null;
          var arriba = r ? r.top : 0;
          var abajo = r2 ? r2.bottom : (r ? r.bottom : 0);
          var izquierda = r ? r.left : 0;
          var derecha = r ? r.right : 0;
          return x >= izquierda - 24 && x <= derecha + 24 && y >= arriba - 48 && y <= abajo + 48;
        },
        soltarEn: function () {
          limpiar();
          hueco.parentNode.replaceChild(tarjeta, hueco);
        },
        devolver: function () {
          limpiar();
          if (hueco.parentNode) hueco.parentNode.removeChild(hueco);
          if (foto) restaurar(foto);
        },
        anunciar: anunciar,
        foto: function () { return foto; },
      };

      function limpiar() {
        tarjeta.classList.remove("visita-arrastrando");
        tarjeta.style.width = "";
        tarjeta.style.left = "";
        tarjeta.style.top = "";
      }
    }

    function bloquearToque(evento) { if (actual && actual.maquina.estado() === "arrastrando") evento.preventDefault(); }

    function terminarEscucha() {
      documento.removeEventListener("pointermove", alMover);
      documento.removeEventListener("pointerup", alSoltar);
      documento.removeEventListener("pointercancel", alCancelar);
      documento.removeEventListener("keydown", alTecla);
      documento.removeEventListener("touchmove", bloquearToque);
      actual = null;
    }

    function alMover(evento) {
      if (actual && actual.maquina.mover({ x: evento.clientX, y: evento.clientY })) evento.preventDefault();
    }

    function alSoltar(evento) {
      if (!actual) return;
      var elegido = actual;
      var indice = elegido.maquina.soltar({ x: evento.clientX, y: evento.clientY });
      terminarEscucha();
      if (indice === null) return;
      var form = elegido.tarjeta.querySelector("[data-orden-form]");
      if (!form) { restaurar(elegido.adaptador.foto()); return; }
      enviar(form, indice + 1, elegido.adaptador.foto(), elegido.tarjeta.getAttribute("data-intento"));
    }

    function alCancelar() {
      if (!actual) return;
      actual.maquina.cancelar();
      terminarEscucha();
    }

    function alTecla(evento) {
      if (evento.key === "Escape") alCancelar();
    }

    documento.addEventListener("pointerdown", function (evento) {
      var franja = evento.target && evento.target.closest ? evento.target.closest("[data-franja]") : null;
      if (!franja || actual || ocupado || evento.button > 0) return;
      var tarjeta = franja.closest("[data-arrastrable]");
      if (!tarjeta || tarjetasDe(documento).length < 2) return;
      var ad = adaptador(tarjeta, entorno.ventana);
      var maquina = crearArrastre(ad, entorno.reloj);
      actual = { maquina: maquina, tarjeta: tarjeta, adaptador: ad };
      documento.addEventListener("pointermove", alMover);
      documento.addEventListener("pointerup", alSoltar);
      documento.addEventListener("pointercancel", alCancelar);
      documento.addEventListener("keydown", alTecla);
      documento.addEventListener("touchmove", bloquearToque, { passive: false });
      if (evento.pointerType !== "touch") evento.preventDefault();
      maquina.presionar({ x: evento.clientX, y: evento.clientY, tipo: evento.pointerType });
    });

    Array.prototype.forEach.call(documento.querySelectorAll("[data-franja]"), function (franja) { franja.hidden = false; });
    return true;
  }

  var api = {
    TEXTOS: TEXTOS, ESPERA_TOQUE_MS: ESPERA_TOQUE_MS, crearArrastre: crearArrastre, nuevaOperacion: nuevaOperacion,
    interpretar: interpretar, guardar: guardar, aplicarOrden: aplicarOrden, preparar: preparar,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else if (global.document) {
    var iniciar = function () {
      preparar(global.document, {
        fetch: global.fetch.bind(global), FormData: global.FormData, navigator: global.navigator, cripto: global.crypto,
        ventana: global, recargar: function () { global.location.reload(); },
        reloj: {
          programar: function (fn, ms) { return global.setTimeout(fn, ms); },
          cancelar: function (id) { global.clearTimeout(id); },
          cuadro: function (fn) { return global.requestAnimationFrame(fn); },
          cancelarCuadro: function (id) { global.cancelAnimationFrame(id); },
        },
      });
    };
    if (global.document.readyState === "loading") global.document.addEventListener("DOMContentLoaded", iniciar);
    else iniciar();
  }
})(typeof window !== "undefined" ? window : globalThis);
