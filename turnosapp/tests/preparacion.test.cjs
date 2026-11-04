const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const test = require("node:test");

const codigo = fs.readFileSync(path.join(__dirname, "../../static/js/preparacion.js"), "utf8");

function preparar({ actualHTML = "antes", nuevoHTML = "despues", fetch } = {}) {
  let intervalo;
  const actual = {
    innerHTML: actualHTML,
    reemplazos: 0,
    replaceWith(nuevo) {
      this.reemplazos += 1;
      this.innerHTML = nuevo.innerHTML;
    },
  };
  const documento = {
    querySelector: () => ({ innerHTML: nuevoHTML }),
  };
  class DOMParser {
    parseFromString() { return documento; }
  }
  const contexto = {
    document: { querySelector: () => actual },
    DOMParser,
    URL,
    fetch,
    window: {
      location: { href: "https://cesfam.test/recetas/preparacion/?vista=activa" },
      setInterval(callback, ms) { intervalo = { callback, ms }; },
    },
  };
  vm.runInNewContext(codigo, contexto);
  return { actual, intervalo };
}

test("consulta el fragmento cada cinco segundos y reemplaza el contenido cambiado", async () => {
  let solicitud;
  const { actual, intervalo } = preparar({
    fetch: async (url, opciones) => {
      solicitud = { url: String(url), opciones };
      return { ok: true, text: async () => "<section>nuevo</section>" };
    },
  });

  assert.equal(intervalo.ms, 5000);
  await intervalo.callback();

  const url = new URL(solicitud.url);
  assert.equal(url.searchParams.get("vista"), "activa");
  assert.equal(url.searchParams.get("fragmento"), "1");
  assert.equal(solicitud.opciones.cache, "no-store");
  assert.equal(solicitud.opciones.credentials, "same-origin");
  assert.equal(actual.innerHTML, "despues");
  assert.equal(actual.reemplazos, 1);
});

test("no reemplaza el fragmento si su contenido no cambió", async () => {
  const { actual, intervalo } = preparar({
    actualHTML: "igual",
    nuevoHTML: "igual",
    fetch: async () => ({ ok: true, text: async () => "<section>igual</section>" }),
  });

  await intervalo.callback();
  assert.equal(actual.reemplazos, 0);
});
