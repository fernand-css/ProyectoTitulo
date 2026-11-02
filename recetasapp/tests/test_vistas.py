"""Permisos por URL, formularios, navegación y protección CSRF."""

import uuid
from datetime import date
from unittest.mock import patch

from django.contrib import admin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from coreapp.tests.test_plantillas import DocumentoHTML
from recetasapp.importacion import generar_archivo
from recetasapp.models import EntregaReceta, ImportacionPadron, Paciente, Receta, ResultadoFilaImportacion
from .ayudas import actores, cargar, fila


@override_settings(SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class VistasTests(TestCase):
    def setUp(self):
        reloj = patch("recetasapp.services.timezone.localdate", return_value=date(2026, 11, 2))
        reloj.start()
        self.addCleanup(reloj.stop)
        self.actores = actores()
        self.carga = cargar(self.actores["qf"], [fila()])
        self.receta = Receta.objects.get()
        self.consultas = [reverse("recetasapp:pacientes"), reverse("recetasapp:paciente_detalle", args=[self.receta.paciente_id]), reverse("recetasapp:receta_detalle", args=[self.receta.pk])]
        self.gestion = [reverse("recetasapp:receta_nueva"), reverse("recetasapp:receta_renovar", args=[self.receta.pk]), reverse("recetasapp:importaciones"), reverse("recetasapp:importacion_nueva"), reverse("recetasapp:importacion_detalle", args=[self.carga.referencia]), reverse("recetasapp:plantilla", args=["csv"]), reverse("recetasapp:plantilla", args=["xlsx"])]
        self.entrega = reverse("recetasapp:entrega_confirmar", args=[self.receta.pk])

    def test_matriz_get_y_post_directo(self):
        for nombre, usuario in self.actores.items():
            self.client.force_login(usuario)
            for ruta in self.consultas:
                self.assertEqual(self.client.get(ruta).status_code, 403 if nombre == "encargado" else 200)
            for ruta in self.gestion:
                self.assertEqual(self.client.get(ruta).status_code, 200 if nombre in ("qf", "admin") else 403)
            self.assertEqual(self.client.get(self.entrega).status_code, 200 if nombre in ("tecnico", "admin") else 403)
            if nombre in ("encargado", "qf"):
                self.assertEqual(self.client.post(self.entrega, {"confirmar": "on", "operacion_id": uuid.uuid4()}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.consultas[0]).status_code, 302)

    def test_busqueda_post_y_paginacion_no_exponen_rut_en_url(self):
        self.client.force_login(self.actores["tecnico"])
        respuesta = self.client.post(self.consultas[0], {"buscar": fila()[0], "pagina": 1})
        self.assertContains(respuesta, fila()[1])
        self.assertEqual(respuesta["Cache-Control"].find("no-store") >= 0, True)
        self.assertNotIn(fila()[0], respuesta.wsgi_request.get_full_path())
        self.assertEqual(respuesta["Referrer-Policy"], "same-origin")

    def test_importacion_no_suprime_origen_del_formulario(self):
        self.client.force_login(self.actores["qf"])
        respuesta = self.client.get(reverse("recetasapp:importacion_nueva"))
        self.assertEqual(respuesta["Referrer-Policy"], "same-origin")

    def test_importacion_multipart_csrf_origen_http_https_y_referente(self):
        ruta = reverse("recetasapp:importacion_nueva")
        for secure in (False, True):
            for formato in ("csv", "xlsx"):
                with self.subTest(secure=secure, formato=formato):
                    cliente = Client(enforce_csrf_checks=True)
                    cliente.force_login(self.actores["qf"])
                    self.assertEqual(cliente.get(ruta, secure=secure).status_code, 200)
                    origen = ("https" if secure else "http") + "://testserver"
                    token = cliente.cookies["csrftoken"].value

                    def enviar(cabeceras, incluir_token=True):
                        datos = {
                            "formato": formato, "sintetico": "on",
                            "archivo": SimpleUploadedFile("sintetico." + formato, generar_archivo(formato, [fila()])),
                        }
                        if incluir_token:
                            datos["csrfmiddlewaretoken"] = token
                        return cliente.post(ruta, datos, secure=secure, **cabeceras)

                    previas = ImportacionPadron.objects.count()
                    for origen_invalido in ("null", "https://otro.example.invalid"):
                        self.assertEqual(enviar({"HTTP_ORIGIN": origen_invalido}).status_code, 403)
                    self.assertEqual(enviar({"HTTP_ORIGIN": origen}, incluir_token=False).status_code, 403)
                    self.assertEqual(ImportacionPadron.objects.count(), previas)
                    self.assertEqual(enviar({"HTTP_ORIGIN": origen}).status_code, 302)
                    self.assertEqual(ImportacionPadron.objects.count(), previas + 1)
                    if secure:
                        self.assertEqual(enviar({"HTTP_REFERER": origen + ruta}).status_code, 302)

    def test_creacion_renovacion_entrega_y_uuid_repetido(self):
        self.client.force_login(self.actores["qf"])
        datos = {"paciente": self.receta.paciente_id, "codigo": "WEB-NUEVA", "fecha_inicio": "2026-01-01", "vigencia_meses": 12, "max_entregas": 2}
        respuesta = self.client.post(reverse("recetasapp:receta_nueva"), datos)
        self.assertEqual(respuesta.status_code, 302)
        datos["codigo"] = "WEB-RENOVADA"
        datos["paciente"] = 999999
        respuesta = self.client.post(reverse("recetasapp:receta_renovar", args=[self.receta.pk]), datos)
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Receta.objects.get(codigo="WEB-RENOVADA").paciente_id, self.receta.paciente_id)
        self.client.force_login(self.actores["tecnico"])
        operacion = str(uuid.uuid4())
        for _ in range(2):
            self.assertEqual(self.client.post(self.entrega, {"operacion_id": operacion, "confirmar": "on"}).status_code, 302)
        self.assertEqual(EntregaReceta.objects.count(), 1)

    def test_csrf_real_y_get_no_cambia_estado(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.actores["tecnico"])
        self.assertEqual(cliente.get(self.entrega).status_code, 200)
        datos = {"operacion_id": str(uuid.uuid4()), "confirmar": "on"}
        self.assertEqual(cliente.post(self.entrega, datos).status_code, 403)
        self.assertEqual(EntregaReceta.objects.count(), 0)
        datos["csrfmiddlewaretoken"] = cliente.cookies["csrftoken"].value
        self.assertEqual(cliente.post(self.entrega, datos).status_code, 302)

    def test_confirmacion_invalida_informa_error_y_conserva_estado(self):
        self.client.force_login(self.actores["tecnico"])
        respuesta = self.client.post(self.entrega, {"operacion_id": "invalido", "confirmar": "on"})
        self.assertContains(respuesta, 'role="alert"')
        self.assertContains(respuesta, "UUID")
        self.assertFalse(EntregaReceta.objects.exists())

    def test_carga_multipart_reporte_y_rechazo_no_expone_datos(self):
        self.client.force_login(self.actores["qf"])
        archivo = SimpleUploadedFile("sintetico.csv", generar_archivo("csv", [fila(), ["VALOR PRIVADO"]]))
        respuesta = self.client.post(reverse("recetasapp:importacion_nueva"), {"formato": "csv", "sintetico": "on", "archivo": archivo}, follow=True)
        self.assertContains(respuesta, "Reporte de importación")
        self.assertContains(respuesta, "Rechazada")
        self.assertNotContains(respuesta, "VALOR PRIVADO")

    def test_formularios_accesibles_ids_unicos_y_html_escapado(self):
        self.client.force_login(self.actores["admin"])
        for ruta in self.gestion[:2] + [reverse("recetasapp:importacion_nueva"), self.entrega, self.consultas[0]]:
            respuesta = self.client.get(ruta)
            elementos = DocumentoHTML(respuesta.content.decode()).elementos
            ids = [a["id"] for _, a in elementos if "id" in a]
            self.assertEqual(len(ids), len(set(ids)), ruta)
            etiquetas = {a["for"] for e, a in elementos if e == "label" and "for" in a}
            for elemento, atributos in elementos:
                if elemento in ("input", "select", "textarea") and atributos.get("type") != "hidden":
                    self.assertIn(atributos.get("id"), etiquetas)
            self.assertEqual(sum(1 for e, _ in elementos if e == "main"), 1)
        paciente = Paciente.objects.get()
        paciente.nombres = "<script>alert('sintetico')</script>"
        paciente.save()
        respuesta = self.client.get(self.consultas[1])
        self.assertNotContains(respuesta, paciente.nombres)
        self.assertContains(respuesta, "&lt;script&gt;")

    def test_admin_no_ofrece_escritura_de_dominio(self):
        for modelo in (Paciente, Receta, EntregaReceta, ImportacionPadron, ResultadoFilaImportacion):
            self.assertNotIn(modelo, admin.site._registry)

    def test_cuenta_desactivada_y_sin_perfil_no_acceden(self):
        usuario = self.actores["tecnico"]
        self.client.force_login(usuario)
        usuario.is_active = False
        usuario.save()
        self.assertIn(self.client.get(self.consultas[0]).status_code, (302, 403))
        usuario.is_active = True
        usuario.save()
        self.client.force_login(usuario)
        usuario.perfil.delete()
        self.assertEqual(self.client.get(self.consultas[0]).status_code, 403)
