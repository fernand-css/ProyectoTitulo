/*
  Preferencias de la persona, aplicadas antes de pintar para evitar saltos: tamaño de texto, modo oscuro
  (desde el 2026-11-22, «Accesibilidad» del menú y hoja «Más» del celular) y menú lateral plegado (lo guarda
  menu.js). Se carga sin `defer`. No guarda datos personales: solo "normal", "grande" o "muy-grande", "oscuro"
  o "claro", y "plegado", en el almacenamiento local de este navegador. Las pantallas públicas marcan <html>
  con `data-solo-claro`: ahí el modo oscuro no se aplica (el tótem y la sala tienen su propia paleta).
*/
(function () {
  var raiz = document.documentElement;
  var CLAVE = "farmacia.texto";
  var CLAVE_TEMA = "farmacia.tema";
  var CLAVE_MENU = "farmacia.menu";
  var NIVELES = ["normal", "grande", "muy-grande"];
  var COLOR_BARRA = { claro: "#244bc3", oscuro: "#0e1621" };
  var nivel = "normal";
  var tema = "claro";
  var soloClaro = raiz.hasAttribute("data-solo-claro");

  raiz.classList.add("js");

  try {
    var guardado = window.localStorage.getItem(CLAVE);
    if (NIVELES.indexOf(guardado) !== -1) { nivel = guardado; }
  } catch (error) { /* Sin almacenamiento: se usa el tamaño normal. */ }

  try {
    if (window.localStorage.getItem(CLAVE_TEMA) === "oscuro") { tema = "oscuro"; }
  } catch (error) { /* Sin almacenamiento: modo claro. */ }

  try {
    if (window.localStorage.getItem(CLAVE_MENU) === "plegado") { raiz.setAttribute("data-menu", "plegado"); }
  } catch (error) { /* Sin almacenamiento: el menú queda desplegado. */ }

  function aplicar() {
    if (nivel === "normal") { raiz.removeAttribute("data-texto"); } else { raiz.setAttribute("data-texto", nivel); }
    var oscuro = tema === "oscuro" && !soloClaro;
    if (oscuro) { raiz.setAttribute("data-tema", "oscuro"); } else { raiz.removeAttribute("data-tema"); }
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta && !soloClaro) { meta.setAttribute("content", oscuro ? COLOR_BARRA.oscuro : COLOR_BARRA.claro); }
    var botones = document.querySelectorAll("[data-texto-nivel]");
    for (var i = 0; i < botones.length; i++) {
      botones[i].setAttribute("aria-pressed", botones[i].getAttribute("data-texto-nivel") === nivel ? "true" : "false");
    }
    var alternar = document.querySelectorAll("[data-tema-alternar]");
    for (var j = 0; j < alternar.length; j++) { alternar[j].setAttribute("aria-pressed", oscuro ? "true" : "false"); }
    var estados = document.querySelectorAll("[data-tema-estado]");
    for (var k = 0; k < estados.length; k++) { estados[k].textContent = oscuro ? "Sí" : "No"; }
  }

  function guardar(clave, valor) {
    try { window.localStorage.setItem(clave, valor); } catch (error) { /* Se aplica solo en esta visita. */ }
  }

  aplicar();
  document.addEventListener("DOMContentLoaded", aplicar);
  document.addEventListener("click", function (evento) {
    var objetivo = evento.target && evento.target.closest ? evento.target : null;
    if (!objetivo) { return; }
    var boton = objetivo.closest("[data-texto-nivel]");
    if (boton) {
      nivel = boton.getAttribute("data-texto-nivel");
      guardar(CLAVE, nivel);
      aplicar();
      return;
    }
    if (objetivo.closest("[data-tema-alternar]")) {
      tema = tema === "oscuro" ? "claro" : "oscuro";
      guardar(CLAVE_TEMA, tema);
      aplicar();
    }
  });
})();
