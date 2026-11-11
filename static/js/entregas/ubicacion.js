/*
  «Usar mi ubicación actual» del formulario de domicilio (spec 08, RF-08-03).
  Pide la ubicación solo al pulsar el botón, rellena latitud, longitud y precisión, y anuncia el resultado en la
  región aria-live. No guarda nada por sí misma: el servidor valida y guarda al enviar el formulario. Sin contexto
  seguro (HTTPS o localhost) o sin permiso, explica con texto que hay que escribir las coordenadas a mano.
*/
document.addEventListener("alpine:init", () => {
  const SIN_CONTEXTO = "Este navegador no permite usar la ubicación aquí: se necesita una conexión segura (HTTPS). Escribe la latitud y la longitud a mano.";
  const SIN_PERMISO = "No diste permiso para usar la ubicación. Escribe la latitud y la longitud a mano.";
  const SIN_SENAL = "No pudimos obtener la ubicación. Inténtalo de nuevo al aire libre o escribe las coordenadas a mano.";

  function redondear(valor, decimales) {
    return Number(valor).toFixed(decimales);
  }

  Alpine.data("ubicacion", () => ({
    estado: "",
    ocupado: false,
    disponible: false,
    init() {
      this.disponible = Boolean(window.isSecureContext && navigator.geolocation);
      if (!this.disponible) this.estado = SIN_CONTEXTO;
    },
    campo(nombre) {
      const formulario = this.$root.closest("form") || this.$root;
      return formulario.querySelector(`[name="${nombre}"]`);
    },
    usar() {
      if (!this.disponible) {
        this.estado = SIN_CONTEXTO;
        return;
      }
      this.ocupado = true;
      this.estado = "Buscando tu ubicación…";
      navigator.geolocation.getCurrentPosition(
        (posicion) => {
          const { latitude, longitude, accuracy } = posicion.coords;
          const latitud = redondear(latitude, 6);
          const longitud = redondear(longitude, 6);
          const precision = Number.isFinite(accuracy) ? String(Math.round(accuracy)) : "";
          this.campo("latitud").value = latitud;
          this.campo("longitud").value = longitud;
          this.campo("precision_metros").value = precision;
          this.estado = `Ubicación lista: ${latitud}, ${longitud}${precision ? ` (±${precision} m)` : ""}. Revisa los datos y guarda el domicilio.`;
          this.ocupado = false;
        },
        (error) => {
          this.estado = error && error.code === 1 ? SIN_PERMISO : SIN_SENAL;
          this.ocupado = false;
        },
        { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 },
      );
    },
  }));
});
