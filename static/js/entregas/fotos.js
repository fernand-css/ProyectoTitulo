/*
  «Registrar fotos» / «Gestionar fotos» (spec 08, RF-08-18).

  Abre el formulario en un <dialog> modal. Nada cambia hasta «Guardar»: marcar una foto para borrar se deshace y
  libera su espacio; los espacios nuevos se muestran hasta completar 3 contando las marcadas; cada espacio muestra
  la vista previa del archivo elegido («Elegir archivo» o «Sacar foto», que en el celular abre la cámara con
  capture="environment"). «Guardar» envía todo en una sola solicitud y el servidor aplica todo o nada. Si una foto
  falla, el aviso queda junto a ella, el foco va al aviso y el modal sigue abierto con lo elegido. Sin conexión no
  se envía nada y se dice con texto. «Cancelar», Esc o la X descartan lo elegido y el foco vuelve al botón.

  Sin JavaScript, el botón es un enlace a la página con el mismo formulario.
*/
(function (global) {
  "use strict";

  var TEXTOS = {
    sinRed: "No hay conexión. No se guardó ningún cambio; vuelve a pulsar «Guardar» cuando tengas señal.",
    fallo: "No pudimos guardar las fotos y no se aplicó ningún cambio. Inténtalo nuevamente.",
    guardando: "Guardando las fotos…",
    sinEspacio: "Ya hay 3 fotos. Marca una para borrar si quieres agregar otra.",
  };

  function espaciosVisibles(guardadas, marcadas, maximo) {
    return Math.max(0, Math.min(maximo, maximo - guardadas + marcadas));
  }

  function textoCuenta(guardadas, marcadas, nuevas, maximo) {
    if (espaciosVisibles(guardadas, marcadas, maximo) === 0) return TEXTOS.sinEspacio;
    var total = guardadas - marcadas + nuevas;
    return "Al guardar quedarán " + total + " de " + maximo + " fotos.";
  }

  function textoQuitada(numero) {
    return "Se quitó la foto nueva " + numero + " para no pasar de 3 fotos.";
  }

  function tamano(bytes) {
    var mb = bytes / (1024 * 1024);
    if (mb >= 0.1) return mb.toFixed(1).replace(".", ",") + " MB";
    return Math.max(1, Math.round(bytes / 1024)) + " KB";
  }

  // Envía el formulario y traduce la respuesta a {ok, mensaje, foto, volver}. Nunca lanza.
  function guardar(opciones) {
    if (opciones.enLinea === false) return Promise.resolve({ ok: false, mensaje: TEXTOS.sinRed, foto: null });
    return opciones.fetch(opciones.url, {
      method: "POST",
      body: opciones.cuerpo,
      credentials: "same-origin",
      headers: { Accept: "application/json", "X-CSRFToken": opciones.csrf || "" },
    }).then(function (respuesta) {
      return respuesta.json().then(
        function (datos) { return interpretar(respuesta.status, datos); },
        function () { return interpretar(respuesta.status, null); }
      );
    }, function () {
      return { ok: false, mensaje: TEXTOS.sinRed, foto: null };
    });
  }

  function interpretar(estado, datos) {
    if (estado >= 200 && estado < 300 && datos && datos.ok) return { ok: true, volver: datos.volver || null };
    if (datos && datos.error) return { ok: false, mensaje: String(datos.error), foto: datos.foto || null };
    return { ok: false, mensaje: TEXTOS.fallo, foto: null };
  }

  function preparar(d, entorno) {
    var abridor = null;

    function formularioDe(dialogo) { return dialogo.querySelector("[data-fotos-form]"); }

    function mejorar(form) {
      form.setAttribute("data-mejorado", "");
      form.querySelectorAll(".etiqueta-archivo").forEach(function (etiqueta) {
        etiqueta.classList.add("boton", "boton-secundario");
      });
      form.querySelectorAll(".foto-borrar").forEach(function (etiqueta) {
        etiqueta.classList.add("boton", "boton-peligro");
      });
    }

    function espacios(form) { return Array.prototype.slice.call(form.querySelectorAll("[data-espacio]")); }

    function archivoDe(espacio) {
      var elegido = null;
      espacio.querySelectorAll("[data-archivo]").forEach(function (campo) {
        if (campo.files && campo.files.length) elegido = campo.files[0];
      });
      return elegido;
    }

    function limpiarPrevia(espacio) {
      var previa = espacio.querySelector("[data-previa]");
      var imagen = previa.querySelector("img");
      if (imagen && imagen.src && entorno.URL) entorno.URL.revokeObjectURL(imagen.src);
      previa.textContent = "";
      previa.hidden = true;
      espacio.querySelector("[data-quitar]").hidden = true;
    }

    function vaciarEspacio(espacio) {
      espacio.querySelectorAll("[data-archivo]").forEach(function (campo) { campo.value = ""; });
      limpiarPrevia(espacio);
    }

    function mostrarError(form, numero, mensaje) {
      espacios(form).forEach(function (espacio) {
        var aviso = espacio.querySelector("[data-error-espacio]");
        var propio = Number(espacio.getAttribute("data-espacio")) === numero;
        aviso.textContent = propio ? mensaje : "";
        aviso.hidden = !propio;
        espacio.classList.toggle("foto-nueva-error", propio);
        var descripcion = espacio.querySelector(".foto-nueva-descripcion");
        if (propio) descripcion.setAttribute("aria-invalid", "true");
        else descripcion.removeAttribute("aria-invalid");
      });
      var general = form.querySelector("[data-fotos-error]");
      general.textContent = numero ? "" : mensaje || "";
      general.hidden = Boolean(numero) || !mensaje;
    }

    function actualizar(form, anunciar) {
      var maximo = Number(form.getAttribute("data-maximo")) || 3;
      var guardadas = Number(form.getAttribute("data-guardadas")) || 0;
      var marcadas = form.querySelectorAll("[data-borrar]:checked").length;
      var visibles = espaciosVisibles(guardadas, marcadas, maximo);
      var nuevas = 0;
      espacios(form).forEach(function (espacio, indice) {
        var visible = indice < visibles;
        if (!visible && !espacio.hidden && archivoDe(espacio)) {
          vaciarEspacio(espacio);
          if (anunciar) form.querySelector("[data-fotos-estado]").textContent = textoQuitada(indice + 1);
        }
        espacio.hidden = !visible;
        if (visible && archivoDe(espacio)) nuevas += 1;
      });
      form.querySelector("[data-fotos-cuenta]").textContent = textoCuenta(guardadas, marcadas, nuevas, maximo);
    }

    function elegir(form, campo) {
      var espacio = campo.closest("[data-espacio]");
      espacio.querySelectorAll("[data-archivo]").forEach(function (otro) {
        if (otro !== campo) otro.value = ""; // un solo archivo por espacio
      });
      limpiarPrevia(espacio);
      var archivo = campo.files && campo.files[0];
      if (archivo) {
        var previa = espacio.querySelector("[data-previa]");
        var numero = espacio.getAttribute("data-espacio");
        if (entorno.URL && /^image\/(jpeg|png)$/.test(archivo.type)) {
          var imagen = d.createElement("img");
          imagen.src = entorno.URL.createObjectURL(archivo);
          imagen.alt = "Vista previa de la foto nueva " + numero;
          previa.appendChild(imagen);
        }
        var nombre = d.createElement("p");
        nombre.className = "suave";
        nombre.textContent = archivo.name + " · " + tamano(archivo.size);
        previa.appendChild(nombre);
        previa.hidden = false;
        espacio.querySelector("[data-quitar]").hidden = false;
      }
      actualizar(form, false);
    }

    function reiniciar(form) {
      espacios(form).forEach(vaciarEspacio);
      form.reset();
      mostrarError(form, null, "");
      form.querySelector("[data-fotos-estado]").textContent = "";
      actualizar(form, false);
    }

    // Descarta lo elegido y devuelve el foco una sola vez por apertura. No depende solo del evento «close», que
    // el navegador puede entregar con retraso: se llama al cerrar con la X, «Cancelar» o Esc, y «close» respalda.
    var abiertos = [];
    function alCerrar(dialogo) {
      var indice = abiertos.indexOf(dialogo);
      if (indice < 0) return;
      abiertos.splice(indice, 1);
      reiniciar(formularioDe(dialogo));
      if (abridor) abridor.focus();
      abridor = null;
    }

    function cerrarDialogo(dialogo) {
      if (dialogo.open) dialogo.close();
      alCerrar(dialogo);
    }

    function abrir(dialogo, origen) {
      abridor = origen;
      var form = formularioDe(dialogo);
      reiniciar(form);
      if (abiertos.indexOf(dialogo) < 0) abiertos.push(dialogo);
      dialogo.showModal();
      var primero = dialogo.querySelector("[data-borrar], [data-espacio]:not([hidden]) [data-archivo]");
      if (primero) primero.focus();
    }

    function enviar(form) {
      var estado = form.querySelector("[data-fotos-estado]");
      var boton = form.querySelector("[data-fotos-guardar]");
      var cuerpo = new entorno.FormData(form);
      // Los espacios ocultos no viajan: así el envío coincide con lo que se ve.
      espacios(form).forEach(function (espacio) {
        if (!espacio.hidden) return;
        var n = espacio.getAttribute("data-espacio");
        ["archivo_", "camara_", "descripcion_"].forEach(function (campo) { cuerpo.delete(campo + n); });
      });
      boton.disabled = true;
      estado.textContent = TEXTOS.guardando;
      var csrf = form.querySelector("[name=csrfmiddlewaretoken]");
      return guardar({
        fetch: entorno.fetch, url: form.action, cuerpo: cuerpo, csrf: csrf ? csrf.value : "",
        enLinea: entorno.navigator ? entorno.navigator.onLine : true,
      }).then(function (resultado) {
        boton.disabled = false;
        if (resultado.ok) {
          estado.textContent = "Fotos guardadas.";
          entorno.recargar();
          return resultado;
        }
        estado.textContent = "";
        mostrarError(form, resultado.foto, resultado.mensaje);
        var destino = resultado.foto
          ? form.querySelector('[data-espacio="' + resultado.foto + '"] [data-error-espacio]')
          : form.querySelector("[data-fotos-error]");
        if (destino) {
          destino.setAttribute("tabindex", "-1");
          destino.focus();
        }
        return resultado;
      });
    }

    d.querySelectorAll("[data-fotos-dialogo]").forEach(function (dialogo) {
      if (typeof dialogo.showModal !== "function") return; // sin <dialog>: queda el enlace a la página
      var form = formularioDe(dialogo);
      mejorar(form);
      dialogo.addEventListener("cancel", function (evento) { // Esc
        evento.preventDefault();
        cerrarDialogo(dialogo);
      });
      dialogo.addEventListener("close", function () { alCerrar(dialogo); });
      form.addEventListener("change", function (evento) {
        if (evento.target.matches("[data-archivo]")) elegir(form, evento.target);
        if (evento.target.matches("[data-borrar]")) actualizar(form, true);
      });
      form.addEventListener("submit", function (evento) {
        evento.preventDefault();
        enviar(form);
      });
      form.addEventListener("click", function (evento) {
        var quitar = evento.target.closest("[data-quitar]");
        if (quitar) {
          var espacio = quitar.closest("[data-espacio]");
          vaciarEspacio(espacio);
          actualizar(form, false);
          var siguiente = espacio.querySelector("[data-archivo]");
          if (siguiente) siguiente.focus();
        }
      });
    });

    d.addEventListener("click", function (evento) {
      var cerrar = evento.target.closest("[data-fotos-cerrar]");
      if (cerrar && cerrar.closest("[data-fotos-dialogo]")) {
        cerrarDialogo(cerrar.closest("[data-fotos-dialogo]"));
        return;
      }
      var origen = evento.target.closest("[data-fotos-abrir]");
      if (!origen) return;
      var dialogo = d.getElementById(origen.getAttribute("data-fotos-abrir"));
      if (!dialogo || typeof dialogo.showModal !== "function") return;
      evento.preventDefault();
      abrir(dialogo, origen);
    });
    return true;
  }

  var api = {
    TEXTOS: TEXTOS, espaciosVisibles: espaciosVisibles, textoCuenta: textoCuenta, textoQuitada: textoQuitada,
    tamano: tamano, guardar: guardar, interpretar: interpretar, preparar: preparar,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else if (global.document) {
    var iniciar = function () {
      preparar(global.document, {
        fetch: global.fetch.bind(global), FormData: global.FormData, URL: global.URL, navigator: global.navigator,
        recargar: function () { global.location.reload(); },
      });
    };
    if (global.document.readyState === "loading") global.document.addEventListener("DOMContentLoaded", iniciar);
    else iniciar();
  }
})(typeof window !== "undefined" ? window : globalThis);
