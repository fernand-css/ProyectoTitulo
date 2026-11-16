// Pruebas de static/js/entregas/fotos.js (spec 08, RF-08-18): espacios, textos y envío con red simulada.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const ruta = path.join(__dirname, "../../static/js/entregas/fotos.js");
const fotos = require(ruta);

test("los espacios nuevos completan 3 contando las marcadas para borrar", () => {
  assert.equal(fotos.espaciosVisibles(0, 0, 3), 3);
  assert.equal(fotos.espaciosVisibles(2, 0, 3), 1);
  assert.equal(fotos.espaciosVisibles(3, 0, 3), 0); // con 3 y ninguna marcada, solo se borra
  assert.equal(fotos.espaciosVisibles(3, 1, 3), 1); // marcar una libera su espacio en el mismo guardado
  assert.equal(fotos.espaciosVisibles(3, 3, 3), 3);
});

test("la cuenta dice cuántas quedarán o que solo se puede borrar", () => {
  assert.equal(fotos.textoCuenta(3, 0, 0, 3), "Ya hay 3 fotos. Marca una para borrar si quieres agregar otra.");
  assert.equal(fotos.textoCuenta(2, 1, 2, 3), "Al guardar quedarán 3 de 3 fotos.");
  assert.equal(fotos.textoCuenta(0, 0, 1, 3), "Al guardar quedarán 1 de 3 fotos.");
  assert.equal(fotos.textoQuitada(2), "Se quitó la foto nueva 2 para no pasar de 3 fotos.");
  assert.equal(fotos.tamano(2.1 * 1024 * 1024), "2,1 MB");
  assert.equal(fotos.tamano(40 * 1024), "40 KB");
});

function respuesta(status, cuerpo) {
  return { status, json: () => (cuerpo === undefined ? Promise.reject(new Error("sin json")) : Promise.resolve(cuerpo)) };
}

test("guardar envía una sola solicitud con Accept JSON y CSRF, y entiende el éxito", async () => {
  const llamadas = [];
  const resultado = await fotos.guardar({
    fetch: (url, opciones) => { llamadas.push({ url, opciones }); return Promise.resolve(respuesta(200, { ok: true, volver: "/entregas/mis/#parada-4" })); },
    url: "/entregas/domicilios/7/fotos/", cuerpo: "cuerpo", csrf: "token", enLinea: true,
  });
  assert.deepEqual(resultado, { ok: true, volver: "/entregas/mis/#parada-4" });
  assert.equal(llamadas.length, 1);
  assert.equal(llamadas[0].opciones.method, "POST");
  assert.equal(llamadas[0].opciones.headers.Accept, "application/json");
  assert.equal(llamadas[0].opciones.headers["X-CSRFToken"], "token");
  assert.equal(llamadas[0].opciones.credentials, "same-origin");
});

test("el error numerado del servidor se devuelve con su foto para mostrarlo junto a ella", async () => {
  const resultado = await fotos.guardar({
    fetch: () => Promise.resolve(respuesta(400, { ok: false, error: "La foto 2 no se pudo procesar: el archivo no es una foto JPEG o PNG válida.", foto: 2 })),
    url: "/x/", cuerpo: null, enLinea: true,
  });
  assert.deepEqual(resultado, { ok: false, mensaje: "La foto 2 no se pudo procesar: el archivo no es una foto JPEG o PNG válida.", foto: 2 });
});

test("sin conexión no se envía nada y se dice con texto", async () => {
  let llamado = false;
  const desconectado = await fotos.guardar({ fetch: () => { llamado = true; }, url: "/x/", cuerpo: null, enLinea: false });
  assert.equal(llamado, false);
  assert.equal(desconectado.ok, false);
  assert.match(desconectado.mensaje, /No hay conexión\. No se guardó ningún cambio/);
  const corte = await fotos.guardar({ fetch: () => Promise.reject(new TypeError("Failed to fetch")), url: "/x/", cuerpo: null, enLinea: true });
  assert.equal(corte.mensaje, fotos.TEXTOS.sinRed);
});

test("una respuesta sin JSON o un error del servidor da un aviso general sin aplicar cambios", async () => {
  const caida = await fotos.guardar({ fetch: () => Promise.resolve(respuesta(500)), url: "/x/", cuerpo: null, enLinea: true });
  assert.deepEqual(caida, { ok: false, mensaje: fotos.TEXTOS.fallo, foto: null });
  assert.deepEqual(fotos.interpretar(403, { detail: "x" }), { ok: false, mensaje: fotos.TEXTOS.fallo, foto: null });
});

test("no usa la cámara en vivo: «Sacar foto» es un campo de archivo con capture", () => {
  const codigo = fs.readFileSync(ruta, "utf8");
  assert.doesNotMatch(codigo, /getUserMedia/);
  const plantilla = fs.readFileSync(path.join(__dirname, "../../templates/entregas/_fotos_formulario.html"), "utf8");
  assert.match(plantilla, /type="file"[^>]*accept="image\/jpeg,image\/png" capture="environment"/);
});
