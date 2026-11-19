/*
  Registro del service worker y datos del reparto sin conexión al entrar y al salir (spec 01 y spec 11).

  - Registra el service worker con alcance «/».
  - Con una cuenta con sesión (`data-cuenta`, su identificador interno): la deja como cuenta activa del celular,
    borra la ruta guardada de otra cuenta o de otro día y los registros con más de 2 días (RF-11-03 y RF-11-14).
  - Al pulsar «Cerrar sesión» con registros por enviar, avisa cuántos son y pide confirmación. Al salir borra la
    ruta guardada; la cola se conserva, ligada a la cuenta, y se envía cuando esa cuenta vuelve a entrar.
  Sin almacen.js o sin IndexedDB, solo registra el service worker y la salida funciona como siempre.
*/
(function (global) {
  "use strict";

  function textoSalida(cantidad) {
    return "Tienes " + cantidad + (cantidad === 1 ? " registro sin enviar" : " registros sin enviar") +
      ". Si sales, se enviarán cuando vuelvas a entrar con esta cuenta. ¿Quieres salir?";
  }

  /*
    entorno: documento, almacen (almacen.js), cuenta, salir (URL de salida), confirmar(texto), enviar(form).
  */
  function crear(entorno) {
    var almacen = entorno.almacen;
    var cuenta = entorno.cuenta ? String(entorno.cuenta) : "";

    async function alEntrar() {
      if (!almacen || !cuenta) return false;
      await almacen.guardarMeta("cuenta_activa", cuenta);
      await almacen.limpiarPaquetes(cuenta);
      await almacen.purgarCola();
      return true;
    }

    // Devuelve true si salió (o dejó salir) y false si la persona canceló.
    async function alSalir(form) {
      if (almacen && cuenta) {
        var pendientes = (await almacen.pendientes(cuenta)).length;
        if (pendientes && !entorno.confirmar(textoSalida(pendientes))) return false;
        await almacen.borrarPaquete(cuenta);
        await almacen.guardarMeta("cuenta_activa", null);
        await almacen.guardarMeta("csrf", null);
      }
      entorno.enviar(form);
      return true;
    }

    function vigilarSalida() {
      if (!entorno.salir) return;
      entorno.documento.querySelectorAll("form").forEach(function (form) {
        var accion = form.getAttribute("action") || "";
        if (accion !== entorno.salir) return;
        form.addEventListener("submit", function (evento) {
          evento.preventDefault();
          alSalir(form).catch(function () { entorno.enviar(form); });  // un fallo de la base no impide salir
        });
      });
    }

    return { alEntrar: alEntrar, alSalir: alSalir, vigilarSalida: vigilarSalida };
  }

  function arrancar() {
    var script = global.document.currentScript;
    var serviceWorkerUrl = script.dataset.serviceWorker;
    if ("serviceWorker" in global.navigator) {
      global.addEventListener("load", function () {
        global.navigator.serviceWorker.register(serviceWorkerUrl, { scope: "/" }).catch(function () {
          console.warn("No se pudo registrar la aplicación en este navegador.");
        });
      });
    }
    var almacen = null;
    try {
      almacen = global.EntregasAlmacen ? global.EntregasAlmacen.delNavegador() : null;
    } catch (error) {
      almacen = null;
    }
    var pwa = crear({
      documento: global.document, almacen: almacen, cuenta: script.dataset.cuenta, salir: script.dataset.salir,
      confirmar: function (texto) { return global.confirm(texto); },
      enviar: function (form) { global.HTMLFormElement.prototype.submit.call(form); },
    });
    pwa.alEntrar().catch(function () { /* sin IndexedDB: nada que limpiar */ });
    pwa.vigilarSalida();
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { crear: crear, textoSalida: textoSalida };
  } else {
    arrancar();
  }
})(typeof self !== "undefined" ? self : this);
