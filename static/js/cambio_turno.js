/* Cambiar fila o marcar urgencia en un modal. Sin JavaScript, los enlaces abren el historial del turno y el
   formulario de urgencia se envía directo; con JavaScript, ambos pasan por un <dialog> con confirmación. */
(function () {
  "use strict";

  // UUID v4 con getRandomValues: también funciona fuera de contextos seguros (http en la red local).
  function nuevaOperacion(cripto) {
    const b = cripto.getRandomValues(new Uint8Array(16));
    b[6] = (b[6] & 15) | 64;
    b[8] = (b[8] & 63) | 128;
    const h = Array.from(b, x => x.toString(16).padStart(2, "0")).join("");
    return h.slice(0, 8) + "-" + h.slice(8, 12) + "-" + h.slice(12, 16) + "-" + h.slice(16, 20) + "-" + h.slice(20);
  }

  function preparar(d, cripto) {
    const dialogos = {fila: d.getElementById("dialogo-fila"), urgencia: d.getElementById("dialogo-urgencia")};
    if (!dialogos.fila || !dialogos.urgencia || typeof dialogos.fila.showModal !== "function") return false;

    function abrir(tipo, origen) {
      const dialogo = dialogos[tipo];
      const formulario = dialogo.querySelector("form");
      formulario.action = origen.dataset.accion;
      formulario.querySelector("[data-operacion]").value = nuevaOperacion(cripto);
      dialogo.querySelectorAll("[data-codigo]").forEach(n => { n.textContent = origen.dataset.codigo; });
      if (tipo === "fila") {
        // La fila actual no se ofrece: elegirla no cambiaría nada.
        dialogo.querySelectorAll("[data-opcion]").forEach(opcion => {
          const actual = opcion.dataset.opcion === origen.dataset.letra;
          opcion.hidden = actual;
          const radio = opcion.querySelector("input");
          radio.checked = false;
          radio.disabled = actual;
        });
      }
      dialogo.showModal();
      // Foco inicial: la primera fila disponible; en la urgencia, «Cancelar», por ser irreversible.
      const foco = tipo === "fila" ? dialogo.querySelector("[data-opcion]:not([hidden]) input") : dialogo.querySelector("[data-cerrar]");
      if (foco) foco.focus();
    }

    d.addEventListener("click", evento => {
      const cerrar = evento.target.closest("[data-cerrar]");
      if (cerrar) { cerrar.closest("dialog").close(); return; }
      const origen = evento.target.closest("[data-abrir]");
      if (!origen || !dialogos[origen.dataset.abrir]) return;
      evento.preventDefault();
      abrir(origen.dataset.abrir, origen);
    });
    return true;
  }

  if (typeof module !== "undefined" && module.exports) module.exports = {nuevaOperacion, preparar};
  else if (typeof document !== "undefined") preparar(document, window.crypto);
})();
