"""Restricciones persistentes de turnos con pacientes exclusivamente sintéticos."""

import uuid
from datetime import date, timedelta
from random import Random

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from coreapp.models import RegistroAuditoria
from coreapp.utils.sinteticos import generar_ruts
from recetasapp.models import EntregaReceta, Paciente, Receta
from turnosapp.models import ContadorTurnosDiario, Turno, TurnoReceta


class ModelosTurnosTests(TestCase):
    def setUp(self):
        self.fecha = date(2026, 11, 2)
        ruts = generar_ruts(2, Random(404))
        self.pacientes = [
            Paciente.objects.create(
                rut=rut, nombres="Paciente sintético", apellidos=f"Demostración {indice}",
                fecha_nacimiento=date(1970, 1, 1),
            )
            for indice, rut in enumerate(ruts)
        ]
        self.receta = Receta.objects.create(
            paciente=self.pacientes[0], codigo="TURNO-DEMO-001",
            fecha_inicio=self.fecha, fecha_fin_exclusiva=date(2027, 5, 2),
            vigencia_meses=6, max_entregas=6,
        )

    def turno(self, **cambios):
        datos = {
            "paciente": self.pacientes[0], "fecha": self.fecha, "numero": 1,
            "tipo_atencion": Turno.TipoAtencion.GENERAL,
        }
        datos.update(cambios)
        return Turno.objects.create(**datos)

    def test_contador_diario_es_unico_y_no_admite_negativos(self):
        contador = ContadorTurnosDiario.objects.create(fecha=self.fecha)
        self.assertEqual(contador.ultimo_numero, 0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ContadorTurnosDiario.objects.create(fecha=self.fecha)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ContadorTurnosDiario.objects.filter(pk=contador.pk).update(ultimo_numero=-1)
        otro = ContadorTurnosDiario.objects.create(fecha=self.fecha + timedelta(days=1))
        self.assertEqual(otro.ultimo_numero, 0)

    def test_numero_es_unico_por_fecha_incluso_con_otro_tipo_y_paciente(self):
        self.turno()
        for tipo in (Turno.TipoAtencion.PREFERENCIAL, Turno.TipoAtencion.CRONICOS):
            with self.subTest(tipo=tipo), self.assertRaises(IntegrityError), transaction.atomic():
                self.turno(paciente=self.pacientes[1], tipo_atencion=tipo)
        self.turno(paciente=self.pacientes[1], numero=2)
        self.assertEqual(Turno.objects.count(), 2)

    def test_un_paciente_no_puede_tener_dos_activos_el_mismo_dia(self):
        original = self.turno()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.turno(numero=2, tipo_atencion=Turno.TipoAtencion.CRONICOS)
        self.assertEqual(Turno.objects.get().pk, original.pk)

    def test_otro_dia_admite_mismo_paciente_y_numero_conservando_historial(self):
        anterior = self.turno()
        nuevo = self.turno(fecha=self.fecha + timedelta(days=1))
        self.assertNotEqual(anterior.pk, nuevo.pk)
        self.assertEqual(Turno.objects.count(), 2)
        self.assertEqual(anterior.estado, Turno.Estado.ESPERANDO)

    def test_uuid_de_operacion_es_unico_tambien_entre_dias(self):
        operacion = uuid.uuid4()
        self.turno(operacion_id=operacion)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.turno(fecha=self.fecha + timedelta(days=1), operacion_id=operacion)

    def test_base_rechaza_numero_cero_negativo_y_estados_o_tipos_desconocidos(self):
        turno = self.turno()
        for cambio in (
            {"numero": 0}, {"numero": -1}, {"tipo_atencion": "urgencia"},
            {"tipo_atencion": ""}, {"estado": "atendido"}, {"estado": ""},
        ):
            with self.subTest(cambio=cambio), self.assertRaises(IntegrityError), transaction.atomic():
                Turno.objects.filter(pk=turno.pk).update(**cambio)

    def test_admite_tipos_acordados_y_actor_nulo_sin_crear_usuario(self):
        turno = self.turno(tipo_atencion=Turno.TipoAtencion.CRONICOS)
        turno.full_clean()
        self.assertIsNone(turno.creado_por_id)
        self.assertIsNone(turno.modificado_por_id)
        self.assertEqual(turno.estado, Turno.Estado.ESPERANDO)
        self.assertIsInstance(turno.operacion_id, uuid.UUID)
        self.assertIsNotNone(turno.creado_en)

    def test_relacion_no_se_duplica_y_permite_varias_recetas(self):
        turno = self.turno()
        TurnoReceta.objects.create(turno=turno, receta=self.receta)
        with self.assertRaises(IntegrityError), transaction.atomic():
            TurnoReceta.objects.create(turno=turno, receta=self.receta)
        otra = Receta.objects.create(
            paciente=self.pacientes[0], codigo="TURNO-DEMO-002",
            fecha_inicio=self.fecha, fecha_fin_exclusiva=date(2027, 5, 2),
            vigencia_meses=6, max_entregas=6,
        )
        TurnoReceta.objects.create(turno=turno, receta=otra)
        self.assertEqual(turno.recetas_vinculadas.count(), 2)

    def test_validacion_rechaza_receta_de_otro_paciente(self):
        turno = self.turno(paciente=self.pacientes[1])
        vinculo = TurnoReceta(turno=turno, receta=self.receta)
        with self.assertRaises(ValidationError) as error:
            vinculo.full_clean()
        self.assertIn("receta", error.exception.message_dict)
        vinculo.turno = self.turno(numero=2)
        vinculo.full_clean()
        vinculo.save()

    def test_historial_protege_paciente_receta_y_turno_vinculado(self):
        turno = self.turno()
        TurnoReceta.objects.create(turno=turno, receta=self.receta)
        for objeto in (self.pacientes[0], self.receta, turno):
            with self.subTest(modelo=type(objeto).__name__), self.assertRaises(ProtectedError):
                objeto.delete()

    def test_persistir_turno_y_vinculo_no_consume_entregas_ni_audita_sin_servicio(self):
        turno = self.turno()
        TurnoReceta.objects.create(turno=turno, receta=self.receta)
        self.receta.refresh_from_db()
        self.assertEqual(self.receta.entregas_completadas, 0)
        self.assertEqual(self.receta.max_entregas, 6)
        self.assertEqual(EntregaReceta.objects.count(), 0)
        self.assertEqual(RegistroAuditoria.objects.count(), 0)

    def test_modelos_no_duplican_identidad_ni_incorporan_discapacidad(self):
        for modelo in (Turno, TurnoReceta, ContadorTurnosDiario):
            campos = {campo.name for campo in modelo._meta.fields}
            self.assertFalse({"rut", "nombres", "fecha_nacimiento", "es_discapacitado", "discapacidad"} & campos)
        turno = self.turno()
        vinculo = TurnoReceta(turno=turno, receta=self.receta)
        for objeto in (turno, vinculo):
            self.assertNotIn(self.pacientes[0].rut, str(objeto))
            self.assertNotIn(self.pacientes[0].nombres, str(objeto))
            self.assertNotIn(self.receta.codigo, str(objeto))
