/*
  Preferencias de la persona, aplicadas antes de pintar para evitar saltos: tamaño de texto (franja
  superior) y menú lateral plegado (lo guarda menu.js). Se carga sin `defer`. No guarda datos
  personales: solo "normal", "grande" o "muy-grande", y "plegado", en el almacenamiento local de
  este navegador.
*/
(function () {
  var raiz = document.documentElement;
  var CLAVE = "farmacia.texto";
  var CLAVE_MENU = "farmacia.menu";
  var NIVELES = ["normal", "grande", "muy-grande"];
  var nivel = "normal";

  raiz.classList.add("js");

  try {
    var guardado = window.localStorage.getItem(CLAVE);
    if (NIVELES.indexOf(guardado) !== -1) { nivel = guardado; }
  } catch (error) { /* Sin almacenamiento: se usa el tamaño normal. */ }

  try {
    if (window.localStorage.getItem(CLAVE_MENU) === "plegado") { raiz.setAttribute("data-menu", "plegado"); }
  } catch (error) { /* Sin almacenamiento: el menú queda desplegado. */ }

  function aplicar() {
    if (nivel === "normal") { raiz.removeAttribute("data-texto"); } else { raiz.setAttribute("data-texto", nivel); }
    var botones = document.querySelectorAll("[data-texto-nivel]");
    for (var i = 0; i < botones.length; i++) {
      botones[i].setAttribute("aria-pressed", botones[i].getAttribute("data-texto-nivel") === nivel ? "true" : "false");
    }
  }

  aplicar();
  document.addEventListener("DOMContentLoaded", aplicar);
  document.addEventListener("click", function (evento) {
    var boton = evento.target && evento.target.closest ? evento.target.closest("[data-texto-nivel]") : null;
    if (!boton) { return; }
    nivel = boton.getAttribute("data-texto-nivel");
    try { window.localStorage.setItem(CLAVE, nivel); } catch (error) { /* Se aplica solo en esta visita. */ }
    aplicar();
  });
})();
