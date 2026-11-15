/* Nada se guarda en localStorage: la operación pertenece a la sesión del servidor.
   Sin botón «Nueva atención» ni impresión: la pantalla vuelve sola al inicio con un formulario
   oculto (POST a finalizar) y «Necesito más tiempo» amplía el plazo (WCAG 2.2.1). */
(() => {
  "use strict";
  const panel = document.querySelector("[data-totem]");
  if (!panel) return;
  const final = panel.querySelector("[data-finalizar]");
  const input = panel.querySelector("[name=rut]");
  const aviso = panel.querySelector("[data-aviso]");
  const cuenta = panel.querySelector("[data-cuenta]");
  // En el resultado la franja con la cuenta está siempre visible; en la entrada aparece a los 20 s.
  const resultado = panel.hasAttribute("data-resultado");
  const segundos = Number(panel.dataset.segundos);
  let limite = Date.now() + segundos * 1000;
  let avisado = false;
  let limpiando = false;
  let ultimaActividad = Date.now();
  function limpiar() {
    if (limpiando) return;
    limpiando = true;
    if (input) input.value = "";
    panel.hidden = true;
    final.requestSubmit();
  }
  const teclado = panel.querySelector(".totem-teclado");
  if (teclado) {
    teclado.hidden = false;
    teclado.addEventListener("click", (event) => {
      const boton = event.target.closest("button");
      if (!boton) return;
      const inicio = input.selectionStart ?? input.value.length;
      const fin = input.selectionEnd ?? inicio;
      if (boton.hasAttribute("data-limpiar")) input.value = "";
      else if (boton.hasAttribute("data-borrar")) input.setRangeText("", inicio === fin ? Math.max(0, inicio - 1) : inicio, fin, "end");
      else if (input.value.length - (fin - inicio) < input.maxLength) input.setRangeText(boton.dataset.tecla, inicio, fin, "end");
      input.focus();
    });
  }
  // La ampliación es explícita: evita solicitudes por cada pulsación del teclado.
  async function ampliar() {
    try {
      const response = await fetch(panel.dataset.continuar, {method: "POST", body: new FormData(final), credentials: "same-origin", cache: "no-store"});
      if (!response.ok) return limpiar();
      limite = Date.now() + segundos * 1000;
      if (!resultado) aviso.hidden = true;
      avisado = false;
      if (cuenta && resultado) cuenta.textContent = String(segundos);
      return true;
    } catch (_) { limpiar(); return false; }
  }
  panel.querySelector("[data-ampliar]").addEventListener("click", ampliar);
  if (input) {
    for (const evento of ["keydown", "pointerdown"]) panel.addEventListener(evento, () => {
      if (Date.now() - ultimaActividad > 30000) {
        ultimaActividad = Date.now();
        ampliar();
      }
    });
  }
  setInterval(() => {
    if (limpiando) return;
    const faltan = Math.ceil((limite - Date.now()) / 1000);
    if (faltan <= 0) return limpiar();
    if (resultado || faltan <= 20) {
      if (!avisado) { aviso.hidden = false; avisado = true; }
      if (cuenta) cuenta.textContent = String(faltan);
    }
  }, 1000);
  window.addEventListener("pageshow", (event) => {
    const navigation = performance.getEntriesByType("navigation")[0];
    if (event.persisted || navigation?.type === "back_forward") {
      panel.hidden = true;
      if (input) input.value = "";
      window.location.replace(panel.dataset.inicio);
    }
  });
})();
