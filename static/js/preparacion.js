(() => {
  const actualizar = async () => {
    const actual = document.querySelector("[data-autorefresh]");
    if (!actual) return;

    const url = new URL(window.location.href);
    url.searchParams.set("fragmento", "1");
    try {
      const respuesta = await fetch(url, {
        cache: "no-store",
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (!respuesta.ok) return;
      const documento = new DOMParser().parseFromString(await respuesta.text(), "text/html");
      const nuevo = documento.querySelector("[data-autorefresh]");
      if (nuevo && actual.innerHTML !== nuevo.innerHTML) actual.replaceWith(nuevo);
    } catch (_error) {
      // La operación manual sigue disponible; el siguiente sondeo reintentará.
    }
  };

  window.setInterval(actualizar, 5000);
})();
