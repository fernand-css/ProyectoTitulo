/*
  Búsqueda instantánea de las listas con buscador: Pacientes, Todas las recetas, Pendientes de retiro, Domicilios y
  Excepciones de reparto. Se comporta como la de «Programar entrega» (entregas/programar.js), sin su selección.

  Marcado que espera:
    form[data-en-vivo="busqueda"]  el buscador. Escribir o cambiar una lista desplegable actualiza los resultados tras
                                   300 ms de pausa; «Buscar», Enter y los botones de filtro, al instante. Una búsqueda
                                   nueva vuelve a la primera página.
    form[data-en-vivo="pagina"]    «Anterior» y «Siguiente»: cambian de página sin recargar y llevan el foco al resumen.
    [data-zona="nombre"]           partes que el servidor vuelve a dibujar (resultados, filtros, «Quitar filtros»); se
                                   reemplazan por las del fragmento con el mismo nombre. El campo donde se escribe nunca
                                   está en una zona: el foco y el cursor no se mueven. Debe existir data-zona="resultados".
    [data-anuncio]                 dentro de una zona: su texto (la cantidad encontrada) se anuncia en la región de estado.
    [data-solo-js]                 dentro del buscador: ayuda que solo es cierta con JavaScript; se muestra al iniciar.

  Pide por POST a la dirección del formulario con la cabecera X-Busqueda-En-Vivo (coreapp/busqueda.py), para que el
  RUT o el nombre nunca vayan en la URL. Cancela la solicitud anterior y descarta las respuestas que llegan tarde. Si
  falla, lo dice y ofrece «Reintentar»; si la sesión venció, sigue a la página de inicio de sesión. Sin JavaScript,
  los formularios se envían como siempre.
*/
(function (global) {
  "use strict";

  const ESPERA_MS = 300;
  const CABECERA = "X-Busqueda-En-Vivo";
  const CAMPO_PAGINA = "pagina";
  const CAMPO_CSRF = "csrfmiddlewaretoken";
  const MENSAJE_ERROR = "No pudimos actualizar la lista. Revisa la conexión y pulsa «Reintentar».";
  const ENFOCABLES = "a[href], button, input, select, textarea, [tabindex]";

  function texto(elemento) {
    return elemento ? String(elemento.textContent || "").replace(/\s+/g, " ").trim() : "";
  }

  function esEnvio(campo) {
    return String(campo.type || "").toLowerCase() === "submit";
  }

  // El botón que usa Enter en el campo: el primer botón de envío del formulario.
  function botonPorOmision(formulario) {
    return Array.prototype.find.call(formulario.elements, esEnvio) || null;
  }

  // Campos que, al cambiar, piden resultados nuevos: lo que la persona escribe o elige (no los ocultos ni botones).
  function esCampoDeBusqueda(campo) {
    if (!campo || !campo.name || campo.name === CAMPO_CSRF || campo.name === CAMPO_PAGINA) return false;
    const tipo = String(campo.type || "").toLowerCase();
    if (campo.tagName === "SELECT" || campo.tagName === "TEXTAREA") return true;
    return campo.tagName === "INPUT" && !["hidden", "submit", "button", "reset", "image", "file"].includes(tipo);
  }

  // Una búsqueda nueva: los campos sin la página, más el botón por omisión, que en Pacientes y Recetas lleva el filtro
  // vigente para que Enter no lo pierda. Si se pulsó un botón de filtro con su mismo nombre, el botón por omisión
  // adopta ese valor antes (así lo siguiente que se escriba conserva el filtro recién elegido).
  function paresBusqueda(formulario, leer, emisor) {
    const omision = botonPorOmision(formulario);
    const mismoNombre = Boolean(emisor && omision && emisor.name && emisor.name === omision.name);
    if (mismoNombre && emisor !== omision) omision.value = emisor.value;
    const pares = leer(formulario).filter((par) => par[0] !== CAMPO_PAGINA);
    if (omision && omision.name) pares.push([omision.name, omision.value]);
    if (emisor && emisor.name && emisor !== omision && !mismoNombre) pares.push([emisor.name, emisor.value]);
    return pares;
  }

  // Un cambio de página: el formulario de la paginación tal como lo dibujó el servidor, más el botón pulsado.
  function paresPagina(formulario, leer, emisor) {
    const pares = leer(formulario);
    if (emisor && emisor.name) pares.push([emisor.name, emisor.value]);
    return pares;
  }

  // Identifica una búsqueda sin el token ni la página: dos claves iguales piden los mismos resultados.
  function claveDe(pares) {
    return JSON.stringify(pares.filter((par) => par[0] !== CAMPO_CSRF && par[0] !== CAMPO_PAGINA));
  }

  function describir(elemento) {
    return {
      id: elemento.id || "",
      nombre: (elemento.getAttribute && elemento.getAttribute("name")) || "",
      valor: elemento.value != null ? String(elemento.value) : "",
      etiqueta: elemento.tagName,
      texto: texto(elemento),
    };
  }

  // El equivalente, en la zona nueva, del elemento que tenía el foco: mismo id, mismo nombre y valor, o mismo texto.
  function equivalente(zona, descripcion) {
    const candidatos = Array.from(zona.querySelectorAll(ENFOCABLES));
    return candidatos.find((e) => descripcion.id && e.id === descripcion.id)
      || candidatos.find((e) => descripcion.nombre && e.getAttribute("name") === descripcion.nombre
        && String(e.value) === descripcion.valor)
      || candidatos.find((e) => descripcion.texto && e.tagName === descripcion.etiqueta && texto(e) === descripcion.texto)
      || null;
  }

  function leerFormulario(formulario) {
    return Array.from(new global.FormData(formulario), (par) => [par[0], String(par[1])]);
  }

  function iniciar(d, entorno) {
    const formulario = d.querySelector('form[data-en-vivo="busqueda"]');
    const inicial = d.querySelector('[data-zona="resultados"]');
    if (!formulario || !inicial) return null;
    const leer = entorno.leer || leerFormulario;
    const parsear = entorno.parsear || function (html) {
      const plantilla = d.createElement("template");
      plantilla.innerHTML = html;
      return Array.from(plantilla.content.querySelectorAll("[data-zona]"));
    };

    let controlador = null;
    let temporizador = null;
    let secuencia = 0;
    let ultimo = null;
    let ultimaClave = claveDe(paresBusqueda(formulario, leer, null));

    // Región de estado (cantidades, solo para lectores de pantalla) y aviso de error, justo antes de los resultados.
    const caja = d.createElement("div");
    caja.className = "busqueda-en-vivo";
    const estado = d.createElement("p");
    estado.className = "sr-only";
    estado.setAttribute("role", "status");
    const error = d.createElement("div");
    error.className = "message message-error busqueda-en-vivo-error";
    error.hidden = true;
    const errorCuerpo = d.createElement("div");
    const errorTexto = d.createElement("p");
    errorTexto.textContent = MENSAJE_ERROR;
    const reintentar = d.createElement("button");
    reintentar.type = "button";
    reintentar.className = "boton boton-secundario";
    reintentar.textContent = "Reintentar";
    errorCuerpo.appendChild(errorTexto);
    errorCuerpo.appendChild(reintentar);
    error.appendChild(errorCuerpo);
    caja.appendChild(estado);
    caja.appendChild(error);
    inicial.parentNode.insertBefore(caja, inicial);

    const campoTexto = formulario.querySelector('input[type="search"]');
    for (const ayuda of formulario.querySelectorAll("[data-solo-js]")) {
      ayuda.hidden = false;
      if (ayuda.id && campoTexto) {
        const descrito = (campoTexto.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
        if (!descrito.includes(ayuda.id)) campoTexto.setAttribute("aria-describedby", descrito.concat(ayuda.id).join(" "));
      }
    }

    function zonaResultados() {
      return d.querySelector('[data-zona="resultados"]');
    }

    function ocupado(valor) {
      const zona = zonaResultados();
      if (!zona) return;
      if (valor) zona.setAttribute("aria-busy", "true");
      else zona.removeAttribute("aria-busy");
    }

    function enfocarResumen(anuncio) {
      const blanco = anuncio || zonaResultados();
      if (!blanco) return;
      blanco.setAttribute("tabindex", "-1");
      blanco.focus();
    }

    function reemplazar(zonas, paginar) {
      const activo = d.activeElement;
      let destino = null;
      let perdido = false;
      let anuncio = null;
      for (const nueva of zonas) {
        const actual = d.querySelector('[data-zona="' + nueva.getAttribute("data-zona") + '"]');
        if (!actual) continue;
        const descripcion = activo && activo !== d.body && actual.contains(activo) ? describir(activo) : null;
        actual.replaceWith(nueva);
        if (descripcion) {
          destino = equivalente(nueva, descripcion);
          perdido = !destino;
        }
        anuncio = anuncio || nueva.querySelector("[data-anuncio]");
      }
      if (paginar || perdido) {
        // Página nueva (o el botón pulsado ya no existe): el foco va al resumen, que el lector lee al llegar.
        enfocarResumen(anuncio);
        return;
      }
      if (destino) destino.focus();
      estado.textContent = texto(anuncio);
    }

    async function pedir(pares, paginar) {
      entorno.clearTimeout(temporizador);
      temporizador = null;
      if (!paginar) ultimaClave = claveDe(pares);
      ultimo = { pares, paginar };
      if (controlador) controlador.abort();
      const propio = entorno.AbortController ? new entorno.AbortController() : null;
      controlador = propio;
      const numero = ++secuencia;
      error.hidden = true;
      ocupado(true);
      const token = pares.find((par) => par[0] === CAMPO_CSRF);
      try {
        const respuesta = await entorno.fetch(formulario.action, {
          method: "POST",
          body: new URLSearchParams(pares),
          credentials: "same-origin",
          headers: { [CABECERA]: "1", "X-CSRFToken": token ? token[1] : "" },
          signal: propio ? propio.signal : undefined,
        });
        if (numero !== secuencia) return; // llegó tarde: ya se pidió otra
        if (respuesta.redirected) {
          entorno.navegar(respuesta.url); // la sesión venció: el servidor manda al inicio de sesión
          return;
        }
        if (!respuesta.ok) throw new Error("HTTP " + respuesta.status);
        const html = await respuesta.text();
        if (numero !== secuencia) return;
        const zonas = parsear(html);
        if (!zonas.length) throw new Error("La respuesta no trae zonas");
        reemplazar(zonas, paginar);
      } catch (falla) {
        if (numero !== secuencia || (falla && falla.name === "AbortError")) return;
        ocupado(false);
        ultimaClave = null; // lo próximo que se escriba vuelve a pedir, aunque repita el texto que falló
        error.hidden = false;
        estado.textContent = MENSAJE_ERROR;
      }
    }

    function programar() {
      entorno.clearTimeout(temporizador);
      temporizador = entorno.setTimeout(function () {
        temporizador = null;
        const pares = paresBusqueda(formulario, leer, null);
        if (claveDe(pares) !== ultimaClave) pedir(pares, false);
      }, ESPERA_MS);
    }

    function alCambiar(evento) {
      if (esCampoDeBusqueda(evento.target)) programar();
    }

    formulario.addEventListener("input", alCambiar);
    formulario.addEventListener("change", alCambiar);

    // En el documento: los formularios de la paginación se vuelven a dibujar con cada respuesta.
    d.addEventListener("submit", function (evento) {
      const origen = evento.target;
      const tipo = origen && origen.getAttribute ? origen.getAttribute("data-en-vivo") : null;
      if (!(tipo === "busqueda" && origen === formulario) && tipo !== "pagina") return;
      const emisor = evento.submitter || null;
      if (emisor && emisor.hasAttribute && emisor.hasAttribute("formaction")) return; // va a otra parte: envío normal
      evento.preventDefault();
      const busqueda = paresBusqueda(formulario, leer, tipo === "busqueda" ? emisor : null);
      // Si se escribió algo y se pulsó otra página antes de la pausa, manda la búsqueda nueva desde la primera.
      if (tipo === "pagina" && claveDe(busqueda) === ultimaClave) pedir(paresPagina(origen, leer, emisor), true);
      else pedir(busqueda, false);
    });

    reintentar.addEventListener("click", function () {
      if (ultimo) pedir(ultimo.pares, ultimo.paginar);
    });

    return { formulario, estado, error, reintentar, pedir };
  }

  const api = {
    ESPERA_MS, CABECERA, MENSAJE_ERROR, botonPorOmision, esCampoDeBusqueda, paresBusqueda, paresPagina, claveDe,
    describir, equivalente, iniciar,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else if (global.document && global.fetch && global.FormData && global.URLSearchParams) {
    const arrancar = function () {
      iniciar(global.document, {
        fetch: global.fetch.bind(global),
        setTimeout: global.setTimeout.bind(global),
        clearTimeout: global.clearTimeout.bind(global),
        AbortController: global.AbortController,
        navegar: function (url) { global.location.assign(url); },
      });
    };
    if (global.document.readyState === "loading") global.document.addEventListener("DOMContentLoaded", arrancar);
    else arrancar();
  }
})(typeof window !== "undefined" ? window : globalThis);
