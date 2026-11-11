const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const test = require("node:test");

const codigo = fs.readFileSync(path.join(__dirname, "../../static/js/entregas/ubicacion.js"), "utf8");

// Ejecuta el script con un DOM y una geolocalización simulados y devuelve el componente de Alpine ya iniciado.
function preparar({ seguro = true, geolocalizacion } = {}) {
  let alIniciar;
  let fabrica;
  const campos = { latitud: { value: "" }, longitud: { value: "" }, precision_metros: { value: "" } };
  const formulario = {
    querySelector(selector) {
      const nombre = /name="([^"]+)"/.exec(selector)[1];
      return campos[nombre];
    },
  };
  const contexto = {
    document: { addEventListener(evento, funcion) { if (evento === "alpine:init") alIniciar = funcion; } },
    Alpine: { data(nombre, funcion) { if (nombre === "ubicacion") fabrica = funcion; } },
    window: { isSecureContext: seguro },
    navigator: geolocalizacion ? { geolocation: geolocalizacion } : {},
  };
  vm.runInNewContext(codigo, contexto);
  alIniciar();
  const componente = fabrica();
  componente.$root = { closest: () => formulario };
  componente.init();
  return { componente, campos };
}

test("rellena latitud, longitud y precisión y lo anuncia con texto", () => {
  let opciones;
  const { componente, campos } = preparar({
    geolocalizacion: {
      getCurrentPosition(exito, _error, configuracion) {
        opciones = configuracion;
        exito({ coords: { latitude: -36.51234567, longitude: -72.2112349, accuracy: 7.6 } });
      },
    },
  });
  assert.equal(componente.estado, "");
  componente.usar();
  assert.deepEqual([campos.latitud.value, campos.longitud.value, campos.precision_metros.value], ["-36.512346", "-72.211235", "8"]);
  assert.match(componente.estado, /Ubicación lista: -36\.512346, -72\.211235 \(±8 m\)/);
  assert.equal(componente.ocupado, false);
  assert.equal(opciones.enableHighAccuracy, true);
});

test("sin permiso explica que se escriban las coordenadas a mano y no toca los campos", () => {
  const { componente, campos } = preparar({
    geolocalizacion: { getCurrentPosition(_exito, error) { error({ code: 1 }); } },
  });
  componente.usar();
  assert.match(componente.estado, /No diste permiso/);
  assert.match(componente.estado, /a mano/);
  assert.equal(campos.latitud.value, "");
  assert.equal(componente.ocupado, false);
});

test("sin señal o con tiempo agotado ofrece reintentar o escribirlas a mano", () => {
  const { componente } = preparar({
    geolocalizacion: { getCurrentPosition(_exito, error) { error({ code: 3 }); } },
  });
  componente.usar();
  assert.match(componente.estado, /No pudimos obtener la ubicación/);
});

test("sin contexto seguro no pide la ubicación y lo dice desde el inicio", () => {
  let pedida = false;
  const { componente } = preparar({
    seguro: false,
    geolocalizacion: { getCurrentPosition() { pedida = true; } },
  });
  assert.match(componente.estado, /conexión segura \(HTTPS\)/);
  componente.usar();
  assert.equal(pedida, false);
  assert.match(componente.estado, /a mano/);
});

test("sin geolocalización en el navegador se comporta como sin contexto seguro", () => {
  const { componente } = preparar({ seguro: true });
  assert.equal(componente.disponible, false);
  assert.match(componente.estado, /a mano/);
});
