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

// Corrección del 2026-11-16: la foto se reduce en el navegador antes de subirla.

// Herramientas simuladas: registran el lienzo y devuelven un JPEG del tamaño pedido.
function herramientas({ ancho = 4000, alto = 3000, bytesSalida = 300 * 1024, falla = false } = {}) {
  const registro = { lienzos: [], dibujos: [], rellenos: [], calidad: null, tipo: null, cerrada: false };
  return {
    registro,
    decodificar() {
      if (falla) return Promise.reject(new Error("formato no soportado"));
      return Promise.resolve({ fuente: "imagen", ancho, alto, cerrar() { registro.cerrada = true; } });
    },
    lienzo(w, h) {
      registro.lienzos.push([w, h]);
      return {
        getContext: () => ({
          set fillStyle(valor) { registro.relleno = valor; },
          fillRect: (...args) => registro.rellenos.push(args),
          drawImage: (...args) => registro.dibujos.push(args),
        }),
        toBlob(listo, tipo, calidad) { registro.tipo = tipo; registro.calidad = calidad; listo({ size: bytesSalida, type: tipo }); },
      };
    },
  };
}

const foto = (nombre, tipo, bytes) => ({ name: nombre, type: tipo, size: bytes });

test("las medidas bajan el lado mayor a 1600 px y respetan la proporción", () => {
  assert.deepEqual(fotos.medidas(4000, 3000, 1600), { ancho: 1600, alto: 1200 });
  assert.deepEqual(fotos.medidas(3000, 4000, 1600), { ancho: 1200, alto: 1600 }); // vertical
  assert.deepEqual(fotos.medidas(1200, 900, 1600), { ancho: 1200, alto: 900 }); // ya cabe
  assert.equal(fotos.nombreJpeg("IMG_2041.HEIC.png"), "IMG_2041.HEIC.jpg");
  assert.equal(fotos.nombreJpeg("porton"), "porton.jpg");
  assert.equal(fotos.textoArchivo(foto("a.jpg", "image/jpeg", 4.8 * 1024 * 1024), { size: 410 * 1024 }),
    "a.jpg · 4,8 MB (se enviará reducida: 0,4 MB)");
});

test("una foto grande del celular se envía como JPEG de 1600 px, más liviana y con otro nombre", async () => {
  const h = herramientas();
  const original = foto("IMG_0001.jpg", "image/jpeg", 6.5 * 1024 * 1024); // sobre el límite de 5 MB del servidor
  const resultado = await fotos.reducir(original, h);
  assert.equal(resultado.reducida, true);
  assert.equal(resultado.archivo.size, 300 * 1024);
  assert.equal(resultado.nombre, "IMG_0001.jpg");
  assert.deepEqual(h.registro.lienzos, [[1600, 1200]]);
  assert.deepEqual(h.registro.dibujos, [["imagen", 0, 0, 1600, 1200]]);
  assert.equal(h.registro.tipo, "image/jpeg");
  assert.equal(h.registro.calidad, fotos.REDUCCION.calidad);
  assert.equal(h.registro.cerrada, true); // libera la imagen decodificada
});

test("un PNG con transparencia queda sobre blanco, como en el servidor", async () => {
  const h = herramientas({ ancho: 2000, alto: 2000 });
  const resultado = await fotos.reducir(foto("croquis.png", "image/png", 3 * 1024 * 1024), h);
  assert.equal(resultado.nombre, "croquis.jpg");
  assert.equal(h.registro.relleno, "#ffffff");
  assert.deepEqual(h.registro.rellenos, [[0, 0, 1600, 1600]]);
});

test("una foto chica, un archivo que no es foto o un fallo del navegador envían la original", async () => {
  const chica = foto("chica.jpg", "image/jpeg", 200 * 1024);
  const sinTocar = herramientas({ ancho: 1200, alto: 900 });
  assert.deepEqual(await fotos.reducir(chica, sinTocar), { archivo: chica, nombre: "chica.jpg", reducida: false });
  assert.deepEqual(sinTocar.registro.lienzos, []);
  const documento = foto("plano.pdf", "application/pdf", 9 * 1024 * 1024);
  assert.equal((await fotos.reducir(documento, herramientas())).archivo, documento); // el servidor da el aviso
  const grande = foto("grande.jpg", "image/jpeg", 6 * 1024 * 1024);
  assert.equal((await fotos.reducir(grande, herramientas({ falla: true }))).archivo, grande);
  assert.equal((await fotos.reducir(grande, null)).archivo, grande); // navegador sin lienzo
  const pesada = foto("ya-comprimida.jpg", "image/jpeg", 250 * 1024);
  const mayor = await fotos.reducir(pesada, herramientas({ ancho: 2400, alto: 1800, bytesSalida: 260 * 1024 }));
  assert.equal(mayor.archivo, pesada); // si la reducida no pesa menos, va la original
});

test("no usa la cámara en vivo: «Sacar foto» es un campo de archivo con capture", () => {
  const codigo = fs.readFileSync(ruta, "utf8");
  assert.doesNotMatch(codigo, /getUserMedia/);
  const plantilla = fs.readFileSync(path.join(__dirname, "../../templates/entregas/_fotos_formulario.html"), "utf8");
  assert.match(plantilla, /type="file"[^>]*accept="image\/jpeg,image\/png" capture="environment"/);
});
