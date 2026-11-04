"""Emisión concurrente con creación de preparaciones, con datos sintéticos."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import uuid
from datetime import timedelta

from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from django.utils import timezone

from coreapp.models import RegistroAuditoria
from recetasapp.models import EntregaReceta, PreparacionReceta, Receta
from recetasapp.services import marcar_lista, registrar_entrega, retirar_preparado
from recetasapp.tests.ayudas import actores
from turnosapp.atencion import reincorporar
from turnosapp.models import Turno, TurnoReceta, Ventanilla
from turnosapp.services import emitir_turno
from turnosapp.tests import test_servicios as servicios


class ConcurrenciaPreparacionTests(TransactionTestCase):
    setUp = servicios.EmisionTests.setUp
    pacientes = servicios.EmisionTests.pacientes
    recetas = servicios.EmisionTests.recetas
    emitir = servicios.EmisionTests.emitir

    def competir(self, solicitudes):
        barrera = Barrier(len(solicitudes))

        def ejecutar(solicitud):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return solicitud() if callable(solicitud) else emitir_turno(*solicitud)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(solicitudes)) as pool:
            return list(pool.map(ejecutar, solicitudes))

    def test_tres_emisiones_simultaneas_crean_una_preparacion_por_vinculo(self):
        pacientes = [self.paciente, self.pacientes(1), self.pacientes(2)]
        for indice, paciente in enumerate(pacientes[1:], start=2):
            self.recetas(paciente, f"PREP-CONCURRENTE-{indice}")

        resultados = self.competir([(paciente.rut, uuid.uuid4()) for paciente in pacientes])

        self.assertEqual({resultado.numero for resultado in resultados}, {1, 2, 3})
        self.assertEqual(Turno.objects.count(), 3)
        self.assertEqual(PreparacionReceta.objects.count(), 3)
        for preparacion in PreparacionReceta.objects.select_related("turno_receta__turno"):
            self.assertEqual(preparacion.turno_receta.turno.creado_en, preparacion.recibida_en)

    @staticmethod
    def resultado_seguro(funcion):
        from django.core.exceptions import ValidationError
        try:
            return "ok", funcion()
        except ValidationError as error:
            return "rechazado", error

    def preparada_ausente(self, *, max_entregas=1):
        self.receta.max_entregas = max_entregas
        self.receta.save(update_fields=["max_entregas"])
        self.emitir()
        actor = actores()["tecnico"]
        preparacion = PreparacionReceta.objects.get(turno_receta__receta=self.receta)
        ahora = timezone.now()
        PreparacionReceta.objects.filter(pk=preparacion.pk).update(
            recibida_en=ahora - timedelta(minutes=10), lista_en=ahora - timedelta(minutes=1),
            lista_por=actor, inicio_medido=ahora - timedelta(minutes=2), duracion_segundos=60,
        )
        Turno.objects.filter(pk=preparacion.turno_receta.turno_id).update(
            estado="ausente", cerrado_en=ahora,
        )
        preparacion.refresh_from_db()
        return actor, preparacion

    def test_dos_retiros_simultaneos_no_crean_dos_entregas(self):
        actor, preparacion = self.preparada_ausente()
        operaciones = [uuid.uuid4(), uuid.uuid4()]
        resultados = self.competir([
            lambda op=op: self.resultado_seguro(lambda: retirar_preparado(actor, preparacion.pk, op))
            for op in operaciones
        ])

        self.assertEqual(sum(estado == "ok" for estado, _ in resultados), 1)
        self.assertEqual(EntregaReceta.objects.filter(turno_receta__receta=self.receta).count(), 1)
        self.receta.refresh_from_db()
        self.assertEqual(self.receta.entregas_completadas, 1)

    def test_marca_simultanea_de_dos_usuarios_conserva_una_medicion(self):
        self.emitir()
        actores_turno = actores()
        preparacion = PreparacionReceta.objects.get(turno_receta__receta=self.receta)
        resultados = self.competir([
            lambda usuario=usuario: marcar_lista(usuario, preparacion.pk)
            for usuario in (actores_turno["qf"], actores_turno["tecnico"])
        ])

        self.assertEqual(len({resultado.pk for resultado in resultados}), 1)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="preparacion.lista").count(), 1)
        preparacion.refresh_from_db()
        self.assertIsNotNone(preparacion.lista_en)

    def test_retiro_compite_con_entrega_regular_en_el_ultimo_cupo(self):
        actor, preparacion = self.preparada_ausente()
        turno_nuevo = Turno.objects.create(
            paciente=self.paciente, fecha=self.fecha, numero=2, tipo_atencion="general",
            estado="llamado", ventanilla=Ventanilla.objects.create(numero=31, operador=actor),
            operador=actor, ultimo_llamado=timezone.now(),
        )
        vinculo_nuevo = TurnoReceta.objects.create(turno=turno_nuevo, receta=self.receta)
        operaciones = [uuid.uuid4(), uuid.uuid4()]
        resultados = self.competir([
            lambda: self.resultado_seguro(lambda: retirar_preparado(actor, preparacion.pk, operaciones[0])),
            lambda: self.resultado_seguro(lambda: registrar_entrega(
                actor, self.receta.pk, operaciones[1], turno_receta_id=vinculo_nuevo.pk,
            )),
        ])

        self.assertEqual(sum(estado == "ok" for estado, _ in resultados), 1)
        self.assertEqual(EntregaReceta.objects.filter(receta=self.receta).count(), 1)
        self.receta.refresh_from_db()
        self.assertEqual(self.receta.entregas_completadas, 1)

    def test_retiro_compite_con_reincorporacion_sin_estado_incoherente(self):
        actor, preparacion = self.preparada_ausente(max_entregas=3)
        resultados = self.competir([
            lambda: self.resultado_seguro(lambda: retirar_preparado(actor, preparacion.pk, uuid.uuid4())),
            lambda: self.resultado_seguro(lambda: reincorporar(actor, preparacion.turno_receta.turno_id, uuid.uuid4())),
        ])

        turno = Turno.objects.get(pk=preparacion.turno_receta.turno_id)
        self.assertEqual(sum(estado == "ok" for estado, _ in resultados), 1)
        if turno.estado == "esperando":
            self.assertFalse(EntregaReceta.objects.filter(turno_receta=preparacion.turno_receta).exists())
        else:
            self.assertEqual(turno.estado, "ausente")
            self.assertTrue(EntregaReceta.objects.filter(turno_receta=preparacion.turno_receta).exists())
