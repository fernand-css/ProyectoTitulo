"""RF-08-06: programar una entrega con sus recetas fijadas, sin duplicarla y con rechazos claros."""

import uuid
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from coreapp.models import RegistroAuditoria
from entregasapp.models import Entrega, IntentoEntrega, RecetaEntrega
from entregasapp.services import EntregaAbiertaExistente, inscribir_excepcion, programar_entrega
from recetasapp.models import PreparacionReceta
from turnosapp.models import Turno, TurnoReceta
from .ayudas import cuenta, equipo, hoy, paciente, receta


def turno(paciente_obj, recetas, estado="esperando", numero=None):
    instante = timezone.now()
    datos = {"cerrado_en": instante} if estado not in ("esperando", "llamado") else {}
    nuevo = Turno.objects.create(paciente=paciente_obj, fecha=hoy(), numero=numero or Turno.objects.count() + 1,
                                 tipo_atencion="general", estado=estado, **datos)
    vinculos = [TurnoReceta.objects.create(turno=nuevo, receta=r) for r in recetas]
    return nuevo, vinculos


class ProgramacionTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.qf = self.equipo["qf"]
        self.encargado = self.equipo["encargado"]
        self.paciente = paciente(edad=85)

    def programar(self, paciente_obj=None, fecha=None, encargado=None, operacion=None, actor=None):
        return programar_entrega(actor or self.qf, (paciente_obj or self.paciente).pk, fecha or hoy(),
                                 (encargado or self.encargado).pk, operacion or uuid.uuid4())

    def test_fija_solo_las_recetas_vigentes_sin_turno_activo_ni_retiro_pendiente(self):
        vigente = receta(self.paciente, "VIGENTE")
        receta(self.paciente, "VENCIDA", inicio=hoy() - timedelta(days=200), fin=hoy())
        receta(self.paciente, "AGOTADA", maximo=2, completadas=2)
        receta(self.paciente, "FUTURA", inicio=hoy() + timedelta(days=5))
        en_turno = receta(self.paciente, "EN-TURNO")
        por_retirar = receta(self.paciente, "POR-RETIRAR")
        turno(self.paciente, [en_turno])
        _, (vinculo,) = turno(self.paciente, [por_retirar], estado="ausente")
        ahora = timezone.now()
        PreparacionReceta.objects.create(turno_receta=vinculo, recibida_en=ahora - timedelta(minutes=5), lista_en=ahora,
                                         lista_por=self.equipo["tecnico"], inicio_medido=ahora - timedelta(minutes=4),
                                         duracion_segundos=240)
        entrega = self.programar()
        self.assertEqual(list(entrega.recetas.values_list("receta_id", flat=True)), [vigente.pk])
        self.assertEqual(entrega.estado, "programada")
        intento = entrega.intentos.get()
        self.assertEqual((intento.numero, intento.fecha_programada, intento.encargado, intento.resultado),
                         (1, hoy(), self.encargado, "pendiente"))
        self.assertEqual(entrega.creado_por, self.qf)
        self.assertTrue(RegistroAuditoria.objects.filter(accion="entrega.programada", objeto_id=str(entrega.pk)).exists())

    def test_la_eleccion_de_recetas_usa_la_fecha_programada(self):
        receta(self.paciente, "VENCE-MANANA", inicio=hoy() - timedelta(days=30), fin=hoy() + timedelta(days=1))
        inicia = receta(self.paciente, "INICIA-EN-3", inicio=hoy() + timedelta(days=3))
        entrega = self.programar(fecha=hoy() + timedelta(days=3))
        self.assertEqual(list(entrega.recetas.values_list("receta_id", flat=True)), [inicia.pk])

    def test_una_sola_entrega_abierta_y_el_reenvio_no_crea_otra(self):
        receta(self.paciente)
        operacion = uuid.uuid4()
        primera = self.programar(operacion=operacion)
        self.assertEqual(self.programar(operacion=operacion).pk, primera.pk)
        with self.assertRaises(EntregaAbiertaExistente) as error:
            self.programar()
        self.assertEqual(error.exception.entrega_id, primera.pk)
        self.assertEqual(Entrega.objects.count(), 1)
        self.assertEqual(IntentoEntrega.objects.count(), 1)
        with self.assertRaisesMessage(ValidationError, "no corresponde"):
            programar_entrega(self.equipo["admin"], self.paciente.pk, hoy(), self.encargado.pk, operacion)

    def test_rechazos_con_motivo_y_sin_cambios(self):
        receta(self.paciente)
        joven = paciente(edad=50)
        receta(joven)
        sin_recetas = paciente(edad=90)
        inactivo = cuenta("encargado_inactivo", self.encargado.groups.get().name, activa=False)
        casos = (
            ("fecha de ayer", lambda: self.programar(fecha=hoy() - timedelta(days=1)), "hoy o posterior"),
            ("encargado inactivo", lambda: self.programar(encargado=inactivo), "encargado de terreno"),
            ("técnico como encargado", lambda: self.programar(encargado=self.equipo["tecnico"]), "encargado de terreno"),
            ("superusuario como encargado", lambda: self.programar(encargado=self.equipo["admin"]), "encargado de terreno"),
            ("paciente no elegible", lambda: self.programar(paciente_obj=joven), "no es elegible"),
            ("sin recetas elegibles", lambda: self.programar(paciente_obj=sin_recetas), "no tiene recetas disponibles"),
            ("operación inválida", lambda: programar_entrega(self.qf, self.paciente.pk, hoy(), self.encargado.pk, "x"), "no es válida"),
        )
        for nombre, accion, mensaje in casos:
            with self.subTest(nombre), self.assertRaisesMessage(ValidationError, mensaje):
                accion()
        self.assertFalse(Entrega.objects.exists())
        self.assertFalse(RecetaEntrega.objects.exists())

    def test_solo_la_qf_y_el_superusuario_programan(self):
        receta(self.paciente)
        for actor in ("tecnico", "encargado"):
            with self.subTest(actor=actor), self.assertRaises(PermissionDenied):
                self.programar(actor=self.equipo[actor])
        self.assertEqual(self.programar(actor=self.equipo["admin"]).creado_por, self.equipo["admin"])

    def test_excepcion_vigente_permite_programar_a_un_paciente_menor(self):
        cronico = paciente(edad=60, cronico=True)
        receta(cronico)
        with self.assertRaisesMessage(ValidationError, "no es elegible"):
            self.programar(paciente_obj=cronico)
        inscribir_excepcion(self.qf, cronico.pk, "sin_red_apoyo")
        self.assertEqual(self.programar(paciente_obj=cronico).paciente, cronico)
