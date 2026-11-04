/*
  Menú principal. Dos comportamientos, ambos opcionales: sin JavaScript la columna lateral queda desplegada
  y la hoja «Más» del celular abre y cierra sola (es un <details>).
    1. Columna lateral del computador: el botón la pliega a una columna angosta y recuerda la elección en
       este navegador (clave «farmacia.menu»; preferencias.js la aplica antes de pintar para evitar un salto).
    2. Hoja «Más» del celular: se cierra con Escape (y devuelve el foco al botón), al tocar fuera, al elegir
       una opción, al salir con el teclado de la hoja y al ensanchar la ventana.
  El ancho de corte es el mismo de menu.css (70 rem). No envía nada ni guarda datos personales.
*/
(function () {
  "use strict";
  var CLAVE = "farmacia.menu";
  var plegar = document.querySelector("[data-menu-plegar]");
  var mas = document.querySelector("[data-mas]");
  if (!plegar && !mas) { return; }

  var raiz = document.documentElement;

  function leer() {
    try { return window.localStorage.getItem(CLAVE); } catch (error) { return null; }
  }
  function guardar(plegado) {
    try {
      if (plegado) { window.localStorage.setItem(CLAVE, "plegado"); } else { window.localStorage.removeItem(CLAVE); }
    } catch (error) { /* Sin almacenamiento: el cambio vale solo en esta visita. */ }
  }

  if (plegar) {
    var estaPlegado = function () { return raiz.getAttribute("data-menu") === "plegado"; };
    var mostrar = function () {
      var plegado = estaPlegado();
      plegar.setAttribute("aria-expanded", plegado ? "false" : "true");
      plegar.setAttribute("aria-label", plegado ? "Desplegar el menú" : "Plegar el menú");
    };
    if (leer() === "plegado") { raiz.setAttribute("data-menu", "plegado"); }
    plegar.addEventListener("click", function () {
      if (estaPlegado()) { raiz.removeAttribute("data-menu"); } else { raiz.setAttribute("data-menu", "plegado"); }
      guardar(estaPlegado());
      mostrar();
    });
    mostrar();
  }

  if (mas) {
    var resumen = mas.querySelector("summary");
    var cerrar = function (devolverFoco) {
      if (!mas.open) { return; }
      mas.open = false;
      if (devolverFoco && resumen) { resumen.focus(); }
    };

    document.addEventListener("keydown", function (evento) {
      if (evento.key === "Escape") { cerrar(true); }
    });
    document.addEventListener("click", function (evento) {
      if (mas.open && !mas.contains(evento.target)) { cerrar(false); }
    });
    mas.addEventListener("click", function (evento) {
      var enlace = evento.target && evento.target.closest ? evento.target.closest("a") : null;
      if (enlace) { cerrar(false); }
    });
    mas.addEventListener("focusout", function (evento) {
      if (mas.open && evento.relatedTarget && !mas.contains(evento.relatedTarget)) { cerrar(false); }
    });
    var ancha = window.matchMedia ? window.matchMedia("(min-width: 70.0625rem)") : null;
    if (ancha && ancha.addEventListener) {
      ancha.addEventListener("change", function (evento) { if (evento.matches) { cerrar(false); } });
    }
  }
})();
