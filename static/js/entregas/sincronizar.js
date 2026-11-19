/*
  Envío de los registros hechos sin conexión (spec 11, RF-11-06, RF-11-07, RF-11-10 y RF-11-11).

  - Lo usan la página (sin_conexion.js) y el service worker (importScripts, evento `sync`): la misma función.
  - Envía solo los registros de la cuenta activa, en lotes de hasta 50, con el token CSRF por cabecera y sin seguir
    redirecciones (una redirección es la sesión vencida: el registro se queda en la cola).
  - Por cada registro, el servidor responde `aplicado`, `ya_aplicado`, `rechazado` (con código) o `reintentar`.
    Los dos primeros salen de la cola; el rechazado queda en «No se pudo enviar» hasta «Entendido»; el resto, y
    cualquier error de red, del servidor o de sesión, se queda para el siguiente intento.
  - Enviar dos veces el mismo registro (dos pestañas, la página y Background Sync) es seguro: el servidor lo
    reconoce por su `operacion_id` y responde `ya_aplicado`.
*/
(function (global) {
  "use strict";

  var LOTE = 50;
  var INTERVALO_MS = 30000;
  var ETIQUETA_SYNC = "cesfam-registros";
  var CAMPOS = ["operacion_id", "intento", "resultado", "motivo", "nota", "registrado_en", "cuenta"];

  // Motivos en palabras si el servidor no los trae (RF-11-10). Los mismos de entregasapp/sin_conexion.py.
  var MENSAJES = {
    otro_usuario: "Este registro se hizo con otra cuenta. Entra con esa cuenta para enviarlo.",
    no_asignada: "Esta visita ya no está asignada a ti.",
    reasignada: "La Q.F. reasignó esta visita antes de que llegara tu registro.",
    anulada: "La Q.F. anuló esta entrega antes de que llegara tu registro.",
    ya_registrada: "Esta visita ya tenía un resultado registrado.",
    hora_invalida: "La hora del registro no es válida. Revisa la fecha y la hora del celular.",
    fuera_de_plazo: "El registro llegó más de 2 días después de hecho y ya no se puede aplicar.",
    invalido: "El registro no es válido. Vuelve a registrar la visita con señal.",
  };

  function paraEnviar(registro) {
    var salida = {};
    CAMPOS.forEach(function (campo) { salida[campo] = registro[campo] === undefined ? "" : registro[campo]; });
    return salida;
  }

  function trozos(lista, tamano) {
    var salida = [];
    for (var i = 0; i < lista.length; i += tamano) salida.push(lista.slice(i, i + tamano));
    return salida;
  }

  /*
    opciones: almacen (almacen.js), url, fetch, obtenerCuenta() y obtenerToken() (pueden devolver promesas).
    enviar() devuelve {estado, aplicados, rechazados, pendientes}; estado: "sin_cuenta", "sin_pendientes",
    "enviado", "sin_red", "sesion", "limite" o "servidor".
  */
  function crearSincronizador(opciones) {
    var enCurso = null;

    async function enviarLote(lote, token) {
      return opciones.fetch(opciones.url, {
        method: "POST",
        credentials: "same-origin",
        redirect: "manual",
        cache: "no-store",
        headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRFToken": token || "" },
        body: JSON.stringify({ registros: lote.map(paraEnviar) }),
      });
    }

    function estadoDeRespuesta(respuesta) {
      if (respuesta.type === "opaqueredirect" || respuesta.status === 0 || (respuesta.status >= 300 && respuesta.status < 400)) return "sesion";
      if (respuesta.status === 401 || respuesta.status === 403) return "sesion";
      if (respuesta.status === 429) return "limite";
      if (!respuesta.ok) return "servidor";
      return null;
    }

    async function aplicar(lote, resultados) {
      var porOperacion = {};
      (resultados || []).forEach(function (r) { if (r && r.operacion_id) porOperacion[r.operacion_id] = r; });
      var cuenta = { aplicados: 0, rechazados: 0 };
      for (var i = 0; i < lote.length; i += 1) {
        var registro = lote[i];
        var resultado = porOperacion[registro.operacion_id];
        if (!resultado) continue;
        if (resultado.estado === "aplicado" || resultado.estado === "ya_aplicado") {
          await opciones.almacen.quitarRegistro(registro.operacion_id);
          cuenta.aplicados += 1;
        } else if (resultado.estado === "rechazado") {
          await opciones.almacen.marcarRechazado(registro, resultado.codigo,
            resultado.mensaje || MENSAJES[resultado.codigo] || MENSAJES.invalido);
          cuenta.rechazados += 1;
        }
      }
      return cuenta;
    }

    async function ejecutar() {
      var cuenta = await opciones.obtenerCuenta();
      if (!cuenta) return { estado: "sin_cuenta", aplicados: 0, rechazados: 0, pendientes: 0 };
      var pendientes = await opciones.almacen.pendientes(cuenta);
      if (!pendientes.length) return { estado: "sin_pendientes", aplicados: 0, rechazados: 0, pendientes: 0 };
      var token = await opciones.obtenerToken();
      var total = { estado: "enviado", aplicados: 0, rechazados: 0 };
      var lotes = trozos(pendientes, LOTE);
      for (var i = 0; i < lotes.length; i += 1) {
        var respuesta;
        try {
          respuesta = await enviarLote(lotes[i], token);
        } catch (error) {
          total.estado = "sin_red";
          break;
        }
        var problema = estadoDeRespuesta(respuesta);
        if (problema) { total.estado = problema; break; }
        var datos;
        try {
          datos = await respuesta.json();
        } catch (error) {
          total.estado = "servidor";
          break;
        }
        var parcial = await aplicar(lotes[i], datos && datos.resultados);
        total.aplicados += parcial.aplicados;
        total.rechazados += parcial.rechazados;
      }
      total.pendientes = (await opciones.almacen.pendientes(cuenta)).length;
      return total;
    }

    return {
      // Un solo envío a la vez en este contexto; quien llame durante un envío recibe ese mismo resultado.
      enviar: function () {
        if (!enCurso) {
          enCurso = ejecutar().finally(function () { enCurso = null; });
        }
        return enCurso;
      },
      enviando: function () { return Boolean(enCurso); },
    };
  }

  // Background Sync donde exista (Chromium); si no, nada: el envío ocurre con la app abierta.
  function registrarSync(navegador) {
    try {
      if (!navegador || !navegador.serviceWorker || !navegador.serviceWorker.ready) return Promise.resolve(false);
      return navegador.serviceWorker.ready.then(function (registro) {
        if (!registro || !registro.sync || !registro.sync.register) return false;
        return registro.sync.register(ETIQUETA_SYNC).then(function () { return true; });
      }).catch(function () { return false; });
    } catch (error) {
      return Promise.resolve(false);
    }
  }

  var api = {
    crearSincronizador: crearSincronizador, registrarSync: registrarSync, paraEnviar: paraEnviar,
    LOTE: LOTE, INTERVALO_MS: INTERVALO_MS, ETIQUETA_SYNC: ETIQUETA_SYNC, MENSAJES: MENSAJES,
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.EntregasSincronizar = api;
  }
})(typeof self !== "undefined" ? self : this);
