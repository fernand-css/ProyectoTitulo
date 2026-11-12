"""RF-09-13: domicilios sintéticos de demostración, reproducibles y auditados, solo con --aplicar y una cuenta Q.F."""

import io

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from coreapp.models import RegistroAuditoria
from entregasapp.models import Domicilio, Entrega
from entregasapp.ruta import Punto, distancia_m
from entregasapp.services import guardar_domicilio
from .ayudas import equipo, paciente


class GenerarDomiciliosDemoTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.elegibles = [paciente(edad=85) for _ in range(4)] + [paciente(edad=60, postrado=True)]
        self.no_elegible = paciente(edad=60)
        self.existente = guardar_domicilio(self.equipo["qf"], self.elegibles[0].pk, {
            "sector": "verde", "direccion": "Dirección sintética previa", "referencias": "Sin cambios"})

    def ejecutar(self, *argumentos):
        salida = io.StringIO()
        call_command("generar_domicilios_demo", *argumentos, stdout=salida)
        return salida.getvalue()

    def test_sin_aplicar_solo_informa(self):
        auditorias = RegistroAuditoria.objects.count()
        texto = self.ejecutar()
        self.assertIn("Simulación: se crearían 4 domicilios", texto)
        self.assertIn("La base no fue modificada", texto)
        self.assertEqual(Domicilio.objects.count(), 1)
        self.assertEqual(RegistroAuditoria.objects.count(), auditorias)
        self.assertEqual(self.ejecutar("--cuenta", self.equipo["qf"].username).count("Simulación"), 1)

    def test_aplicar_crea_domicilios_sinteticos_dentro_del_radio_sin_verificar_y_auditados(self):
        texto = self.ejecutar("--aplicar", "--cuenta", self.equipo["qf"].username, "--radio-km", "5")
        self.assertIn("Domicilios sintéticos creados: 4; omitidos: 0", texto)
        origen = Punto("origen", settings.REPARTO_ORIGEN_LATITUD, settings.REPARTO_ORIGEN_LONGITUD)
        nuevos = Domicilio.objects.exclude(pk=self.existente.pk)
        self.assertEqual({d.paciente_id for d in nuevos}, {p.pk for p in self.elegibles[1:]})
        for domicilio in nuevos:
            with self.subTest(domicilio=domicilio.pk):
                self.assertLessEqual(distancia_m(origen, Punto(0, float(domicilio.latitud), float(domicilio.longitud))), 5000 + 1)
                self.assertIsNone(domicilio.verificado_en)
                self.assertIn(domicilio.sector, ("verde", "azul", "rojo"))
                self.assertRegex(domicilio.localidad, r"^Localidad demo \d+$")
                self.assertIn("demostración", domicilio.direccion)
                self.assertIn("demostración", domicilio.referencias)
                self.assertEqual(domicilio.creado_por, self.equipo["qf"])
                self.assertTrue(RegistroAuditoria.objects.filter(accion="domicilio.creado", objeto_id=str(domicilio.pk),
                                                                 usuario=self.equipo["qf"]).exists())
        self.existente.refresh_from_db()
        self.assertEqual((self.existente.direccion, self.existente.latitud), ("Dirección sintética previa", None))
        self.assertFalse(Domicilio.objects.filter(paciente=self.no_elegible).exists())
        self.assertFalse(Entrega.objects.exists())

    def test_repetir_con_la_misma_semilla_no_toca_los_existentes_y_es_reproducible(self):
        self.ejecutar("--aplicar", "--cuenta", self.equipo["qf"].username, "--semilla", "7")
        primero = {d.paciente_id: (d.latitud, d.longitud, d.sector, d.direccion) for d in Domicilio.objects.all()}
        versiones = list(Domicilio.objects.order_by("pk").values_list("version", "modificado_en"))
        texto = self.ejecutar("--aplicar", "--cuenta", self.equipo["admin"].username, "--semilla", "7")
        self.assertIn("Domicilios sintéticos creados: 0", texto)
        self.assertEqual(list(Domicilio.objects.order_by("pk").values_list("version", "modificado_en")), versiones)
        # Con la misma semilla, cada paciente recibe el mismo domicilio (aquí se borra solo en la base de pruebas).
        Domicilio.objects.exclude(pk=self.existente.pk).delete()
        self.ejecutar("--aplicar", "--cuenta", self.equipo["admin"].username, "--semilla", "7")
        self.assertEqual({d.paciente_id: (d.latitud, d.longitud, d.sector, d.direccion) for d in Domicilio.objects.all()}, primero)

    def test_rechaza_cuentas_sin_permiso_y_aplicar_sin_cuenta(self):
        for argumentos in (("--aplicar",), ("--aplicar", "--cuenta", self.equipo["tecnico"].username),
                           ("--aplicar", "--cuenta", self.equipo["encargado"].username),
                           ("--aplicar", "--cuenta", "no_existe"), ("--radio-km", "0")):
            with self.subTest(argumentos=argumentos), self.assertRaises(CommandError):
                self.ejecutar(*argumentos)
        self.assertEqual(Domicilio.objects.count(), 1)
