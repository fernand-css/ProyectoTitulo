"""Consultas derivadas de preparación y pendientes de retiro."""

from datetime import date, datetime, timedelta
from random import Random
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase

from coreapp.utils.sinteticos import generar_ruts
from recetasapp.models import Paciente, PreparacionReceta, Receta
from recetasapp.preparacion import pendientes_retiro, por_preparar
from turnosapp.models import Turno, TurnoReceta, Ventanilla


class ConsultasPreparacionTests(TestCase):
    def setUp(self):
        self.hoy = date(2026, 11, 3)
        self.instante = datetime(2026, 11, 3, 9, tzinfo=ZoneInfo("America/Santiago"))
        self.usuario = get_user_model().objects.create_user(username="consulta-preparacion")
        self.ruts = generar_ruts(8, Random(872))
        self.turno_numero = 0
        self.receta_numero = 0

    def preparacion(self, indice, estado, *, lista=True, apellidos="Álvarez Muñoz", entrada=None):
        paciente = Paciente.objects.create(
            rut=self.ruts[indice], nombres=f"Paciente {indice}", apellidos=apellidos,
            fecha_nacimiento=date(1980, 1, 1),
        )
        self.turno_numero += 1
        asignacion = {}
        if estado == "llamado":
            ventanilla = Ventanilla.objects.create(numero=20 + indice, operador=self.usuario)
            asignacion = {
                "ventanilla": ventanilla, "operador": self.usuario,
                "ultimo_llamado": self.instante,
            }
        turno = Turno.objects.create(
            paciente=paciente, fecha=self.hoy, numero=self.turno_numero,
            tipo_atencion="general", estado=estado,
            cerrado_en=self.instante if estado in ("ausente", "sin_atencion_cierre", "atendido", "cerrado_sin_entrega") else None,
            entrada_cola=entrada or self.instante + timedelta(minutes=indice),
            **asignacion,
        )
        self.receta_numero += 1
        receta = Receta.objects.create(
            paciente=paciente, codigo=f"CONSULTA-{self.receta_numero}", fecha_inicio=self.hoy,
            fecha_fin_exclusiva=self.hoy + timedelta(days=30), vigencia_meses=1, max_entregas=2,
        )
        vinculo = TurnoReceta.objects.create(turno=turno, receta=receta)
        return PreparacionReceta.objects.create(
            turno_receta=vinculo, recibida_en=self.instante,
            lista_en=self.instante if lista else None,
            lista_por=self.usuario if lista else None,
            inicio_medido=self.instante if lista else None,
            duracion_segundos=0 if lista else None,
        )

    def test_por_preparar_solo_turnos_activos_y_en_orden_de_llegada(self):
        tarde = self.preparacion(0, "esperando", lista=False, entrada=self.instante + timedelta(minutes=5))
        temprano = self.preparacion(1, "llamado", lista=False, entrada=self.instante)
        self.preparacion(2, "ausente", lista=False)
        self.assertEqual(list(por_preparar(self.hoy)), [temprano, tarde])

    def test_pendiente_derivado_incluye_cierres_y_excluye_activos(self):
        esperados = {
            self.preparacion(0, "ausente").pk,
            self.preparacion(1, "sin_atencion_cierre").pk,
            self.preparacion(2, "atendido").pk,
            self.preparacion(3, "cerrado_sin_entrega").pk,
        }
        self.preparacion(4, "esperando")
        self.preparacion(5, "ausente", lista=False)
        reincorporado = self.preparacion(6, "esperando")
        self.assertEqual(set(pendientes_retiro().values_list("pk", flat=True)), esperados)
        self.assertNotIn(reincorporado.pk, set(pendientes_retiro().values_list("pk", flat=True)))

    def test_busca_por_rut_con_puntos_y_apellido_sin_acentos(self):
        preparacion = self.preparacion(0, "ausente", apellidos="Álvarez Muñoz")
        cuerpo, dv = preparacion.turno_receta.turno.paciente.rut.split("-")
        rut_con_puntos = f"{int(cuerpo):,}-{dv}".replace(",", ".")
        self.assertEqual(list(pendientes_retiro(rut_con_puntos)), [preparacion])
        self.assertEqual(list(pendientes_retiro("alvarez")), [preparacion])
        self.assertEqual(list(pendientes_retiro("MUÑOZ")), [preparacion])
        self.assertFalse(pendientes_retiro("nadie"))
