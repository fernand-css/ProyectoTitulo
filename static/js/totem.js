/* Nada se guarda en localStorage: la operación pertenece a la sesión del servidor.
   Sin botón «Nueva atención» ni impresión: la pantalla vuelve sola al inicio con un formulario
   oculto (POST a finalizar) y «Necesito más tiempo» amplía el plazo (WCAG 2.2.1). En el resultado,
   «Volver al tótem» envía ese mismo formulario, así que también funciona sin JavaScript. */
(() => {
  "use strict";
  const panel = document.querySelector("[data-totem]");
  if (!panel) return;
  const final = panel.querySelector("[data-finalizar]");
  const input = panel.querySelector("[name=rut]");
  const aviso = panel.querySelector("[data-aviso]");
  const cuenta = panel.querySelector("[data-cuenta]");
  const frase = panel.querySelector("[data-frase]");
  const anuncio = panel.querySelector("[data-anuncio]");
  // En el resultado la franja con la cuenta está siempre visible; en la entrada aparece a los 20 s.
  const resultado = panel.hasAttribute("data-resultado");
  const segundos = Number(panel.dataset.segundos);
  let limite = Date.now() + segundos * 1000;
  let avisado = false;
  let limpiando = false;
  let ultimaActividad = Date.now();
  // Oculta el número de inmediato y detiene la cuenta para no enviar el formulario dos veces.
  function ocultar() {
    limpiando = true;
    if (input) input.value = "";
    panel.hidden = true;
  }
  function limpiar() {
    if (limpiando) return;
    ocultar();
    final.requestSubmit();
  }
  final.addEventListener("submit", ocultar);
  // Lo que se lee en voz alta es la misma frase de la franja. Repetir el mismo texto no se anuncia,
  // por eso se alterna un espacio duro al final.
  function anunciar() {
    if (!anuncio || !frase) return;
    const texto = frase.textContent.trim();
    anuncio.textContent = anuncio.textContent === texto ? texto + "\u00a0" : texto;
  }
  // Formato del RUT mientras se escribe: el último carácter es siempre el dígito verificador, así que el guion
  // y los puntos se ponen solos («1234» → «123-4» → «12.345.678-5»). Se trabaja sobre los caracteres que cuentan
  // (números y K); la K solo vale al final y el cuerpo tiene a lo más 8 cifras. El servidor acepta el RUT con o
  // sin puntos y guion, así que el formato solo ayuda a leerlo antes de confirmar.
  const MAXIMO = 9;
  const significativos = (texto) => String(texto).toUpperCase().replace(/[^0-9K]/g, "");
  function depurar(crudo) {
    const sinCeros = crudo.replace(/^0+/, "");
    return (sinCeros.slice(0, -1).replace(/K/g, "") + sinCeros.slice(-1)).slice(0, MAXIMO);
  }
  function formatear(crudo) {
    if (crudo.length < 2) return crudo;
    return crudo.slice(0, -1).replace(/\B(?=(\d{3})+$)/g, ".") + "-" + crudo.slice(-1);
  }
  // Posición en el texto con formato justo después del carácter que cuenta número `n`.
  function posicion(formateado, n) {
    if (n <= 0) return 0;
    let vistos = 0;
    for (let i = 0; i < formateado.length; i++) if (/[0-9K]/.test(formateado[i]) && ++vistos === n) return i + 1;
    return formateado.length;
  }
  function escribir(crudo, cursor) {
    const limpio = depurar(crudo);
    const texto = formatear(limpio);
    input.value = texto;
    const lugar = posicion(texto, Math.min(cursor, limpio.length));
    if (input.setSelectionRange) input.setSelectionRange(lugar, lugar);
  }
  // Cuántos caracteres que cuentan hay antes de cada extremo de la selección.
  function seleccion() {
    const fin = input.selectionEnd ?? input.value.length;
    const inicio = input.selectionStart ?? fin;
    return [significativos(input.value.slice(0, inicio)).length, significativos(input.value.slice(0, fin)).length];
  }
  if (input) {
    // Teclado físico o texto pegado: se vuelve a dar formato conservando el lugar del cursor.
    input.addEventListener("input", () => {
      const [, despues] = seleccion();
      escribir(significativos(input.value), despues);
    });
    if (input.value) escribir(significativos(input.value), MAXIMO);
  }
  const teclado = panel.querySelector(".totem-teclado");
  if (teclado && input) {
    teclado.hidden = false;
    for (const ayuda of panel.querySelectorAll("[data-solo-js]")) ayuda.hidden = false;
    teclado.addEventListener("click", (event) => {
      const boton = event.target.closest("button");
      if (!boton) return;
      const crudo = significativos(input.value);
      const [inicio, fin] = seleccion();
      if (boton.hasAttribute("data-limpiar")) escribir("", 0);
      else if (boton.hasAttribute("data-borrar")) {
        // Borra el último número o K antes del cursor, nunca solo un punto o el guion.
        const desde = inicio === fin ? Math.max(0, inicio - 1) : inicio;
        escribir(crudo.slice(0, desde) + crudo.slice(fin), desde);
      } else {
        const nuevo = crudo.slice(0, inicio) + boton.dataset.tecla + crudo.slice(fin);
        if (nuevo.length <= MAXIMO) escribir(nuevo, inicio + 1);
      }
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
      if (cuenta && resultado) {
        cuenta.textContent = String(segundos);
        anunciar();
      }
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
