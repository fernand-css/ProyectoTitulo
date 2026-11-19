/*
  Base del navegador del reparto sin conexión (spec 11, RF-11-03, RF-11-05 y RF-11-14).

  - Solo IndexedDB del origen de la app; nunca localStorage ni la caché del service worker para datos personales.
  - Tres almacenes: `paquete` (uno por cuenta, se reemplaza en cada descarga), `cola` (registros por enviar y
    rechazados, con clave `operacion_id`) y `meta` (cuenta activa y token CSRF de la sesión, para enviar desde el
    service worker con Background Sync).
  - El paquete vale solo para su cuenta y para la fecha de hoy en el celular; si no, se borra.
  - La cola se conserva al salir, ligada a su cuenta; un registro con más de 2 días se borra (el servidor lo
    rechazaría con `fuera_de_plazo`).
  Se usa en la página, en pwa.js y en el service worker (importScripts). En Node, `crearAlmacen(memoria())`.
*/
(function (global) {
  "use strict";

  var NOMBRE = "cesfam-reparto";
  var VERSION = 1;
  var PLAZO_DIAS = 2;
  var ALMACENES = { paquete: "cuenta", cola: "operacion_id", meta: "clave" };

  function copia(valor) {
    return valor === undefined ? undefined : JSON.parse(JSON.stringify(valor));
  }

  // Adaptador en memoria (pruebas y navegadores sin IndexedDB: los datos duran lo que dura la página).
  function memoria() {
    var datos = { paquete: new Map(), cola: new Map(), meta: new Map() };
    return {
      leer: function (almacen, clave) { return Promise.resolve(copia(datos[almacen].get(String(clave)))); },
      todos: function (almacen) { return Promise.resolve(Array.from(datos[almacen].values()).map(copia)); },
      poner: function (almacen, valor) {
        datos[almacen].set(String(valor[ALMACENES[almacen]]), copia(valor));
        return Promise.resolve();
      },
      borrar: function (almacen, clave) { datos[almacen].delete(String(clave)); return Promise.resolve(); },
      datos: datos,
    };
  }

  function promesa(solicitud) {
    return new Promise(function (resolver, rechazar) {
      solicitud.onsuccess = function () { resolver(solicitud.result); };
      solicitud.onerror = function () { rechazar(solicitud.error); };
    });
  }

  function indexedDb(fabrica) {
    var abierta = null;
    function abrir() {
      if (!abierta) {
        abierta = new Promise(function (resolver, rechazar) {
          var solicitud = fabrica.open(NOMBRE, VERSION);
          solicitud.onupgradeneeded = function () {
            var base = solicitud.result;
            Object.keys(ALMACENES).forEach(function (nombre) {
              if (!base.objectStoreNames.contains(nombre)) base.createObjectStore(nombre, { keyPath: ALMACENES[nombre] });
            });
          };
          solicitud.onsuccess = function () { resolver(solicitud.result); };
          solicitud.onerror = function () { abierta = null; rechazar(solicitud.error); };
        });
      }
      return abierta;
    }
    function operar(almacen, modo, accion) {
      return abrir().then(function (base) {
        return promesa(accion(base.transaction(almacen, modo).objectStore(almacen)));
      });
    }
    // Las claves se guardan como texto, igual que en memoria.
    return {
      leer: function (almacen, clave) { return operar(almacen, "readonly", function (s) { return s.get(String(clave)); }); },
      todos: function (almacen) { return operar(almacen, "readonly", function (s) { return s.getAll(); }); },
      poner: function (almacen, valor) {
        var guardado = copia(valor);
        guardado[ALMACENES[almacen]] = String(guardado[ALMACENES[almacen]]);
        return operar(almacen, "readwrite", function (s) { return s.put(guardado); });
      },
      borrar: function (almacen, clave) { return operar(almacen, "readwrite", function (s) { return s.delete(String(clave)); }); },
    };
  }

  // Fecha local del celular en AAAA-MM-DD (la del paquete y la del registro).
  function fechaLocal(fecha) {
    var d = fecha || new Date();
    function dos(n) { return (n < 10 ? "0" : "") + n; }
    return d.getFullYear() + "-" + dos(d.getMonth() + 1) + "-" + dos(d.getDate());
  }

  function diasEntre(desde, hasta) {
    var a = desde.split("-").map(Number);
    var b = hasta.split("-").map(Number);
    return Math.round((Date.UTC(b[0], b[1] - 1, b[2]) - Date.UTC(a[0], a[1] - 1, a[2])) / 86400000);
  }

  function crearAlmacen(adaptador, opciones) {
    var reloj = (opciones && opciones.ahora) || function () { return new Date(); };

    function hoy() { return fechaLocal(reloj()); }

    var api = {
      fechaLocal: fechaLocal,

      // Paquete ---------------------------------------------------------------------------------------------
      guardarPaquete: function (paquete) {
        return adaptador.poner("paquete", {
          cuenta: String(paquete.cuenta), fecha: paquete.fecha, guardado_en: reloj().toISOString(), datos: paquete,
        });
      },
      // Paquete vigente de la cuenta: de hoy en el celular. Uno de otro día se borra (RF-11-03).
      leerPaquete: function (cuenta) {
        if (cuenta === null || cuenta === undefined || cuenta === "") return Promise.resolve(null);
        return adaptador.leer("paquete", cuenta).then(function (guardado) {
          if (!guardado) return null;
          if (guardado.fecha !== hoy()) return adaptador.borrar("paquete", cuenta).then(function () { return null; });
          return guardado;
        });
      },
      borrarPaquete: function (cuenta) { return adaptador.borrar("paquete", cuenta); },
      // Borra los paquetes de otras cuentas y los que no son de hoy.
      limpiarPaquetes: function (cuentaActual) {
        var dia = hoy();
        return adaptador.todos("paquete").then(function (todos) {
          return Promise.all(todos.filter(function (p) {
            return p.cuenta !== String(cuentaActual) || p.fecha !== dia;
          }).map(function (p) { return adaptador.borrar("paquete", p.cuenta); }));
        });
      },

      // Cola ------------------------------------------------------------------------------------------------
      registros: function (cuenta) {
        return adaptador.todos("cola").then(function (todos) {
          return todos.filter(function (r) { return cuenta === undefined || String(r.cuenta) === String(cuenta); })
            .sort(function (a, b) { return a.registrado_en < b.registrado_en ? -1 : a.registrado_en > b.registrado_en ? 1 : 0; });
        });
      },
      pendientes: function (cuenta) {
        return api.registros(cuenta).then(function (lista) { return lista.filter(function (r) { return r.estado === "pendiente"; }); });
      },
      rechazados: function (cuenta) {
        return api.registros(cuenta).then(function (lista) { return lista.filter(function (r) { return r.estado === "rechazado"; }); });
      },
      // Un solo registro por intento y cuenta mientras esté en la cola (RF-11-05).
      agregarRegistro: function (registro) {
        return api.pendientes(registro.cuenta).then(function (lista) {
          if (lista.some(function (r) { return String(r.intento) === String(registro.intento); })) {
            var error = new Error("Esta visita ya tiene un registro por enviar.");
            error.codigo = "duplicado";
            throw error;
          }
          return adaptador.poner("cola", Object.assign({}, registro, { estado: "pendiente" }));
        });
      },
      marcarRechazado: function (registro, codigo, mensaje) {
        return adaptador.poner("cola", Object.assign({}, registro, { estado: "rechazado", codigo: codigo, mensaje: mensaje || "" }));
      },
      quitarRegistro: function (operacionId) { return adaptador.borrar("cola", operacionId); },
      // RF-11-14: un registro con más de 2 días ya no se puede aplicar; se borra.
      purgarCola: function () {
        var dia = hoy();
        return adaptador.todos("cola").then(function (todos) {
          return Promise.all(todos.filter(function (r) {
            var fecha = r.fecha_local || fechaLocal(new Date(r.registrado_en));
            return diasEntre(fecha, dia) > PLAZO_DIAS;
          }).map(function (r) { return adaptador.borrar("cola", r.operacion_id); }));
        });
      },

      // Meta ------------------------------------------------------------------------------------------------
      leerMeta: function (clave) {
        return adaptador.leer("meta", clave).then(function (fila) { return fila ? fila.valor : null; });
      },
      guardarMeta: function (clave, valor) {
        if (valor === null || valor === undefined || valor === "") return adaptador.borrar("meta", clave);
        return adaptador.poner("meta", { clave: clave, valor: valor });
      },
    };
    return api;
  }

  // Almacén del navegador (IndexedDB) o, si no existe, en memoria.
  var compartido = null;
  function delNavegador() {
    if (!compartido) {
      var fabrica = global.indexedDB;
      compartido = crearAlmacen(fabrica ? indexedDb(fabrica) : memoria());
    }
    return compartido;
  }

  var api = { crearAlmacen: crearAlmacen, memoria: memoria, delNavegador: delNavegador, fechaLocal: fechaLocal, PLAZO_DIAS: PLAZO_DIAS };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.EntregasAlmacen = api;
  }
})(typeof self !== "undefined" ? self : this);
