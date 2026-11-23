// DOM mínimo para las pruebas de Node de las tarjetas, el orden, «Usar mapa» y el mapa (spec 09, enmienda del
// 2026-11-15). Implementa lo justo que usan esos archivos: árbol, atributos, clases, hidden, eventos y selectores
// simples (etiqueta, #id, .clase, [atributo], [atributo="valor"], :not([hidden]), descendiente y listas con coma).

class Lista {
  constructor(nodo) { this.nodo = nodo; }
  get valores() { return (this.nodo.getAttribute("class") || "").split(/\s+/).filter(Boolean); }
  contains(clase) { return this.valores.includes(clase); }
  add(...clases) { this.nodo.setAttribute("class", [...new Set([...this.valores, ...clases])].join(" ")); }
  remove(...clases) { this.nodo.setAttribute("class", this.valores.filter((c) => !clases.includes(c)).join(" ")); }
  toggle(clase, forzar) {
    const poner = forzar === undefined ? !this.contains(clase) : Boolean(forzar);
    if (poner) this.add(clase); else this.remove(clase);
    return poner;
  }
}

function partesSimples(selector) {
  const partes = [];
  const expresion = /:not\(\[([\w-]+)\]\)|\[([\w-]+)(?:=(?:"([^"]*)"|([\w-]+)))?\]|#([\w-]+)|\.([\w-]+)|([a-zA-Z][a-zA-Z0-9-]*)/g;
  let m;
  while ((m = expresion.exec(selector))) {
    const [, no, atributo, comillas, suelto, id, clase, etiqueta] = m;
    if (no) partes.push((n) => !n.hasAttribute(no));
    else if (atributo) {
      const valor = comillas !== undefined ? comillas : suelto;
      partes.push((n) => n.hasAttribute(atributo) && (valor === undefined || n.getAttribute(atributo) === valor));
    } else if (id) partes.push((n) => n.getAttribute("id") === id);
    else if (clase) partes.push((n) => n.classList.contains(clase));
    else if (etiqueta) partes.push((n) => n.tagName === etiqueta.toUpperCase());
  }
  return (n) => partes.every((p) => p(n));
}

function coincide(nodo, selector, raiz) {
  return selector.split(",").some((alternativa) => {
    const pasos = alternativa.trim().split(/\s+/).map(partesSimples);
    if (!pasos[pasos.length - 1](nodo)) return false;
    let actual = nodo.parentNode;
    for (let i = pasos.length - 2; i >= 0; i -= 1) {
      while (actual && actual !== raiz.parentNode && !(actual.esElemento && pasos[i](actual))) actual = actual.parentNode;
      if (!actual || actual === raiz.parentNode) return false;
      actual = actual.parentNode;
    }
    return true;
  });
}

class Nodo {
  constructor(documento, etiqueta) {
    this.ownerDocument = documento;
    this.tagName = etiqueta ? etiqueta.toUpperCase() : "#text";
    this.esElemento = Boolean(etiqueta);
    this.atributos = new Map();
    this.childNodes = [];
    this.parentNode = null;
    this.escuchas = {};
    this.style = {};
    this.classList = new Lista(this);
    this._texto = "";
    this.rect = { top: 0, bottom: 0, left: 0, right: 0, width: 0, height: 0 };
    this.value = "";
  }
  get children() { return this.childNodes.filter((n) => n.esElemento); }
  get firstChild() { return this.childNodes[0] || null; }
  get firstElementChild() { return this.children[0] || null; }
  get nextSibling() {
    if (!this.parentNode) return null;
    const hermanos = this.parentNode.childNodes;
    return hermanos[hermanos.indexOf(this) + 1] || null;
  }
  get id() { return this.getAttribute("id") || ""; }
  set id(valor) { this.setAttribute("id", valor); }
  get className() { return this.getAttribute("class") || ""; }
  set className(valor) { this.setAttribute("class", valor); }
  get hidden() { return this.hasAttribute("hidden"); }
  set hidden(valor) { if (valor) this.setAttribute("hidden", ""); else this.removeAttribute("hidden"); }
  get textContent() { return this.esElemento ? this.childNodes.map((n) => n.textContent).join("") : this._texto; }
  set textContent(valor) {
    if (!this.esElemento) { this._texto = String(valor); return; }
    this.childNodes.forEach((n) => { n.parentNode = null; });
    this.childNodes = [];
    if (valor !== "" && valor != null) this.appendChild(this.ownerDocument.createTextNode(String(valor)));
  }
  getAttribute(nombre) { return this.atributos.has(nombre) ? this.atributos.get(nombre) : null; }
  setAttribute(nombre, valor) { this.atributos.set(nombre, String(valor)); }
  removeAttribute(nombre) { this.atributos.delete(nombre); }
  hasAttribute(nombre) { return this.atributos.has(nombre); }
  _soltar(nodo) {
    if (nodo.parentNode) {
      const hermanos = nodo.parentNode.childNodes;
      hermanos.splice(hermanos.indexOf(nodo), 1);
    }
  }
  appendChild(nodo) { this._soltar(nodo); this.childNodes.push(nodo); nodo.parentNode = this; return nodo; }
  insertBefore(nodo, referencia) {
    if (!referencia) return this.appendChild(nodo);
    this._soltar(nodo);
    this.childNodes.splice(this.childNodes.indexOf(referencia), 0, nodo);
    nodo.parentNode = this;
    return nodo;
  }
  removeChild(nodo) { this._soltar(nodo); nodo.parentNode = null; return nodo; }
  replaceChild(nuevo, viejo) { this.insertBefore(nuevo, viejo); this.removeChild(viejo); return viejo; }
  descendientes() {
    const lista = [];
    const visitar = (n) => n.children.forEach((h) => { lista.push(h); visitar(h); });
    visitar(this);
    return lista;
  }
  querySelectorAll(selector) { return this.descendientes().filter((n) => coincide(n, selector, this)); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  matches(selector) { return coincide(this, selector, this.ownerDocument.body); }
  closest(selector) {
    let actual = this;
    while (actual && actual.esElemento) {
      if (actual.matches(selector)) return actual;
      actual = actual.parentNode;
    }
    return null;
  }
  addEventListener(tipo, fn) { (this.escuchas[tipo] = this.escuchas[tipo] || []).push(fn); }
  removeEventListener(tipo, fn) { this.escuchas[tipo] = (this.escuchas[tipo] || []).filter((f) => f !== fn); }
  dispatchEvent(evento) {
    evento.target = evento.target || this;
    let actual = this;
    while (actual) {
      (actual.escuchas[evento.type] || []).slice().forEach((fn) => fn(evento));
      actual = actual.parentNode;
    }
    return !evento.defaultPrevented;
  }
  click() { this.dispatchEvent(evento("click")); }
  focus() { this.ownerDocument.activeElement = this; }
  contains(otro) { for (let n = otro; n; n = n.parentNode) { if (n === this) return true; } return false; }
  getBoundingClientRect() { return this.rect; }
}

function evento(tipo, datos) {
  return Object.assign({ type: tipo, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } }, datos || {});
}

class Documento extends Nodo {
  constructor() {
    super(null, "documento");
    this.ownerDocument = this;
    this.body = this.createElement("body");
    this.appendChild(this.body);
    this.activeElement = null;
  }
  createElement(etiqueta) {
    const nodo = new Nodo(this, etiqueta);
    if (etiqueta === "template") {
      nodo.content = { firstElementChild: null };
      Object.defineProperty(nodo, "innerHTML", { set: (html) => { nodo.content.firstElementChild = this.desdeHtml(html); } });
    }
    return nodo;
  }
  createTextNode(texto) { const n = new Nodo(this, null); n._texto = texto; return n; }
  getElementById(id) { return this.querySelector("#" + id); }
  // HTML muy simple para las pruebas: un elemento con atributos y texto, sin anidar.
  desdeHtml(html) {
    const m = /^<([a-z0-9]+)([^>]*)>([^<]*)<\/\1>$/i.exec(html.trim());
    if (!m) return null;
    const nodo = this.createElement(m[1]);
    const atributos = /([\w-]+)(?:="([^"]*)")?/g;
    let a;
    while ((a = atributos.exec(m[2]))) nodo.setAttribute(a[1], a[2] === undefined ? "" : a[2]);
    nodo.textContent = m[3];
    return nodo;
  }
}

// Construye un árbol desde una descripción: ["etiqueta", {atributos}, ...hijos o texto].
function crear(documento, descripcion) {
  if (typeof descripcion === "string") return documento.createTextNode(descripcion);
  const [etiqueta, atributos, ...hijos] = descripcion;
  const nodo = documento.createElement(etiqueta);
  Object.entries(atributos || {}).forEach(([nombre, valor]) => nodo.setAttribute(nombre, valor === true ? "" : valor));
  if (atributos && atributos.value !== undefined) nodo.value = String(atributos.value);
  hijos.forEach((hijo) => nodo.appendChild(crear(documento, hijo)));
  return nodo;
}

module.exports = { Documento, crear, evento };
