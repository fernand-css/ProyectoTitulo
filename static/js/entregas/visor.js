/*
  Visor de las fotos del domicilio (spec 08, RF-08-19).

  Cada miniatura es un enlace a la imagen privada; con JavaScript pasa a ser un botón («Ver foto ampliada: …»)
  que abre la imagen en un <dialog> modal, con su descripción como texto alternativo y como pie. Se cierra con la
  X, con un clic fuera de la imagen o con Esc (comportamiento nativo del diálogo). Mientras está abierto, el foco
  queda dentro; al cerrar, vuelve a la miniatura. La imagen se pide a la misma vista privada, sin caché.
*/
(function (global) {
  "use strict";

  function nombre(descripcion) {
    return "Foto ampliada: " + descripcion;
  }

  // Cierra salvo que el clic caiga sobre la imagen misma (el botón X se cierra por su cuenta).
  function esFuera(objetivo) {
    return !(objetivo && objetivo.closest && objetivo.closest("img"));
  }

  function preparar(d) {
    var dialogo = d.querySelector("[data-visor]");
    if (!dialogo || typeof dialogo.showModal !== "function") return false; // sin <dialog>: quedan los enlaces
    var pie = dialogo.querySelector("[data-visor-pie]");
    var cerrar = dialogo.querySelector("[data-visor-cerrar]");
    var origen = null;
    var imagen = null;

    function abrir(enlace) {
      var descripcion = enlace.getAttribute("data-descripcion") || "";
      quitarImagen();
      origen = enlace;
      imagen = d.createElement("img");
      imagen.src = enlace.getAttribute("href");
      imagen.alt = descripcion;
      imagen.className = "visor-imagen";
      pie.parentNode.insertBefore(imagen, pie);
      pie.textContent = descripcion;
      dialogo.setAttribute("aria-label", nombre(descripcion));
      dialogo.showModal();
      cerrar.focus();
    }

    function quitarImagen() {
      if (imagen && imagen.parentNode) imagen.parentNode.removeChild(imagen);
      imagen = null;
    }

    // Limpia y devuelve el foco al cerrar con la X, un clic fuera o Esc. El evento «close» solo respalda: el
    // navegador puede entregarlo con retraso, y si el visor ya se volvió a abrir, no se toca.
    function alCerrar() {
      if (dialogo.open) return;
      quitarImagen();
      pie.textContent = "";
      if (origen) origen.focus();
      origen = null;
    }

    function cerrarVisor() {
      if (dialogo.open) dialogo.close();
      alCerrar();
    }

    dialogo.addEventListener("close", alCerrar);
    dialogo.addEventListener("cancel", function (evento) { // Esc
      evento.preventDefault();
      cerrarVisor();
    });
    dialogo.addEventListener("click", function (evento) {
      if (evento.target.closest("[data-visor-cerrar]") || esFuera(evento.target)) cerrarVisor();
    });

    d.querySelectorAll("[data-visor-abrir]").forEach(function (enlace) {
      enlace.setAttribute("role", "button");
      enlace.addEventListener("keydown", function (evento) {
        if (evento.key === " ") { evento.preventDefault(); abrir(enlace); } // un botón también se activa con Espacio
      });
    });
    d.addEventListener("click", function (evento) {
      var enlace = evento.target.closest("[data-visor-abrir]");
      if (!enlace) return;
      evento.preventDefault();
      abrir(enlace);
    });
    return true;
  }

  var api = { nombre: nombre, esFuera: esFuera, preparar: preparar };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else if (global.document) {
    if (global.document.readyState === "loading") {
      global.document.addEventListener("DOMContentLoaded", function () { preparar(global.document); });
    } else {
      preparar(global.document);
    }
  }
})(typeof window !== "undefined" ? window : globalThis);
