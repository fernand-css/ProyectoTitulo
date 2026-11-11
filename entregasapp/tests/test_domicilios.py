"""RF-08-03 y RF-08-04: registro del domicilio, edición por versión, verificación y aviso del padrón."""

from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from coreapp.models import RegistroAuditoria
from entregasapp.consultas import estado_domicilio
from entregasapp.models import Domicilio
from entregasapp.services import guardar_domicilio, verificar_domicilio
from recetasapp.models import Paciente
from recetasapp.tests.ayudas import cargar
from .ayudas import equipo, paciente

DATOS = {"sector": "verde", "localidad": "Dadinco", "direccion": "Camino a Dadinco km 2, casa roja",
         "referencias": "Portón verde junto al paradero", "latitud": "", "longitud": "", "precision_metros": ""}


class DomicilioTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.encargado = self.equipo["encargado"]
        self.paciente = paciente(edad=85)

    def estado(self):
        # Paciente recién leído: la caché de la relación inversa no debe ocultar cambios.
        return estado_domicilio(Paciente.objects.get(pk=self.paciente.pk))

    def crear(self, actor=None, **cambios):
        return guardar_domicilio(actor or self.encargado, self.paciente.pk, {**DATOS, **cambios})

    def test_crea_desde_el_padron_y_recuerda_la_direccion_de_origen(self):
        domicilio = self.crear(direccion=self.paciente.direccion)
        self.assertEqual(domicilio.direccion_padron, self.paciente.direccion)
        self.assertEqual(domicilio.version, 1)
        self.assertEqual((domicilio.creado_por, domicilio.modificado_por), (self.encargado, self.encargado))
        self.assertEqual(self.estado().clave, "pendiente")
        registro = RegistroAuditoria.objects.get(accion="domicilio.creado")
        self.assertEqual((registro.objeto_tipo, registro.objeto_id), ("entregasapp.Domicilio", str(domicilio.pk)))

    def test_sin_domicilio_figura_sin_registrar(self):
        estado = self.estado()
        self.assertEqual((estado.clave, estado.texto), ("sin_registrar", "Sin registrar"))

    def test_roles_que_pueden_guardar_y_paciente_no_elegible(self):
        with self.assertRaises(PermissionDenied):
            self.crear(self.equipo["tecnico"])
        self.crear(self.equipo["qf"])
        otro = paciente(edad=85)
        guardar_domicilio(self.equipo["admin"], otro.pk, DATOS)
        joven = paciente(edad=40)
        with self.assertRaises(ValidationError):
            guardar_domicilio(self.encargado, joven.pk, DATOS)
        self.assertFalse(Domicilio.objects.filter(paciente=joven).exists())

    def test_coordenadas_juntas_y_en_rango(self):
        with self.assertRaises(ValidationError):
            self.crear(latitud="-36.5")
        with self.assertRaises(ValidationError):
            self.crear(latitud="-95", longitud="-72.2")
        with self.assertRaises(ValidationError):
            self.crear(latitud="abc", longitud="-72.2")
        domicilio = self.crear(latitud="-36.5123456", longitud="-72.211234", precision_metros="8")
        self.assertEqual((domicilio.latitud, domicilio.longitud, domicilio.precision_metros),
                         (Decimal("-36.512346"), Decimal("-72.211234"), 8))

    def test_edicion_por_version_no_sobrescribe_un_cambio_ajeno(self):
        domicilio = self.crear()
        guardar_domicilio(self.equipo["qf"], self.paciente.pk, {**DATOS, "referencias": "Casa con parrón"}, version=1)
        with self.assertRaisesMessage(ValidationError, "El domicilio cambió; revisa los datos nuevos."):
            guardar_domicilio(self.encargado, self.paciente.pk, {**DATOS, "referencias": "Otra referencia"}, version=1)
        with self.assertRaisesMessage(ValidationError, "El domicilio cambió; revisa los datos nuevos."):
            guardar_domicilio(self.encargado, self.paciente.pk, DATOS)  # sin versión: creía que no existía
        domicilio.refresh_from_db()
        self.assertEqual((domicilio.referencias, domicilio.version), ("Casa con parrón", 2))

    def test_verificar_exige_sector_y_solo_lo_hace_el_encargado(self):
        domicilio = self.crear(sector="")
        with self.assertRaisesMessage(ValidationError, "sector"):
            verificar_domicilio(self.encargado, domicilio.pk, domicilio.version)
        domicilio = guardar_domicilio(self.encargado, self.paciente.pk, DATOS, version=domicilio.version)
        for actor in (self.equipo["qf"], self.equipo["admin"], self.equipo["tecnico"], AnonymousUser()):
            with self.subTest(actor=getattr(actor, "username", "anónimo")), self.assertRaises(PermissionDenied):
                verificar_domicilio(actor, domicilio.pk, domicilio.version)
        domicilio.refresh_from_db()
        self.assertIsNone(domicilio.verificado_en)
        domicilio = verificar_domicilio(self.encargado, domicilio.pk, domicilio.version)
        self.assertEqual(domicilio.verificado_por, self.encargado)
        self.assertIsNotNone(domicilio.verificado_en)
        self.assertEqual(self.estado().clave, "verificado")
        self.assertTrue(RegistroAuditoria.objects.filter(accion="domicilio.verificado", objeto_id=str(domicilio.pk)).exists())

    def test_cambiar_la_ubicacion_vuelve_a_pendiente_y_la_precision_o_las_fotos_no(self):
        domicilio = self.crear(latitud="-36.5", longitud="-72.2", precision_metros="10")
        domicilio = verificar_domicilio(self.encargado, domicilio.pk, domicilio.version)
        domicilio = guardar_domicilio(self.encargado, self.paciente.pk,
                                      {**DATOS, "latitud": "-36.5", "longitud": "-72.2", "precision_metros": "4"}, version=domicilio.version)
        self.assertIsNotNone(domicilio.verificado_en)  # la precisión sola no cambia la ubicación
        domicilio = guardar_domicilio(self.encargado, self.paciente.pk,
                                      {**DATOS, "latitud": "-36.5", "longitud": "-72.2", "precision_metros": "4"}, version=domicilio.version)
        self.assertIsNotNone(domicilio.verificado_en)  # guardar sin cambios conserva la verificación
        for campo, valor in (("referencias", "Casa amarilla"), ("sector", "azul"), ("localidad", "Puertas de Virguín"),
                             ("direccion", "Camino a Dadinco km 3"), ("latitud", "-36.6")):
            with self.subTest(campo=campo):
                domicilio = verificar_domicilio(self.encargado, domicilio.pk, domicilio.version)
                datos = {**DATOS, "latitud": "-36.5", "longitud": "-72.2", campo: valor}
                domicilio = guardar_domicilio(self.equipo["qf"], self.paciente.pk, datos, version=domicilio.version)
                self.assertIsNone(domicilio.verificado_en)
                self.assertIsNone(domicilio.verificado_por)
                self.assertEqual(self.estado().clave, "pendiente")

    def test_la_importacion_no_toca_el_domicilio_y_deja_el_aviso_del_padron(self):
        p = self.paciente
        domicilio = self.crear(direccion=p.direccion)
        domicilio = verificar_domicilio(self.encargado, domicilio.pk, domicilio.version)
        fila = [p.rut, p.nombres, p.apellidos, p.fecha_nacimiento.isoformat(), "0", "0", p.telefono,
                "Sector El Sauce, parcela 14", "", "", "", ""]
        cargar(self.equipo["qf"], [fila])
        p.refresh_from_db()
        self.assertEqual(p.direccion, "Sector El Sauce, parcela 14")
        antes = Domicilio.objects.values().get(pk=domicilio.pk)
        estado = self.estado()
        self.assertEqual((estado.clave, estado.padron_cambio, estado.direccion_padron),
                         ("pendiente", True, "Sector El Sauce, parcela 14"))
        self.assertEqual(antes["direccion"], DATOS["direccion"])
        self.assertEqual(antes["direccion_padron"], "Camino a Dadinco km 2, casa roja")
        self.assertIsNotNone(antes["verificado_en"])
        # Guardar de nuevo reconoce la dirección nueva del padrón y quita el aviso, pero no verifica.
        domicilio = guardar_domicilio(self.encargado, p.pk, DATOS, version=domicilio.version)
        estado = self.estado()
        self.assertEqual((estado.clave, estado.padron_cambio), ("pendiente", False))
        self.assertEqual(domicilio.direccion_padron, "Sector El Sauce, parcela 14")
        verificar_domicilio(self.encargado, domicilio.pk, domicilio.version)
        self.assertEqual(self.estado().clave, "verificado")

    def test_si_falla_la_auditoria_no_se_guarda_nada(self):
        with patch("entregasapp.services.auditar", side_effect=RuntimeError("auditoría")), self.assertRaises(RuntimeError):
            self.crear()
        self.assertFalse(Domicilio.objects.exists())
        domicilio = self.crear()
        with patch("entregasapp.services.auditar", side_effect=RuntimeError("auditoría")), self.assertRaises(RuntimeError):
            verificar_domicilio(self.encargado, domicilio.pk, domicilio.version)
        domicilio.refresh_from_db()
        self.assertEqual((domicilio.version, domicilio.verificado_en), (1, None))

    def test_la_auditoria_no_guarda_datos_personales(self):
        domicilio = self.crear(latitud="-36.5", longitud="-72.2")
        verificar_domicilio(self.encargado, domicilio.pk, domicilio.version)
        for registro in RegistroAuditoria.objects.all():
            texto = f"{registro.accion} {registro.objeto_tipo} {registro.objeto_id}"
            for dato in (self.paciente.rut, self.paciente.nombres, self.paciente.apellidos, DATOS["direccion"], "Dadinco", "-36.5"):
                self.assertNotIn(dato, texto)
