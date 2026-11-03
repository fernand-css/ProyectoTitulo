/* Solo consulta estado: ningún GET inicia, llama, cierra o recupera operaciones. */
(() => {
  "use strict";
  const estado = document.querySelector("[data-estado]");
  if (!estado) return;
  const automatico = document.querySelector("[data-automatico]");
  const boton = document.querySelector("[data-actualizar]");
  const mensaje = document.querySelector("[data-mensaje-estado]");
  let enCurso = false;
  let firma = null;
  boton.hidden = false;
  async function actualizar(manual = false) {
    if (enCurso || (!manual && (!automatico.checked || estado.contains(document.activeElement)))) return;
    enCurso = true;
    try {
      const response = await fetch(estado.dataset.url, {credentials: "same-origin", cache: "no-store", headers: {Accept: "application/json"}});
      if (response.status === 403 || response.redirected) {
        automatico.checked = false;
        estado.replaceChildren();
        mensaje.textContent = "Tu sesión ya no permite consultar la atención. Recarga el panel para continuar.";
        return;
      }
      if (!response.ok) throw new Error("estado");
      const datos = await response.json();
      if (manual || !estado.contains(document.activeElement)) {
        estado.innerHTML = datos.html;
        if (firma !== null && firma !== datos.firma) mensaje.textContent = "El estado de atención se actualizó. Revisa tu ventanilla.";
        firma = datos.firma;
      }
    } catch (_) {
      mensaje.textContent = "No se pudo actualizar el estado. Puedes reintentar o recargar el panel.";
    } finally { enCurso = false; }
  }
  boton.addEventListener("click", () => actualizar(true));
  setInterval(() => actualizar(), 1000);
})();
