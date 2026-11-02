"use strict";

const serviceWorkerUrl = document.currentScript.dataset.serviceWorker;
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register(serviceWorkerUrl, { scope: "/" }).catch(() => {
      console.warn("No se pudo registrar la aplicación en este navegador.");
    });
  });
}
