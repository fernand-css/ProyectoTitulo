/*
  «Registrar fotos» / «Gestionar fotos» (spec 08, RF-08-18).

  Abre el formulario en un <dialog> modal. Nada cambia hasta «Guardar»: marcar una foto para borrar se deshace y
  libera su espacio; los espacios nuevos se muestran hasta completar 3 contando las marcadas; cada espacio muestra
  la vista previa del archivo elegido («Elegir archivo» o «Sacar foto», que en el celular abre la cámara con
  capture="environment"). «Guardar» envía todo en una sola solicitud y el servidor aplica todo o nada. Si una foto
  falla, el aviso queda junto a ella, el foco va al aviso y el modal sigue abierto con lo elegido. Sin conexión no
  se envía nada y se dice con texto. «Cancelar», Esc o la X descartan lo elegido y el foco vuelve al botón.

  Reducción en el navegador (corrección del 2026-11-16): al elegir una foto, se redibuja en un lienzo con el lado
  mayor de 1600 px y se codifica como JPEG. «Guardar» envía esa versión, que pesa mucho menos (menos datos en
  zonas rurales y sin chocar con el límite de 5 MB del servidor) y ya no lleva EXIF ni ubicación, porque el lienzo
  no los copia. El servidor la valida y recomprime igual que siempre (coreapp/utils/custom_image.py). Si el
  navegador no puede reducirla, o la reducida no pesa menos, se envía la original.

  Sin JavaScript, el botón es un enlace a la página con el mismo formulario.
*/
(function (global) {
  "use strict";

  var TEXTOS = {
    sinRed: "No hay conexión. No se guardó ningún cambio; vuelve a pulsar «Guardar» cuando tengas señal.",
    fallo: "No pudimos guardar las fotos y no se aplicó ningún cambio. Inténtalo nuevamente.",
    guardando: "Guardando las fotos…",
    preparando: "Preparando las fotos…",
    sinEspacio: "Ya hay 3 fotos. Marca una para borrar si quieres agregar otra.",
  };

  // El lado mayor coincide con el del servidor; la calidad es algo mayor porque el servidor vuelve a comprimir.
  var REDUCCION = { ladoMaximo: 1600, calidad: 0.85, minimoBytes: 500 * 1024 };

  function medidas(ancho, alto, ladoMaximo) {
    var mayor = Math.max(ancho, alto);
    if (!mayor || mayor <= ladoMaximo) return { ancho: ancho, alto: alto };
    var factor = ladoMaximo / mayor;
    return { ancho: Math.max(1, Math.round(ancho * factor)), alto: Math.max(1, Math.round(alto * factor)) };
  }

  function nombreJpeg(nombre) {
    return String(nombre || "foto").replace(/\.[^./\\]*$/, "") + ".jpg";
  }

  function textoArchivo(original, reducida) {
    var texto = original.name + " · " + tamano(original.size);
    return reducida ? texto + " (se enviará reducida: " + tamano(reducida.size) + ")" : texto;
  }

  /*
    Reduce una foto JPEG o PNG. `herramientas`: decodificar(archivo) → Promise<{fuente, ancho, alto, cerrar?}>
    (con la orientación ya aplicada) y lienzo(ancho, alto) → canvas. Devuelve {archivo, nombre, reducida}; nunca
    falla: ante cualquier problema devuelve la original. Una foto chica (hasta 1600 px y 500 KB) no se toca.
  */
  function reducir(archivo, herramientas, opciones) {
    opciones = opciones || REDUCCION;
    var original = { archivo: archivo, nombre: archivo.name, reducida: false };
    if (!herramientas || !/^image\/(jpeg|png)$/.test(archivo.type)) return Promise.resolve(original);
    var imagen = null;
    return Promise.resolve()
      .then(function () { return herramientas.decodificar(archivo); })
      .then(function (decodificada) {
        imagen = decodificada;
        var destino = medidas(imagen.ancho, imagen.alto, opciones.ladoMaximo);
        var igual = destino.ancho === imagen.ancho && destino.alto === imagen.alto;
        if (igual && archivo.size <= opciones.minimoBytes) return null;
        var lienzo = herramientas.lienzo(destino.ancho, destino.alto);
        var contexto = lienzo.getContext("2d");
        contexto.fillStyle = "#ffffff"; // la transparencia de un PNG queda sobre blanco, como en el servidor
        contexto.fillRect(0, 0, destino.ancho, destino.alto);
        contexto.drawImage(imagen.fuente, 0, 0, destino.ancho, destino.alto);
        return new Promise(function (resolver) { lienzo.toBlob(resolver, "image/jpeg", opciones.calidad); });
      })
      .then(function (blob) {
        if (!blob || !blob.size || blob.size >= archivo.size) return original;
        return { archivo: blob, nombre: nombreJpeg(archivo.name), reducida: true };
      }, function () { return original; })
      .then(function (resultado) {
        try { if (imagen && imagen.cerrar) imagen.cerrar(); } catch (error) { /* nada que liberar */ }
        return resultado;
      });
  }

  // Herramientas del navegador: createImageBitmap con la orientación de la foto o, si no está, una <img>.
  function herramientasNavegador(ventana) {
    var d = ventana.document;
    var prueba = d && d.createElement("canvas");
    if (!prueba || typeof prueba.getContext !== "function" || typeof prueba.toBlob !== "function") return null;

    function porImagen(archivo) {
      return new Promise(function (resolver, rechazar) {
        var url = ventana.URL.createObjectURL(archivo);
        var imagen = new ventana.Image();
        imagen.onload = function () {
          resolver({ fuente: imagen, ancho: imagen.naturalWidth, alto: imagen.naturalHeight,
            cerrar: function () { ventana.URL.revokeObjectURL(url); } });
        };
        imagen.onerror = function () { ventana.URL.revokeObjectURL(url); rechazar(new Error("No se pudo leer la foto.")); };
        imagen.src = url;
      });
    }

    return {
      decodificar: function (archivo) {
        if (typeof ventana.createImageBitmap !== "function") return porImagen(archivo);
        return Promise.resolve()
          .then(function () { return ventana.createImageBitmap(archivo, { imageOrientation: "from-image" }); })
          .then(function (mapa) {
            return { fuente: mapa, ancho: mapa.width, alto: mapa.height, cerrar: function () { mapa.close(); } };
          }, function () { return porImagen(archivo); });
      },
      lienzo: function (ancho, alto) {
        var lienzo = d.createElement("canvas");
        lienzo.width = ancho;
        lienzo.height = alto;
        return lienzo;
      },
    };
  }

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
    var reducciones = []; // {espacio, original, promesa}: la reducción de la foto elegida en cada espacio

    function reduccionDe(espacio) {
      return reducciones.filter(function (r) { return r.espacio === espacio; })[0] || null;
    }

    function olvidarReduccion(espacio) {
      reducciones = reducciones.filter(function (r) { return r.espacio !== espacio; });
    }

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
      olvidarReduccion(espacio);
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
        nombre.textContent = textoArchivo(archivo, null);
        previa.appendChild(nombre);
        previa.hidden = false;
        espacio.querySelector("[data-quitar]").hidden = false;
        if (entorno.herramientas) {
          var reduccion = { espacio: espacio, original: archivo, promesa: reducir(archivo, entorno.herramientas) };
          reducciones.push(reduccion);
          reduccion.promesa.then(function (resultado) {
            if (reduccionDe(espacio) === reduccion && resultado.reducida) {
              nombre.textContent = textoArchivo(archivo, resultado.archivo);
            }
          });
        }
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

    // Cambia en el cuerpo cada foto elegida por su versión reducida, si la hay y sigue siendo la elegida.
    function usarReducidas(form, cuerpo) {
      var visibles = espacios(form).filter(function (espacio) { return !espacio.hidden; });
      return Promise.all(visibles.map(function (espacio) {
        var reduccion = reduccionDe(espacio);
        if (!reduccion) return null;
        return reduccion.promesa.then(function (resultado) {
          if (!resultado.reducida) return;
          espacio.querySelectorAll("[data-archivo]").forEach(function (campo) {
            if (campo.files && campo.files[0] === reduccion.original) cuerpo.set(campo.name, resultado.archivo, resultado.nombre);
          });
        });
      }));
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
      estado.textContent = reducciones.length ? TEXTOS.preparando : TEXTOS.guardando;
      var csrf = form.querySelector("[name=csrfmiddlewaretoken]");
      return usarReducidas(form, cuerpo).then(function () {
        estado.textContent = TEXTOS.guardando;
        return guardar({
          fetch: entorno.fetch, url: form.action, cuerpo: cuerpo, csrf: csrf ? csrf.value : "",
          enLinea: entorno.navigator ? entorno.navigator.onLine : true,
        });
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
    REDUCCION: REDUCCION, medidas: medidas, nombreJpeg: nombreJpeg, textoArchivo: textoArchivo, reducir: reducir,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else if (global.document) {
    var iniciar = function () {
      preparar(global.document, {
        fetch: global.fetch.bind(global), FormData: global.FormData, URL: global.URL, navigator: global.navigator,
        recargar: function () { global.location.reload(); }, herramientas: herramientasNavegador(global),
      });
    };
    if (global.document.readyState === "loading") global.document.addEventListener("DOMContentLoaded", iniciar);
    else iniciar();
  }
})(typeof window !== "undefined" ? window : globalThis);
