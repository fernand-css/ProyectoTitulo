/*
  Menú principal plegable. Con pantalla angosta y JavaScript, el menú se oculta tras el botón «Menú»;
  sin JavaScript (o en pantalla ancha) el menú se ve siempre completo. El ancho de corte es el mismo
  de base.css (64rem). No guarda nada ni envía datos.
*/
(function () {
  var boton = document.querySelector("[data-menu-boton]");
  var menu = document.querySelector("[data-menu]");
  if (!boton || !menu) { return; }

  var angosta = window.matchMedia ? window.matchMedia("(max-width: 64rem)") : null;

  function abierto() { return boton.getAttribute("aria-expanded") === "true"; }

  function cambiar(abrir, devolverFoco) {
    if (abrir) { menu.classList.add("nav-abierto"); } else { menu.classList.remove("nav-abierto"); }
    boton.setAttribute("aria-expanded", abrir ? "true" : "false");
    if (!abrir && devolverFoco) { boton.focus(); }
  }

  boton.addEventListener("click", function () { cambiar(!abierto(), false); });

  document.addEventListener("keydown", function (evento) {
    if (evento.key === "Escape" && abierto()) { cambiar(false, true); }
  });

  // Tocar fuera del menú lo cierra.
  document.addEventListener("click", function (evento) {
    if (abierto() && !menu.contains(evento.target) && !boton.contains(evento.target)) { cambiar(false, false); }
  });

  // Al ensanchar la ventana el menú vuelve a mostrarse completo, así que se reinicia el estado.
  if (angosta && angosta.addEventListener) {
    angosta.addEventListener("change", function (evento) { if (!evento.matches) { cambiar(false, false); } });
  }
})();
