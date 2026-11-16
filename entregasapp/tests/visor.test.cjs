// Pruebas de static/js/entregas/visor.js (spec 08, RF-08-19) con un DOM mínimo simulado.
const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const visor = require(path.join(__dirname, "../../static/js/entregas/visor.js"));

// Elemento simulado: atributos, eventos, hijos y `closest` por atributo data o etiqueta.
class Elemento {
  constructor(etiqueta, atributos = {}) {
    this.etiqueta = etiqueta;
    this.atributos = { ...atributos };
    this.oyentes = {};
    this.hijos = [];
    this.parentNode = null;
    this.textContent = "";
  }
  getAttribute(nombre) { return nombre in this.atributos ? this.atributos[nombre] : null; }
  setAttribute(nombre, valor) { this.atributos[nombre] = String(valor); }
  addEventListener(tipo, funcion) { (this.oyentes[tipo] = this.oyentes[tipo] || []).push(funcion); }
  emitir(tipo, evento = {}) {
    const completo = { target: this, preventDefault() { this.prevenido = true; }, ...evento };
    for (let nodo = this; nodo; nodo = nodo.parentNode) (nodo.oyentes[tipo] || []).forEach((f) => f(completo));
    return completo;
  }
  appendChild(hijo) { hijo.parentNode = this; this.hijos.push(hijo); return hijo; }
  insertBefore(hijo, referencia) { hijo.parentNode = this; this.hijos.splice(this.hijos.indexOf(referencia), 0, hijo); }
  removeChild(hijo) { this.hijos = this.hijos.filter((h) => h !== hijo); hijo.parentNode = null; }
  coincide(selector) {
    const dato = /^\[([a-z-]+)\]$/.exec(selector);
    return dato ? dato[1] in this.atributos : this.etiqueta === selector;
  }
  closest(selector) {
    for (let nodo = this; nodo; nodo = nodo.parentNode) if (nodo.coincide && nodo.coincide(selector)) return nodo;
    return null;
  }
  focus() { documento.enfocado = this; }
}

let documento;

function preparar() {
  const raiz = new Elemento("body");
  const dialogo = raiz.appendChild(new Elemento("dialog", { "data-visor": "", "aria-label": "Foto ampliada" }));
  const contenido = dialogo.appendChild(new Elemento("div"));
  const cerrar = contenido.appendChild(new Elemento("button", { "data-visor-cerrar": "" }));
  const figura = contenido.appendChild(new Elemento("figure"));
  const pie = figura.appendChild(new Elemento("figcaption", { "data-visor-pie": "" }));
  const miniatura = raiz.appendChild(new Elemento("a", { "data-visor-abrir": "", href: "/entregas/fotos/7/", "data-descripcion": "Portón verde" }));
  dialogo.open = false;
  dialogo.showModal = () => { dialogo.open = true; };
  dialogo.close = () => { dialogo.open = false; dialogo.emitir("close"); };
  documento = {
    enfocado: null,
    querySelector: (s) => ({ "[data-visor]": dialogo })[s] || null,
    querySelectorAll: (s) => (s === "[data-visor-abrir]" ? [miniatura] : []),
    addEventListener: (tipo, f) => raiz.addEventListener(tipo, f),
    createElement: (etiqueta) => new Elemento(etiqueta),
  };
  dialogo.querySelector = (s) => ({ "[data-visor-pie]": pie, "[data-visor-cerrar]": cerrar })[s];
  assert.equal(visor.preparar(documento), true);
  return { dialogo, cerrar, figura, pie, miniatura, contenido };
}

test("la miniatura pasa a botón y abre la imagen con su descripción como alternativa y pie", () => {
  const { dialogo, cerrar, figura, pie, miniatura } = preparar();
  assert.equal(miniatura.getAttribute("role"), "button");
  const evento = miniatura.emitir("click");
  assert.equal(evento.prevenido, true);
  assert.equal(dialogo.open, true);
  const imagen = figura.hijos[0];
  assert.equal(imagen.etiqueta, "img");
  assert.equal(imagen.src, "/entregas/fotos/7/");
  assert.equal(imagen.alt, "Portón verde");
  assert.equal(pie.textContent, "Portón verde");
  assert.equal(dialogo.getAttribute("aria-label"), "Foto ampliada: Portón verde");
  assert.equal(documento.enfocado, cerrar);
});

test("se cierra con la X y el foco vuelve a la miniatura", () => {
  const { dialogo, cerrar, figura, miniatura } = preparar();
  miniatura.emitir("click");
  cerrar.emitir("click");
  assert.equal(dialogo.open, false);
  assert.equal(figura.hijos.length, 1); // solo queda el pie: la imagen se retira
  assert.equal(documento.enfocado, miniatura);
});

test("un clic fuera de la imagen cierra; sobre la imagen no", () => {
  const { dialogo, contenido, figura, miniatura } = preparar();
  miniatura.emitir("click");
  figura.hijos[0].emitir("click");
  assert.equal(dialogo.open, true);
  contenido.emitir("click");
  assert.equal(dialogo.open, false);
  assert.equal(documento.enfocado, miniatura);
});

test("Esc usa el cierre nativo del diálogo y también devuelve el foco", () => {
  const { dialogo, miniatura } = preparar();
  miniatura.emitir("click");
  const evento = dialogo.emitir("cancel"); // Esc en un <dialog> modal
  assert.equal(evento.prevenido, true);
  assert.equal(dialogo.open, false);
  assert.equal(documento.enfocado, miniatura);
});

test("Espacio abre la foto como en un botón", () => {
  const { dialogo, miniatura } = preparar();
  const evento = miniatura.emitir("keydown", { key: " " });
  assert.equal(evento.prevenido, true);
  assert.equal(dialogo.open, true);
});

test("sin <dialog> no hace nada y quedan los enlaces", () => {
  assert.equal(visor.preparar({ querySelector: () => ({}) }), false);
  assert.equal(visor.nombre("Buzón azul"), "Foto ampliada: Buzón azul");
});

test("un «close» que llega tarde, con el visor ya reabierto, no quita la imagen nueva", () => {
  const { dialogo, figura, miniatura } = preparar();
  miniatura.emitir("click");
  dialogo.open = false; // el navegador cerró, pero su evento «close» aún no llega
  miniatura.emitir("click");
  dialogo.emitir("close");
  assert.equal(dialogo.open, true);
  assert.equal(figura.hijos.filter((h) => h.etiqueta === "img").length, 1);
});

test("limpia y devuelve el foco aunque el navegador no entregue «close» a tiempo", () => {
  const { dialogo, cerrar, figura, pie, miniatura } = preparar();
  dialogo.close = () => { dialogo.open = false; }; // «close» queda pendiente
  miniatura.emitir("click");
  cerrar.emitir("click");
  assert.equal(dialogo.open, false);
  assert.equal(figura.hijos.filter((h) => h.etiqueta === "img").length, 0);
  assert.equal(pie.textContent, "");
  assert.equal(documento.enfocado, miniatura);
});
