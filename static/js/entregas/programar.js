/*
  «Programar entrega» (spec 08, ampliación del 2026-11-13).

  programar      RF-08-16 y RF-08-17: la lista se actualiza mientras se escribe o se cambia un filtro (espera de
                 300 ms, cancela la solicitud anterior y descarta respuestas viejas), por POST para que el RUT o el
                 nombre nunca vayan en la URL. Reemplaza solo la lista, sin mover el foco, y anuncia la cantidad en
                 la región de estado. Conserva la selección al cambiar de página, buscar o filtrar; «Seleccionar los
                 N filtrados» se anula, y lo dice, si cambia la búsqueda o un filtro.
  programarLote  RF-08-17: confirma el lote revisado en tramos de hasta 25 pacientes, en orden, con avance; ante un
                 corte se detiene y permite reintentar desde el primer tramo sin respuesta (el servidor no duplica).

  Sin JavaScript, el formulario funciona igual con «Buscar», las casillas de la página y el envío completo.
*/
document.addEventListener("alpine:init", () => {
  const ESPERA_MS = 300;
  const CAMPOS_FILTRO = ["buscar", "sector", "motivo", "estado", "localidad"];
  const AVISO_TODOS = "Se quitó la selección de todos los filtrados porque cambiaste la búsqueda o un filtro.";

  function pacientes(n) {
    return `${n} ${n === 1 ? "paciente" : "pacientes"} del reparto`;
  }

  function textoSeleccion(n, todos) {
    if (todos) return `Seleccionaste los ${n} filtrados.`;
    if (n === 0) return "Ningún paciente seleccionado.";
    return `${n} ${n === 1 ? "seleccionado" : "seleccionados"}.`;
  }

  Alpine.data("programar", () => {
    // Objetos del navegador fuera del estado reactivo de Alpine.
    let controlador = null;
    let temporizador = null;
    return {
      seleccionados: {},
      todos: false,
      totalTodos: 0,
      claveTodos: "",
      total: 0,
      error: false,
      paginaPendiente: 1,
      secuencia: 0,
      ultimaClave: "",

      init() {
        this.leerLista();
        this.mostrarSoloJs();
        this.ultimaClave = this.claveFiltros();
        this.anunciarSeleccion();
      },

      valor(nombre) {
        const campo = this.$root.elements[nombre];
        return campo && campo.value != null ? String(campo.value) : "";
      },

      claveFiltros() {
        return JSON.stringify(CAMPOS_FILTRO.map((campo) => this.valor(campo).trim()));
      },

      casillas() {
        return Array.from(this.$refs.lista.querySelectorAll("input[data-paciente]"));
      },

      leerLista() {
        const raiz = this.$refs.lista.querySelector("[data-total]");
        this.total = raiz ? Number(raiz.dataset.total) || 0 : 0;
      },

      mostrarSoloJs() {
        this.$refs.lista.querySelectorAll("[data-solo-js]").forEach((elemento) => { elemento.hidden = false; });
      },

      marcarCasillas() {
        for (const casilla of this.casillas()) {
          casilla.checked = this.todos || Boolean(this.seleccionados[casilla.dataset.paciente]);
        }
      },

      cantidad() {
        return this.todos ? this.totalTodos : Object.keys(this.seleccionados).length;
      },

      anunciar(texto) {
        this.$refs.estado.textContent = texto;
      },

      anunciarSeleccion(extra = "") {
        const n = this.cantidad();
        this.$refs.seleccion.textContent = extra ? `${textoSeleccion(n, this.todos)} ${extra}` : textoSeleccion(n, this.todos);
        this.$refs.programar.textContent = `Programar seleccionados (${n})`;
      },

      cambio(evento) {
        const objetivo = evento.target;
        if (objetivo.dataset && objetivo.dataset.paciente) {
          if (evento.type === "change") this.alternar(objetivo);
          return;
        }
        if (!CAMPOS_FILTRO.includes(objetivo.name)) return;
        clearTimeout(temporizador);
        temporizador = setTimeout(() => {
          if (this.claveFiltros() !== this.ultimaClave) this.actualizar(1);
        }, ESPERA_MS);
      },

      alternar(casilla) {
        if (this.todos) {
          // Quitar una casilla deja de ser «todos los filtrados»: quedan los marcados de esta página.
          this.todos = false;
          this.seleccionados = {};
          for (const otra of this.casillas()) if (otra.checked) this.seleccionados[otra.dataset.paciente] = true;
          this.anunciarSeleccion("Se quitó la selección de todos los filtrados; quedan los marcados de esta página.");
          return;
        }
        if (casilla.checked) this.seleccionados[casilla.dataset.paciente] = true;
        else delete this.seleccionados[casilla.dataset.paciente];
        this.anunciarSeleccion();
      },

      clic(evento) {
        const boton = evento.target && evento.target.closest ? evento.target.closest('[data-accion="pagina"]') : null;
        if (!boton) return;
        for (const casilla of this.casillas()) {
          casilla.checked = true;
          this.seleccionados[casilla.dataset.paciente] = true;
        }
        this.anunciarSeleccion();
      },

      quitarSeleccion() {
        this.seleccionados = {};
        this.todos = false;
        this.marcarCasillas();
        this.anunciarSeleccion();
      },

      cancelarTodos() {
        if (!this.todos) return "";
        this.todos = false;
        this.marcarCasillas();
        return AVISO_TODOS;
      },

      enviar(evento) {
        const boton = evento.submitter || null;
        const accion = boton && boton.dataset ? boton.dataset.accion : "";
        if (accion === "programar") {
          if (this.todos && this.claveFiltros() !== this.claveTodos) {
            evento.preventDefault();
            this.anunciarSeleccion(this.cancelarTodos());
            return;
          }
          if (this.cantidad() === 0) {
            evento.preventDefault();
            this.anunciarSeleccion("Marca al menos un paciente antes de programar.");
            return;
          }
          this.escribirOcultos();
          return; // envío normal a la revisión del lote
        }
        evento.preventDefault();
        if (accion === "todos") {
          this.todos = true;
          this.totalTodos = this.total;
          this.claveTodos = this.claveFiltros();
          this.marcarCasillas();
          this.anunciarSeleccion();
          return;
        }
        clearTimeout(temporizador);
        this.actualizar(boton && boton.name === "pagina" ? Number(boton.value) || 1 : 1);
      },

      escribirOcultos() {
        if (this.todos) {
          this.$refs.ocultos.innerHTML = '<input type="hidden" name="todos" value="1">';
          return;
        }
        const ids = Object.keys(this.seleccionados).map(Number).filter((id) => Number.isInteger(id) && id > 0);
        this.$refs.ocultos.innerHTML = ids.map((id) => `<input type="hidden" name="ids" value="${id}">`).join("");
      },

      cuerpo(pagina) {
        const datos = new URLSearchParams();
        datos.set("csrfmiddlewaretoken", this.valor("csrfmiddlewaretoken"));
        for (const campo of CAMPOS_FILTRO) datos.set(campo, this.valor(campo));
        datos.set("pagina", String(pagina));
        return datos;
      },

      reintentar() {
        this.actualizar(this.paginaPendiente);
      },

      async actualizar(pagina) {
        const clave = this.claveFiltros();
        const aviso = clave !== this.ultimaClave ? this.cancelarTodos() : "";
        this.ultimaClave = clave;
        if (controlador) controlador.abort();
        const propio = new AbortController();
        controlador = propio;
        const numero = ++this.secuencia;
        this.error = false;
        try {
          const respuesta = await fetch(this.$root.dataset.urlLista, {
            method: "POST",
            body: this.cuerpo(pagina),
            credentials: "same-origin",
            headers: { "X-CSRFToken": this.valor("csrfmiddlewaretoken"), "X-Requested-With": "XMLHttpRequest" },
            signal: propio.signal,
          });
          if (!respuesta.ok) throw new Error(`HTTP ${respuesta.status}`);
          const html = await respuesta.text();
          if (numero !== this.secuencia) return; // llegó tarde: ya se pidió otra
          this.$refs.lista.innerHTML = html;
          this.leerLista();
          this.mostrarSoloJs();
          this.marcarCasillas();
          this.anunciar(aviso ? `${pacientes(this.total)}. ${aviso}` : pacientes(this.total));
          this.anunciarSeleccion();
        } catch (error) {
          if (numero !== this.secuencia || (error && error.name === "AbortError")) return;
          this.error = true;
          this.paginaPendiente = pagina;
          this.anunciar("No pudimos actualizar la lista. Revisa la conexión y pulsa «Reintentar».");
        }
      },
    };
  });

  Alpine.data("programarLote", () => ({
    iniciado: false,
    ocupado: false,
    terminado: false,
    interrumpido: false,
    hechos: 0,
    siguiente: 0,
    estado: "",
    programados: {},
    omitidosNuevos: [],
    omitidosRevision: 0,
    urlProgramacion: "",

    init() {
      const datos = this.$root.dataset;
      this.url = datos.url;
      this.programables = Number(datos.programables) || 0;
      this.total = Number(datos.total) || 0;
      this.tramo = Number(datos.tramo) || 25;
      this.omitidosRevision = Number(datos.omitidos) || 0;
      this.urlProgramacion = datos.urlProgramacion;
    },

    nombreDe(id) {
      const elemento = this.$root.querySelector(`[data-paciente="${Number(id)}"] [data-nombre]`);
      return elemento ? elemento.textContent.trim() : "Paciente del lote";
    },

    detener(mensaje) {
      this.ocupado = false;
      this.interrumpido = true;
      const motivo = mensaje || "Revisa la conexión y pulsa «Reintentar»: lo ya programado no se repite.";
      this.estado = `Se interrumpió en ${this.siguiente} de ${this.programables}. ${motivo}`;
    },

    async confirmar() {
      if (this.ocupado || this.terminado) return;
      const formulario = this.$root.querySelector("form");
      const token = formulario.elements.csrfmiddlewaretoken.value;
      const contexto = formulario.elements.contexto.value;
      this.ocupado = true;
      this.iniciado = true;
      this.interrumpido = false;
      this.estado = `Programando ${this.siguiente} de ${this.programables}`;
      while (this.siguiente < this.programables) {
        const desde = this.siguiente;
        const hasta = Math.min(desde + this.tramo, this.programables);
        let datos = {};
        try {
          const respuesta = await fetch(this.url, {
            method: "POST",
            credentials: "same-origin",
            headers: { "X-CSRFToken": token, "X-Requested-With": "XMLHttpRequest" },
            body: new URLSearchParams({ csrfmiddlewaretoken: token, contexto, desde: String(desde), hasta: String(hasta) }),
          });
          datos = await respuesta.json().catch(() => ({}));
          if (!respuesta.ok) {
            this.detener(datos.error);
            return;
          }
        } catch (_error) {
          this.detener("");
          return;
        }
        for (const resultado of datos.resultados || []) {
          if (resultado.estado === "programado") {
            this.programados[resultado.paciente] = true;
          } else if (!this.omitidosNuevos.some((omitido) => omitido.paciente === resultado.paciente)) {
            this.omitidosNuevos.push({ paciente: resultado.paciente, nombre: this.nombreDe(resultado.paciente), motivo: resultado.motivo });
          }
        }
        this.siguiente = hasta;
        this.hechos = hasta;
        this.estado = `Programando ${hasta} de ${this.programables}`;
      }
      const programados = Object.keys(this.programados).length;
      const omitidos = this.omitidosRevision + this.omitidosNuevos.length;
      this.estado = `Se programaron ${programados} de ${this.total}.` +
        (omitidos ? ` No se programaron ${omitidos}: revisa el motivo de cada uno en la lista.` : "");
      this.ocupado = false;
      this.terminado = true;
    },
  }));
});
