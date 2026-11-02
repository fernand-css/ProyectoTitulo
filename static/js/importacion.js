/*
  Pantalla «Importar padrón»: muestra el archivo elegido y deduce el formato por su extensión.
  Es una comodidad: el servidor vuelve a validar el formato y el contenido del archivo.
*/
document.addEventListener("alpine:init", () => {
  const FORMATOS = { csv: "csv", xlsx: "xlsx" };

  Alpine.data("importacion", () => ({
    nombre: "",
    detectado: false,
    sobre: false,
    init() {
      const campo = this.$root.querySelector('input[type="file"]');
      if (campo) campo.addEventListener("change", () => this.elegir(campo));
    },
    elegir(campo) {
      const archivo = campo.files && campo.files[0];
      this.detectado = false;
      if (!archivo) { this.nombre = ""; return; }
      const kib = archivo.size / 1024;
      this.nombre = archivo.name + " (" + (kib < 1024 ? Math.max(1, Math.round(kib)) + " KiB" : (kib / 1024).toFixed(1).replace(".", ",") + " MiB") + ")";
      const extension = (archivo.name.split(".").pop() || "").toLowerCase();
      const selector = this.$root.querySelector("select");
      if (selector && FORMATOS[extension]) {
        selector.value = FORMATOS[extension];
        this.detectado = true;
      }
    },
  }));
});
