/*
  Preferencia de tamaño de texto (franja superior). Se carga sin `defer` para aplicarla antes de
  pintar la página y evitar un salto de tamaño. No guarda datos personales: solo "normal",
  "grande" o "muy-grande" en el almacenamiento local de este navegador.
*/
(function () {
  var raiz = document.documentElement;
  var CLAVE = "farmacia.texto";
  var NIVELES = ["normal", "grande", "muy-grande"];
  var nivel = "normal";

  raiz.classList.add("js");

  try {
    var guardado = window.localStorage.getItem(CLAVE);
    if (NIVELES.indexOf(guardado) !== -1) { nivel = guardado; }
  } catch (error) { /* Sin almacenamiento: se usa el tamaño normal. */ }

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
