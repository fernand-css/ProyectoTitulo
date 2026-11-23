// Botones informativos de «Mis entregas» (2026-11-22). Sin JavaScript el texto de ayuda queda visible y el botón
// oculto. Con JavaScript el texto se guarda y el párrafo queda vacío como región aria-live: al pulsar el botón
// se escribe el texto (los lectores de pantalla lo anuncian) y se borra a los 3 segundos. Pulsar de nuevo
// lo vuelve a mostrar y reinicia el plazo.
(function () {
  "use strict";
  var DURACION_MS = 3000;

  function preparar(boton) {
    var texto = document.getElementById(boton.getAttribute("aria-controls") || "");
    if (!texto) return;
    var contenido = texto.textContent.trim();
    var temporizador = null;
    texto.setAttribute("aria-live", "polite");
    texto.textContent = "";
    boton.hidden = false;

    function ocultar() {
      temporizador = null;
      texto.textContent = "";
      boton.setAttribute("aria-expanded", "false");
    }

    boton.addEventListener("click", function () {
      if (temporizador) window.clearTimeout(temporizador);
      texto.textContent = contenido;
      boton.setAttribute("aria-expanded", "true");
      temporizador = window.setTimeout(ocultar, DURACION_MS);
    });
  }

  function iniciar() {
    Array.prototype.forEach.call(document.querySelectorAll("[data-ayuda-boton]"), preparar);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
})();
