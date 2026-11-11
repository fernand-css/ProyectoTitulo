"""RF-08-14: matriz de permisos en el servidor, CSRF, `no-store`, URL sin datos personales y auditoría limpia."""

import uuid

from django.test import Client, TestCase
from django.urls import URLPattern, reverse

from coreapp.models import RegistroAuditoria
from entregasapp import urls as rutas
from entregasapp.models import Domicilio, Entrega, FotoDomicilio, InscripcionReparto, IntentoEntrega
from entregasapp.services import (
    guardar_domicilio, inscribir_excepcion, programar_entrega, registrar_entregada, registrar_no_entregada, verificar_domicilio,
)
from .ayudas import cuenta, equipo, hoy, paciente, receta

DOMICILIO = {"sector": "azul", "localidad": "Puertas de Virguín", "direccion": "Parcela 14, camino interior",
             "referencias": "Casa con parrón", "latitud": "-36.498765", "longitud": "-72.198765", "precision_metros": "6"}


class PermisosTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.persona = paciente(edad=87)
        receta(self.persona)
        self.domicilio = guardar_domicilio(self.equipo["encargado"], self.persona.pk, DOMICILIO)
        self.foto = FotoDomicilio.objects.create(domicilio=self.domicilio, posicion=1, archivo="domicilios/no-existe.jpg",
                                                 descripcion="Portón", ancho=10, alto=10, bytes=10)
        self.entrega = programar_entrega(self.equipo["qf"], self.persona.pk, hoy(), self.equipo["encargado"].pk, uuid.uuid4())
        self.intento = self.entrega.intentos.get()
        cronico = paciente(edad=60)
        self.inscripcion = inscribir_excepcion(self.equipo["qf"], cronico.pk, "discapacidad")
        self.vinculo = self.entrega.recetas.get()

    def rutas_get(self):
        return {
            "indice": reverse("entregasapp:indice"), "programacion": reverse("entregasapp:programacion"),
            "programar": reverse("entregasapp:programar"), "pendientes": reverse("entregasapp:pendientes"),
            "detalle": reverse("entregasapp:detalle", args=[self.entrega.pk]), "mis": reverse("entregasapp:mis"),
            "registro": reverse("entregasapp:registro", args=[self.intento.pk]),
            "domicilios": reverse("entregasapp:domicilios"),
            "domicilio": reverse("entregasapp:domicilio", args=[self.persona.pk]),
            "excepciones": reverse("entregasapp:excepciones"),
        }

    def rutas_post(self):
        return {
            "reasignar": reverse("entregasapp:reasignar", args=[self.entrega.pk]),
            "anular": reverse("entregasapp:anular", args=[self.entrega.pk]),
            "receta_revisada": reverse("entregasapp:receta_revisada", args=[self.vinculo.pk]),
            "intento_entregada": reverse("entregasapp:intento_entregada", args=[self.intento.pk]),
            "intento_no_entregada": reverse("entregasapp:intento_no_entregada", args=[self.intento.pk]),
            "domicilio": reverse("entregasapp:domicilio", args=[self.persona.pk]),
            "domicilio_verificar": reverse("entregasapp:domicilio_verificar", args=[self.domicilio.pk]),
            "foto_agregar": reverse("entregasapp:foto_agregar", args=[self.domicilio.pk]),
            "foto_eliminar": reverse("entregasapp:foto_eliminar", args=[self.foto.pk]),
            "excepciones": reverse("entregasapp:excepciones"),
            "excepcion_retirar": reverse("entregasapp:excepcion_retirar", args=[self.inscripcion.pk]),
        }

    def estado(self):
        return (
            list(Entrega.objects.values_list("estado", flat=True)),
            list(IntentoEntrega.objects.values_list("resultado", flat=True)),
            list(Domicilio.objects.values_list("version", "verificado_en")),
            FotoDomicilio.objects.count(), InscripcionReparto.objects.filter(retirada_en__isnull=True).count(),
        )

    def test_anonimo_va_a_iniciar_sesion_y_no_ejecuta_nada(self):
        antes = self.estado()
        for nombre, url in {**self.rutas_get(), "foto": reverse("entregasapp:foto", args=[self.foto.pk])}.items():
            with self.subTest(get=nombre):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn(reverse("usuariosapp:login"), respuesta["Location"])
        for nombre, url in self.rutas_post().items():
            with self.subTest(post=nombre):
                self.assertEqual(self.client.post(url, {"motivo": "otro", "nota": "x"}).status_code, 302)
        self.assertEqual(self.estado(), antes)

    def test_cuenta_inactiva_o_sin_perfil_recibe_403(self):
        from coreapp.roles import ENCARGADO, JEFA
        for usuario in (cuenta("inactiva_reparto", JEFA, activa=False), cuenta("sin_perfil_reparto", ENCARGADO, perfil=False)):
            self.client.force_login(usuario)
            for nombre, url in self.rutas_get().items():
                with self.subTest(usuario=usuario.username, ruta=nombre):
                    self.assertIn(self.client.get(url).status_code, (302, 403))
            self.client.logout()

    def test_el_tecnico_consulta_pero_cualquier_post_se_rechaza(self):
        self.client.force_login(self.equipo["tecnico"])
        for nombre in ("programacion", "pendientes", "detalle", "domicilios", "domicilio"):
            with self.subTest(get=nombre):
                respuesta = self.client.get(self.rutas_get()[nombre])
                self.assertEqual(respuesta.status_code, 200)
                self.assertIn("no-store", respuesta["Cache-Control"])
        for nombre in ("programar", "mis", "registro", "excepciones"):
            with self.subTest(prohibida=nombre):
                self.assertEqual(self.client.get(self.rutas_get()[nombre]).status_code, 403)
        antes = self.estado()
        for nombre, url in self.rutas_post().items():
            with self.subTest(post=nombre):
                self.assertEqual(self.client.post(url, {**DOMICILIO, "motivo": "otro", "nota": "x", "version": 1,
                                                        "operacion_id": uuid.uuid4(), "confirmar": "on"}).status_code, 403)
        self.assertEqual(self.estado(), antes)

    def test_el_encargado_no_entra_a_la_gestion_y_el_superusuario_no_registra_en_terreno(self):
        self.client.force_login(self.equipo["encargado"])
        for nombre in ("programacion", "programar", "pendientes", "excepciones"):
            with self.subTest(encargado=nombre):
                self.assertEqual(self.client.get(self.rutas_get()[nombre]).status_code, 403)
        self.assertEqual(self.client.get(self.rutas_get()["detalle"]).status_code, 200)  # tiene un intento ahí
        self.client.force_login(self.equipo["encargado2"])
        self.assertEqual(self.client.get(self.rutas_get()["detalle"]).status_code, 403)
        self.client.force_login(self.equipo["admin"])
        for nombre in ("mis", "registro"):
            with self.subTest(superusuario=nombre):
                self.assertEqual(self.client.get(self.rutas_get()[nombre]).status_code, 403)
        for nombre in ("intento_entregada", "domicilio_verificar"):
            with self.subTest(superusuario_post=nombre):
                self.assertEqual(self.client.post(self.rutas_post()[nombre], {"operacion_id": uuid.uuid4(), "confirmar": "on",
                                                                              "version": 1}).status_code, 403)
        for nombre in ("programacion", "programar", "pendientes", "excepciones", "domicilios"):
            with self.subTest(superusuario_gestion=nombre):
                self.assertEqual(self.client.get(self.rutas_get()[nombre]).status_code, 200)

    def test_post_sin_csrf_se_rechaza(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.equipo["encargado"])
        antes = self.estado()
        respuesta = cliente.post(self.rutas_post()["intento_entregada"], {"operacion_id": uuid.uuid4(), "confirmar": "on"})
        self.assertEqual(respuesta.status_code, 403)
        respuesta = cliente.post(self.rutas_post()["domicilio_verificar"], {"version": self.domicilio.version})
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self.estado(), antes)

    def test_todas_las_pantallas_responden_sin_cache(self):
        for actor, nombres in ((self.equipo["qf"], ("programacion", "programar", "pendientes", "detalle", "domicilios", "domicilio", "excepciones")),
                               (self.equipo["encargado"], ("mis", "registro", "domicilios", "domicilio", "detalle"))):
            self.client.force_login(actor)
            for nombre in nombres:
                with self.subTest(actor=actor.username, ruta=nombre):
                    respuesta = self.client.get(self.rutas_get()[nombre])
                    self.assertEqual(respuesta.status_code, 200)
                    self.assertIn("no-store", respuesta["Cache-Control"])
                    self.assertNotIn(self.persona.rut, respuesta.request["PATH_INFO"])

    def test_las_rutas_solo_aceptan_identificadores_internos(self):
        for patron in rutas.urlpatterns:
            self.assertIsInstance(patron, URLPattern)
            convertidores = getattr(patron.pattern, "converters", {})
            with self.subTest(ruta=str(patron.pattern)):
                self.assertTrue(all(type(c).__name__ == "IntConverter" for c in convertidores.values()))

    def test_la_auditoria_no_guarda_datos_personales(self):
        verificar_domicilio(self.equipo["encargado"], self.domicilio.pk, self.domicilio.version)
        registrar_no_entregada(self.equipo["encargado"], self.intento.pk, "otro", "Vecina de la casa roja avisa", uuid.uuid4())
        otra = paciente(edad=90)
        receta(otra)
        intento = programar_entrega(self.equipo["qf"], otra.pk, hoy(), self.equipo["encargado"].pk, uuid.uuid4()).intentos.get()
        registrar_entregada(self.equipo["encargado"], intento.pk, uuid.uuid4())
        acciones = set(RegistroAuditoria.objects.values_list("accion", flat=True))
        for accion in ("domicilio.creado", "domicilio.verificado", "reparto.excepcion_inscrita", "entrega.programada",
                       "intento.no_entregado", "intento.entregado", "receta.entrega"):
            self.assertIn(accion, acciones)
        prohibidos = [self.persona.rut, self.persona.nombres, self.persona.apellidos, self.persona.direccion,
                      DOMICILIO["direccion"], DOMICILIO["referencias"], DOMICILIO["localidad"], "-36.49", "-72.19",
                      "Vecina", otra.rut, "+56 9"]
        for registro in RegistroAuditoria.objects.all():
            texto = " ".join((registro.accion, registro.objeto_tipo, registro.objeto_id))
            for dato in prohibidos:
                self.assertNotIn(dato, texto)
