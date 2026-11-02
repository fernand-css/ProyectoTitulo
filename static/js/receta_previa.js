/*
  Vista previa de «Crear receta»: dibuja una casilla por entrega y calcula el último día válido mientras se escribe.
  Es solo una ayuda visual; el servidor vuelve a calcular y validar todo al guardar (recetasapp/services.py: calcular_fin).
  Mismo cálculo: inicio + meses (día ajustado al fin de mes si el mes es más corto) y se resta un día.
*/
document.addEventListener("alpine:init", () => {
  const LIMITE = 24; // igual que MAX_CASILLAS en recetasapp/presentacion.py
  const MAX_MESES = 1200;
  const formato = new Intl.DateTimeFormat("es-CL", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });

  // Devuelve el último día válido (Date en UTC) o null si los datos no alcanzan.
  function ultimoDiaValido(iso, meses) {
    const partes = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
    if (!partes || !Number.isInteger(meses) || meses < 1 || meses > MAX_MESES) return null;
    const anio0 = Number(partes[1]), mes0 = Number(partes[2]) - 1, dia0 = Number(partes[3]);
    const probe = new Date(Date.UTC(anio0, mes0, dia0));
    if (probe.getUTCFullYear() !== anio0 || probe.getUTCMonth() !== mes0 || probe.getUTCDate() !== dia0) return null;
    const total = anio0 * 12 + mes0 + meses;
    const anio = Math.floor(total / 12), mes = total % 12;
    if (anio > 9999) return null;
    const diasDelMes = new Date(Date.UTC(anio, mes + 1, 0)).getUTCDate();
    const finExclusivo = new Date(Date.UTC(anio, mes, Math.min(dia0, diasDelMes)));
    finExclusivo.setUTCDate(finExclusivo.getUTCDate() - 1);
    return finExclusivo;
  }

  Alpine.data("recetaPrevia", () => ({
    cupo: 0,
    limite: LIMITE,
    textoFin: "",
    init() { this.leer(); },
    leer() {
      const valor = (id) => { const campo = this.$root.querySelector("#" + id); return campo ? campo.value : ""; };
      const cupo = parseInt(valor("id_max_entregas"), 10);
      this.cupo = Number.isInteger(cupo) && cupo > 0 ? cupo : 0;
      const fin = ultimoDiaValido(valor("id_fecha_inicio"), parseInt(valor("id_vigencia_meses"), 10));
      this.textoFin = fin ? "Último día válido: " + formato.format(fin) : "Indica el inicio y los meses para ver el último día válido.";
    },
    get casillas() {
      return Array.from({ length: Math.min(this.cupo, LIMITE) }, (_, indice) => indice + 1);
    },
  }));
  // Expuesta para las pruebas de comportamiento.
  window.__ultimoDiaValido = ultimoDiaValido;
});
