"""Atención sintética con dos recetas y cupos disponibles."""
import uuid
from datetime import timedelta
from recetasapp.models import Receta
from turnosapp.atencion import finalizar_atencion
from turnosapp.cola import procesar_pendiente
from turnosapp.models import TurnoReceta
from .datos_cola import DatosCola


class DatosCierre(DatosCola):
    def setUp(self):
        super().setUp()
        self.ventanilla = self.activar()
        self.actual = self.turno()
        self.recetas_cierre, self.vinculos = [], []
        for indice in range(2):
            receta = Receta.objects.create(paciente=self.actual.paciente, codigo=f"CIERRE-DEMO-{indice}",
                fecha_inicio=self.fecha, fecha_fin_exclusiva=self.fecha + timedelta(days=30), vigencia_meses=1, max_entregas=3)
            self.recetas_cierre.append(receta)
            self.vinculos.append(TurnoReceta.objects.create(turno=self.actual, receta=receta))
        procesar_pendiente(self.pendiente().pk)
        self.actual.refresh_from_db()

    def confirmar(self, seleccion=None, operacion=None, **datos):
        ids = [r.pk for r in self.recetas_cierre] if seleccion is None else seleccion
        def ejecutar():
            return finalizar_atencion(self.personal["tecnico"], self.actual.pk, operacion or uuid.uuid4(), recetas_entregadas=ids, **datos)
        if hasattr(self, "captureOnCommitCallbacks"):
            with self.captureOnCommitCallbacks(execute=True):
                return ejecutar()
        return ejecutar()
