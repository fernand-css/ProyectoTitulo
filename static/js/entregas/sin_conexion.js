/*
  Reparto sin conexión en la página (spec 11, RF-11-02 a RF-11-06, RF-11-10, RF-11-13 y RF-11-16).

  Tres lugares, según lo que tenga la página:
  - «Mis entregas» (con señal): descarga el paquete de la ruta y lo guarda en el celular, pide al service worker que
    guarde la página sin conexión, marca las tarjetas con registros por enviar y envía la cola.
  - «Registrar visita» (con señal): el formulario del 08 se envía como siempre; solo si el envío falla por la red,
    o el navegador está sin conexión, el registro se guarda en la cola con el identificador del formulario.
  - Vista sin conexión (la muestra el service worker): dibuja la ruta desde el paquete, con «Entregada» y «No
    entregada», «Deshacer» para lo que no se ha enviado y la lista «No se pudo enviar».
  En los tres, la barra de estado (región aria-live) dice con texto la conexión, la hora de la última descarga,
  cuántos registros faltan por enviar, «Enviando…» y el resultado del último envío. Nunca muestra el RUT: el paquete
  no lo trae. No usa localStorage: todo vive en IndexedDB (almacen.js).
*/
(function (global) {
  "use strict";

  var TEXTOS = {
    conectado: "Conectado",
    sinConexion: "Sin conexión",
    sinPaquete: "No hay una ruta guardada para hoy. Ábrela con señal.",
    noSeGuardo: "No se pudo guardar la ruta en este celular. Vuelve a abrir «Mis entregas» con señal.",
    sinPendientes: "No hay registros por enviar.",
    enviando: "Enviando…",
    sinRed: "Sin señal: los registros se enviarán solos al volver la conexión.",
    sesion: "Tu sesión venció o cambió: vuelve a entrar con esta cuenta para enviar los registros.",
    servidor: "El servidor no respondió. Se reintentará en 30 segundos.",
    limite: "Se enviaron muchos registros seguidos. Se reintentará en un minuto.",
    porEnviar: "Registrada sin conexión · por enviar",
    guardado: "Registro guardado en este celular: se enviará al volver la señal.",
    deshecho: "Registro deshecho. La visita vuelve a estar por registrar.",
    duplicado: "Esta visita ya tiene un registro por enviar.",
    confirmar: "Marca la casilla para confirmar que entregaste las recetas.",
    motivo: "Elige el motivo de la no entrega.",
    notaLarga: "La nota admite hasta 200 caracteres.",
    notaOtro: "Con el motivo «Otro», escribe una nota breve.",
    paraVer: "Pulsa «Actualizar la lista» para ver tu ruta al día.",
  };
  var NOTA_MAXIMA = 200;

  function plural(n, uno, varios) { return n + " " + (n === 1 ? uno : varios); }

  function horaCorta(valor) {
    var fecha = valor instanceof Date ? valor : new Date(valor);
    if (isNaN(fecha.getTime())) return "";
    function dos(n) { return (n < 10 ? "0" : "") + n; }
    return dos(fecha.getHours()) + ":" + dos(fecha.getMinutes());
  }

  function fechaCorta(iso) {
    var partes = String(iso || "").split("-");
    return partes.length === 3 ? partes[2] + "/" + partes[1] : "";
  }

  function nuevoId(entorno) {
    if (entorno.uuid) return entorno.uuid();
    var cripto = global.crypto;
    if (cripto && cripto.randomUUID) return cripto.randomUUID();
    // Respaldo RFC 4122 v4 con getRandomValues.
    var bytes = new Uint8Array(16);
    cripto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    var hex = Array.prototype.map.call(bytes, function (b) { return (b < 16 ? "0" : "") + b.toString(16); }).join("");
    return hex.slice(0, 8) + "-" + hex.slice(8, 12) + "-" + hex.slice(12, 16) + "-" + hex.slice(16, 20) + "-" + hex.slice(20);
  }

  // Crea un elemento: el(doc, "p", {class: "x"}, ["texto", otroNodo]).
  function el(documento, etiqueta, atributos, hijos) {
    var nodo = documento.createElement(etiqueta);
    Object.keys(atributos || {}).forEach(function (nombre) {
      var valor = atributos[nombre];
      if (valor === false || valor === null || valor === undefined) return;
      nodo.setAttribute(nombre, valor === true ? "" : String(valor));
    });
    (hijos || []).forEach(function (hijo) {
      if (hijo === null || hijo === undefined) return;
      nodo.appendChild(typeof hijo === "string" ? documento.createTextNode(hijo) : hijo);
    });
    return nodo;
  }

  function vaciar(nodo) {
    while (nodo.firstChild) nodo.removeChild(nodo.firstChild);
  }

  // Validación del 08 en el celular (RF-11-05): devuelve el mensaje de error o "".
  function validar(resultado, motivo, nota, confirmado, motivosValidos) {
    nota = (nota || "").trim();
    if (resultado === "entregada") return confirmado ? "" : TEXTOS.confirmar;
    if (!motivo || (motivosValidos && motivosValidos.indexOf(motivo) < 0)) return TEXTOS.motivo;
    if (nota.length > NOTA_MAXIMA) return TEXTOS.notaLarga;
    if (motivo === "otro" && !nota) return TEXTOS.notaOtro;
    return "";
  }

  function crearRegistro(entorno, datos) {
    var ahora = entorno.ahora ? entorno.ahora() : new Date();
    var resultado = datos.resultado;
    return {
      operacion_id: datos.operacion_id || nuevoId(entorno),
      intento: Number(datos.intento),
      resultado: resultado,
      motivo: resultado === "no_entregada" ? datos.motivo : "",
      nota: resultado === "no_entregada" ? (datos.nota || "").trim() : "",
      registrado_en: ahora.toISOString(),
      fecha_local: entorno.almacen.fechaLocal(ahora),
      cuenta: Number(datos.cuenta),
    };
  }

  /* ---------------------------------------------------------------------------------------------------------
     Controlador. `entorno`: documento, raiz (la barra de estado), almacen, sincronizador, fetch, navegador,
     ventana, ahora(), uuid(), recargar(), ir(url), confirmar(texto). Las pruebas de Node pasan dobles de todo.
  --------------------------------------------------------------------------------------------------------- */
  function crear(entorno) {
    var documento = entorno.documento;
    var raiz = entorno.raiz;
    var almacen = entorno.almacen;
    var modo = documento.querySelector("[data-sin-conexion]") ? "sin_conexion" : "en_linea";
    var cuenta = raiz.getAttribute("data-cuenta") || "";
    var paquete = null;
    var ultimoEnvio = "";
    var abierto = null;  // {intento, resultado} del formulario abierto en la vista sin conexión

    function parte(nombre) { return raiz.querySelector("[data-" + nombre + "]"); }

    function enLinea() {
      return !(entorno.navegador && entorno.navegador.onLine === false);
    }

    function decir(nombre, texto) {
      var nodo = parte(nombre);
      if (!nodo) return;
      nodo.textContent = texto || "";
      nodo.hidden = !texto;
    }

    // `lista: false` solo actualiza la barra de estado: así el reintento periódico no borra un formulario a medio
    // llenar en la vista sin conexión.
    async function refrescar(opciones) {
      var conLista = !(opciones && opciones.lista === false);
      var pendientes = cuenta ? await almacen.pendientes(cuenta) : [];
      var rechazados = cuenta ? await almacen.rechazados(cuenta) : [];
      decir("estado-conexion", modo === "sin_conexion" || !enLinea() ? TEXTOS.sinConexion : TEXTOS.conectado);
      if (paquete) {
        var visitas = paquete.datos.paradas.length;
        decir("estado-guardada", "Ruta guardada en este celular a las " + horaCorta(paquete.guardado_en) + " · " +
          plural(visitas, "visita", "visitas"));
      } else {
        decir("estado-guardada", modo === "sin_conexion" ? TEXTOS.sinPaquete : "");
      }
      decir("estado-pendientes", pendientes.length ? plural(pendientes.length, "registro por enviar", "registros por enviar")
        : TEXTOS.sinPendientes);
      decir("estado-envio", ultimoEnvio);
      var boton = parte("sincronizar");
      if (boton) boton.hidden = !pendientes.length;
      dibujarRechazados(rechazados);
      if (modo === "sin_conexion") { if (conLista) dibujarVista(pendientes); }
      else marcarTarjetas(pendientes);
      return { pendientes: pendientes, rechazados: rechazados };
    }

    function dibujarRechazados(rechazados) {
      var seccion = parte("rechazados");
      var lista = parte("lista-rechazados");
      if (!seccion || !lista) return;
      vaciar(lista);
      seccion.hidden = !rechazados.length;
      rechazados.forEach(function (registro) {
        var nombre = nombreDe(registro.intento);
        var boton = el(documento, "button", { class: "boton boton-secundario", type: "button", "data-entendido": registro.operacion_id },
          ["Entendido", el(documento, "span", { class: "sr-only" }, [nombre ? ": " + nombre : ""])]);
        boton.addEventListener("click", function () { entendido(registro.operacion_id); });
        lista.appendChild(el(documento, "li", { "data-rechazado": registro.operacion_id }, [
          el(documento, "div", {}, [
            el(documento, "strong", {}, [(registro.resultado === "entregada" ? "Entregada" : "No entregada") +
              (nombre ? " · " + nombre : "") + " · " + horaCorta(registro.registrado_en)]),
            el(documento, "span", { class: "dato-secundario" }, [registro.mensaje || ""]),
          ]),
          boton,
        ]));
      });
    }

    async function entendido(operacionId) {
      await almacen.quitarRegistro(operacionId);
      ultimoEnvio = "";
      await refrescar();
      var siguiente = raiz.querySelector("[data-entendido]") || parte("estado-lista");
      if (siguiente && siguiente.focus) siguiente.focus();
    }

    function nombreDe(intento) {
      if (!paquete) return "";
      var parada = paquete.datos.paradas.filter(function (p) { return String(p.intento) === String(intento); })[0];
      return parada ? parada.nombre : "";
    }

    // «Mis entregas» con señal: marca las tarjetas que tienen un registro en la cola.
    function marcarTarjetas(pendientes) {
      var porIntento = {};
      pendientes.forEach(function (r) { porIntento[String(r.intento)] = r; });
      documento.querySelectorAll("[data-marca-sin-conexion]").forEach(function (marca) {
        if (marca.parentNode) marca.parentNode.removeChild(marca);
      });
      Object.keys(porIntento).forEach(function (intento) {
        var tarjeta = documento.getElementById("parada-" + intento);
        if (!tarjeta) return;
        var marca = el(documento, "p", { class: "etiqueta-ruta sin-conexion-marca", "data-marca-sin-conexion": true },
          [TEXTOS.porEnviar + " · " + horaCorta(porIntento[intento].registrado_en)]);
        var resumen = tarjeta.querySelector(".visita-resumen") || tarjeta;
        resumen.appendChild(marca);
      });
    }

    /* Vista sin conexión ---------------------------------------------------------------------------------- */

    function dato(titulo, contenido) {
      return el(documento, "div", {}, [el(documento, "dt", {}, [titulo]), el(documento, "dd", {}, [contenido])]);
    }

    function formulario(parada, resultado) {
      var id = "registro-" + resultado + "-" + parada.intento;
      var error = el(documento, "p", { class: "message message-error", role: "alert", "data-error": true, hidden: true }, []);
      var campos = [];
      if (resultado === "entregada") {
        campos.push(el(documento, "div", { class: "campo campo-casilla" }, [
          el(documento, "input", { type: "checkbox", id: id + "-confirmar", name: "confirmar", "data-confirmar": true }, []),
          el(documento, "label", { for: id + "-confirmar" }, ["Entregué las recetas al paciente o a su cuidador"]),
        ]));
      } else {
        var opciones = [el(documento, "option", { value: "" }, ["Elige el motivo"])].concat(
          paquete.datos.motivos.map(function (m) { return el(documento, "option", { value: m[0] }, [m[1]]); }));
        campos.push(el(documento, "div", { class: "campo" }, [
          el(documento, "label", { for: id + "-motivo" }, ["Motivo"]),
          el(documento, "select", { id: id + "-motivo", name: "motivo", "data-motivo": true }, opciones),
        ]));
        campos.push(el(documento, "div", { class: "campo" }, [
          el(documento, "label", { for: id + "-nota" }, ["Nota"]),
          el(documento, "textarea", { id: id + "-nota", name: "nota", rows: "3", maxlength: String(NOTA_MAXIMA),
            "aria-describedby": id + "-ayuda", "data-nota": true }, []),
          el(documento, "p", { class: "campo-ayuda", id: id + "-ayuda" }, ["Obligatoria con el motivo «Otro». Hasta 200 caracteres."]),
        ]));
      }
      var guardar = el(documento, "button", { class: "boton", type: "submit" }, ["Guardar registro"]);
      var cancelar = el(documento, "button", { class: "boton boton-secundario", type: "button", "data-cancelar": true }, ["Cancelar"]);
      var form = el(documento, "form", { class: "panel sin-conexion-form", id: id, "data-formulario": resultado, novalidate: true,
        "aria-label": (resultado === "entregada" ? "Registrar entregada: " : "Registrar no entregada: ") + parada.nombre },
        [error].concat(campos).concat([el(documento, "div", { class: "acciones" }, [guardar, cancelar])]));
      form.addEventListener("submit", function (evento) {
        evento.preventDefault();
        guardarDesdeVista(parada, resultado, form);
      });
      cancelar.addEventListener("click", function () {
        abierto = null;
        refrescar().then(function () { enfocar("[data-abrir=\"" + resultado + "\"][data-intento=\"" + parada.intento + "\"]"); });
      });
      return form;
    }

    function enfocar(selector) {
      var nodo = documento.querySelector(selector);
      if (nodo && nodo.focus) nodo.focus();
    }

    function tarjeta(parada, pendiente) {
      var rotulos = el(documento, "p", { class: "parada-rotulos" }, [
        parada.numero ? el(documento, "span", { class: "parada-numero" }, ["Parada " + parada.numero]) : null,
        parada.seccion === "sin_coordenadas" ? el(documento, "span", { class: "etiqueta-ruta" }, ["Sin coordenadas"]) : null,
        parada.traslado_iniciado ? el(documento, "span", { class: "etiqueta-ruta" }, ["Traslado iniciado"]) : null,
      ]);
      var telefono = parada.telefono
        ? el(documento, "a", { href: "tel:" + parada.telefono.replace(/\s+/g, "") }, [parada.telefono])
        : documento.createTextNode("No registrado");
      var lugar = [parada.sector ? "Sector " + parada.sector : "Sin sector", parada.localidad].filter(Boolean).join(" · ");
      var datos = el(documento, "dl", { class: "visita-datos" }, [
        dato("Dirección", parada.direccion || "Sin dirección registrada"),
        parada.referencias ? dato("Referencias", parada.referencias) : null,
        dato("Sector y localidad", lugar),
        dato("Teléfono", telefono),
        dato("Recetas", plural(parada.recetas, "receta", "recetas")),
      ]);
      var tituloId = "sin-conexion-visita-" + parada.intento;
      var hijos = [rotulos,
        parada.atrasada ? el(documento, "p", { class: "visita-aviso" }, ["Atrasada desde el " + fechaCorta(parada.fecha_programada)]) : null,
        el(documento, "h3", { id: tituloId }, [parada.nombre]), datos];
      if (pendiente) {
        var deshacer = el(documento, "button", { class: "boton boton-secundario", type: "button", "data-deshacer": pendiente.operacion_id },
          ["Deshacer", el(documento, "span", { class: "sr-only" }, [": " + parada.nombre])]);
        deshacer.addEventListener("click", function () { deshacerRegistro(pendiente.operacion_id, parada.intento); });
        hijos.push(el(documento, "p", { class: "etiqueta-ruta sin-conexion-marca", "data-marca-sin-conexion": true }, [
          TEXTOS.porEnviar + " · " + (pendiente.resultado === "entregada" ? "Entregada" : "No entregada") + " · " +
          horaCorta(pendiente.registrado_en)]));
        hijos.push(el(documento, "div", { class: "acciones visita-acciones" }, [deshacer]));
      } else {
        var acciones = el(documento, "div", { class: "acciones visita-acciones" }, ["entregada", "no_entregada"].map(function (resultado) {
          var abiertoAqui = abierto && abierto.intento === parada.intento && abierto.resultado === resultado;
          var boton = el(documento, "button", {
            class: resultado === "entregada" ? "boton" : "boton boton-secundario", type: "button",
            "aria-expanded": abiertoAqui ? "true" : "false", "aria-controls": "registro-" + resultado + "-" + parada.intento,
            "data-abrir": resultado, "data-intento": parada.intento,
          }, [resultado === "entregada" ? "Entregada" : "No entregada", el(documento, "span", { class: "sr-only" }, [": " + parada.nombre])]);
          boton.addEventListener("click", function () {
            abierto = abiertoAqui ? null : { intento: parada.intento, resultado: resultado };
            refrescar().then(function () {
              enfocar(abierto ? "#registro-" + resultado + "-" + parada.intento + " [data-confirmar], #registro-" + resultado + "-" +
                parada.intento + " [data-motivo]" : "[data-abrir=\"" + resultado + "\"][data-intento=\"" + parada.intento + "\"]");
            });
          });
          return boton;
        }));
        hijos.push(acciones);
        if (abierto && abierto.intento === parada.intento) hijos.push(formulario(parada, abierto.resultado));
      }
      return el(documento, "li", { class: "visita" + (parada.atrasada ? " visita-atrasada" : ""), id: "parada-" + parada.intento,
        "data-intento": parada.intento, "aria-labelledby": tituloId }, hijos);
    }

    function dibujarVista(pendientes) {
      var seccion = documento.querySelector("[data-paradas]");
      var lista = documento.querySelector("[data-lista-paradas]");
      var aviso = documento.querySelector("[data-sin-paquete]");
      if (aviso) aviso.hidden = Boolean(paquete);
      if (!seccion || !lista) return;
      vaciar(lista);
      seccion.hidden = !paquete;
      if (!paquete) return;
      var porIntento = {};
      pendientes.forEach(function (r) { porIntento[String(r.intento)] = r; });
      var cantidad = documento.querySelector("[data-cantidad]");
      if (cantidad) cantidad.textContent = String(paquete.datos.paradas.length);
      paquete.datos.paradas.forEach(function (parada) {
        lista.appendChild(tarjeta(parada, porIntento[String(parada.intento)]));
      });
    }

    async function guardarDesdeVista(parada, resultado, form) {
      var motivo = form.querySelector("[data-motivo]");
      var nota = form.querySelector("[data-nota]");
      var confirmar = form.querySelector("[data-confirmar]");
      var datos = {
        intento: parada.intento, resultado: resultado, cuenta: cuenta,
        motivo: motivo ? motivo.value : "", nota: nota ? nota.value : "", confirmado: confirmar ? confirmar.checked : false,
      };
      var motivos = paquete.datos.motivos.map(function (m) { return m[0]; });
      var problema = validar(resultado, datos.motivo, datos.nota, datos.confirmado, motivos);
      var error = form.querySelector("[data-error]");
      if (problema) {
        error.textContent = problema;
        error.hidden = false;
        return false;
      }
      var guardado = await encolar(datos);
      if (guardado) {
        abierto = null;
        await refrescar();
        enfocar("[data-deshacer=\"" + guardado.operacion_id + "\"]");
      } else {
        error.textContent = TEXTOS.duplicado;
        error.hidden = false;
      }
      return Boolean(guardado);
    }

    async function deshacerRegistro(operacionId, intento) {
      await almacen.quitarRegistro(operacionId);
      ultimoEnvio = TEXTOS.deshecho;
      await refrescar();
      enfocar("[data-abrir=\"entregada\"][data-intento=\"" + intento + "\"]");
    }

    /* Cola y envío ---------------------------------------------------------------------------------------- */

    async function encolar(datos) {
      var registro = crearRegistro(entorno, datos);
      try {
        await almacen.agregarRegistro(registro);
      } catch (error) {
        if (error && error.codigo === "duplicado") return null;
        throw error;
      }
      ultimoEnvio = TEXTOS.guardado;
      if (entorno.registrarSync) entorno.registrarSync();
      return registro;
    }

    async function sincronizar() {
      if (!cuenta) return null;
      var pendientes = await almacen.pendientes(cuenta);
      if (!pendientes.length) return null;
      ultimoEnvio = TEXTOS.enviando;
      decir("estado-envio", ultimoEnvio);
      var resultado = await entorno.sincronizador.enviar();
      ultimoEnvio = textoDelEnvio(resultado);
      var cambio = resultado.aplicados || resultado.rechazados;
      if (resultado.aplicados && modo === "sin_conexion" && !abierto) await descargarPaquete();
      if (resultado.aplicados && modo === "en_linea") {
        // La lista del servidor se dibujó antes del envío: se ofrece actualizarla, sin recargar por sorpresa.
        await descargarPaquete();
        var actualizar = parte("actualizar");
        if (actualizar) actualizar.hidden = false;
        ultimoEnvio += " " + TEXTOS.paraVer;
      }
      await refrescar({ lista: Boolean(cambio) && !abierto });
      return resultado;
    }

    function textoDelEnvio(resultado) {
      var partes = [];
      if (resultado.aplicados) partes.push("Se " + (resultado.aplicados === 1 ? "envió 1 registro" : "enviaron " + resultado.aplicados + " registros") + ".");
      if (resultado.rechazados) partes.push(plural(resultado.rechazados, "registro no se pudo aplicar", "registros no se pudieron aplicar") + ": revisa «No se pudo enviar».");
      if (resultado.estado === "sin_red") partes.push(TEXTOS.sinRed);
      if (resultado.estado === "sesion") partes.push(TEXTOS.sesion);
      if (resultado.estado === "servidor") partes.push(TEXTOS.servidor);
      if (resultado.estado === "limite") partes.push(TEXTOS.limite);
      return partes.join(" ");
    }

    /* Paquete --------------------------------------------------------------------------------------------- */

    async function descargarPaquete() {
      var url = raiz.getAttribute("data-paquete-url");
      try {
        var respuesta = await entorno.fetch(url, { credentials: "same-origin", redirect: "manual", cache: "no-store",
          headers: { Accept: "application/json" } });
        if (!respuesta.ok) return false;
        var datos = await respuesta.json();
        if (!datos || String(datos.cuenta) !== String(cuenta) || !Array.isArray(datos.paradas)) return false;
        await almacen.guardarPaquete(datos);
        paquete = await almacen.leerPaquete(cuenta);
        return Boolean(paquete);
      } catch (error) {
        return false;
      }
    }

    function guardarPaginaSinConexion() {
      var navegador = entorno.navegador;
      var url = raiz.getAttribute("data-sin-conexion-url");
      try {
        if (!navegador || !navegador.serviceWorker || !navegador.serviceWorker.ready || !url) return;
        navegador.serviceWorker.ready.then(function (registro) {
          if (registro && registro.active) registro.active.postMessage({ tipo: "guardar-sin-conexion", url: url });
        }).catch(function () {});
      } catch (error) { /* sin service worker: la vista sin conexión no estará disponible */ }
    }

    /* «Registrar visita» con señal (RF-11-16) ------------------------------------------------------------- */

    function interceptarFormularios() {
      documento.querySelectorAll("form[data-registro-sin-conexion]").forEach(function (form) {
        form.addEventListener("submit", function (evento) {
          evento.preventDefault();
          enviarFormulario(form);
        });
      });
    }

    function datosDelFormulario(form) {
      function valor(nombre) {
        var campo = form.querySelector("[name=\"" + nombre + "\"]");
        return campo ? campo.value : "";
      }
      var confirmar = form.querySelector("[name=\"confirmar\"]");
      return {
        operacion_id: valor("operacion_id"), intento: form.getAttribute("data-intento"), cuenta: cuenta,
        resultado: form.getAttribute("data-registro-sin-conexion"), motivo: valor("motivo"), nota: valor("nota"),
        confirmado: Boolean(confirmar && confirmar.checked),
      };
    }

    async function guardarDesdeFormulario(form) {
      var datos = datosDelFormulario(form);
      var aviso = form.querySelector("[data-aviso-sin-conexion]");
      var motivos = Array.prototype.map.call(form.querySelectorAll("[name=\"motivo\"] option"), function (o) { return o.value; })
        .filter(Boolean);
      var problema = validar(datos.resultado, datos.motivo, datos.nota, datos.confirmado, motivos.length ? motivos : null);
      if (problema) {
        if (aviso) { aviso.textContent = problema; aviso.hidden = false; aviso.className = "message message-error"; }
        return "invalido";
      }
      var registro = await encolar(datos);
      if (aviso) {
        aviso.textContent = registro ? TEXTOS.porEnviar + ". " + TEXTOS.guardado : TEXTOS.duplicado;
        aviso.className = "message " + (registro ? "message-success" : "message-warning");
        aviso.hidden = false;
      }
      documento.querySelectorAll("form[data-registro-sin-conexion] button[type=\"submit\"]").forEach(function (b) {
        b.setAttribute("disabled", "");
      });
      await refrescar();
      return registro ? "en_cola" : "duplicado";
    }

    async function enviarFormulario(form) {
      if (!enLinea()) return guardarDesdeFormulario(form);
      var respuesta;
      try {
        respuesta = await entorno.fetch(form.getAttribute("action"), {
          method: "POST", body: entorno.formData(form), credentials: "same-origin", redirect: "manual",
        });
      } catch (error) {
        return guardarDesdeFormulario(form);  // el envío falló por la red
      }
      if (respuesta.type === "opaqueredirect" || (respuesta.status >= 300 && respuesta.status < 400)) {
        entorno.ir(raiz.getAttribute("data-mis-url") || "/");  // registrado: la página siguiente trae el mensaje
        return "enviado";
      }
      // Con errores (400): se vuelve a enviar normal para mostrar la página del servidor. Es seguro: la operación
      // es la misma y el servidor no aplicó nada.
      entorno.enviarNormal(form);
      return "servidor";
    }

    /* Arranque -------------------------------------------------------------------------------------------- */

    async function iniciar() {
      raiz.hidden = false;
      if (modo === "sin_conexion") {
        cuenta = String((await almacen.leerMeta("cuenta_activa")) || "");
        paquete = await almacen.leerPaquete(cuenta);
        var ruta = /\/intentos\/(\d+)\//.exec((entorno.ventana && entorno.ventana.location && entorno.ventana.location.pathname) || "");
        var elegido = /resultado=(entregada|no_entregada)/.exec((entorno.ventana && entorno.ventana.location && entorno.ventana.location.search) || "");
        if (ruta && paquete && paquete.datos.paradas.some(function (p) { return String(p.intento) === ruta[1]; })) {
          abierto = { intento: Number(ruta[1]), resultado: elegido ? elegido[1] : "entregada" };
        }
      } else {
        var token = documento.querySelector("input[name=\"csrfmiddlewaretoken\"]");
        await almacen.guardarMeta("cuenta_activa", cuenta);
        if (token && token.value) await almacen.guardarMeta("csrf", token.value);
        await almacen.limpiarPaquetes(cuenta);
        await almacen.purgarCola();
        paquete = await almacen.leerPaquete(cuenta);
        if (raiz.hasAttribute("data-descargar")) {
          var ok = await descargarPaquete();
          if (ok) guardarPaginaSinConexion();
          else if (!paquete) ultimoEnvio = TEXTOS.noSeGuardo;
        }
        interceptarFormularios();
      }
      var boton = parte("sincronizar");
      if (boton) boton.addEventListener("click", function () { sincronizar(); });
      var actualizar = parte("actualizar");
      if (actualizar) actualizar.addEventListener("click", function () { if (entorno.recargar) entorno.recargar(); });
      await refrescar();
      await sincronizar();
      return controlador;
    }

    var controlador = {
      iniciar: iniciar, refrescar: refrescar, sincronizar: sincronizar, encolar: encolar,
      enviarFormulario: enviarFormulario, guardarDesdeVista: guardarDesdeVista, descargarPaquete: descargarPaquete,
      get modo() { return modo; }, get paquete() { return paquete; }, get cuenta() { return cuenta; },
    };
    return controlador;
  }

  // Reintento cada 30 s mientras queden registros y envío al volver la señal (RF-11-06).
  function programar(controlador, ventana, intervaloMs) {
    if (!ventana) return null;
    if (ventana.addEventListener) {
      ventana.addEventListener("online", function () {
        controlador.refrescar({ lista: false }).then(function () { return controlador.sincronizar(); });
      });
      ventana.addEventListener("offline", function () { controlador.refrescar({ lista: false }); });
    }
    return ventana.setInterval ? ventana.setInterval(function () { controlador.sincronizar(); }, intervaloMs) : null;
  }

  function arrancar() {
    var documento = global.document;
    var raiz = documento && documento.querySelector("[data-reparto-estado]");
    if (!raiz || !global.EntregasAlmacen || !global.EntregasSincronizar) return null;
    var almacen = global.EntregasAlmacen.delNavegador();
    var cuentaDeLaPagina = raiz.getAttribute("data-cuenta") || "";
    var sincronizador = global.EntregasSincronizar.crearSincronizador({
      almacen: almacen,
      url: raiz.getAttribute("data-sincronizar-url"),
      fetch: global.fetch.bind(global),
      obtenerCuenta: function () { return cuentaDeLaPagina || almacen.leerMeta("cuenta_activa"); },
      obtenerToken: function () {
        var campo = documento.querySelector("input[name=\"csrfmiddlewaretoken\"]");
        return campo && campo.value ? campo.value : almacen.leerMeta("csrf");
      },
    });
    var controlador = crear({
      documento: documento, raiz: raiz, almacen: almacen, sincronizador: sincronizador,
      fetch: global.fetch.bind(global), navegador: global.navigator, ventana: global,
      formData: function (form) { return new global.FormData(form); },
      ir: function (url) { global.location.assign(url); },
      recargar: function () { global.location.reload(); },
      enviarNormal: function (form) { global.HTMLFormElement.prototype.submit.call(form); },
      registrarSync: function () { return global.EntregasSincronizar.registrarSync(global.navigator); },
    });
    controlador.iniciar().then(function () {
      programar(controlador, global, global.EntregasSincronizar.INTERVALO_MS);
    });
    return controlador;
  }

  var api = { crear: crear, programar: programar, validar: validar, crearRegistro: crearRegistro, horaCorta: horaCorta, TEXTOS: TEXTOS };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.EntregasSinConexion = api;
    arrancar();
  }
})(typeof self !== "undefined" ? self : this);
