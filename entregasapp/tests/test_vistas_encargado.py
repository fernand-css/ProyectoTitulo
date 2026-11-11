"""RF-08-08 a RF-08-10 por HTTP: «Mis entregas» en el celular del encargado y registro del resultado."""

import uuid
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse

from entregasapp.models import Entrega, IntentoEntrega
from entregasapp.services import guardar_domicilio, programar_entrega
from recetasapp.models import Receta
from .ayudas import equipo, hoy, paciente, receta


class MisEntregasVistaTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.encargado = self.equipo["encargado"]
        self.client.force_login(self.encargado)

    def entrega(self, *, fecha=None, encargado=None, sector="verde"):
        persona = paciente(edad=88)
        receta(persona, maximo=12, completadas=3)
        if sector:
            guardar_domicilio(self.equipo["qf"], persona.pk, {
                "sector": sector, "localidad": "Dadinco", "direccion": "Camino a Dadinco km 2",
                "referencias": "Casa roja, portón verde", "latitud": "-36.512345", "longitud": "-72.211234",
                "precision_metros": "8"})
        entrega = programar_entrega(self.equipo["qf"], persona.pk, fecha or hoy(), (encargado or self.encargado).pk, uuid.uuid4())
        return persona, entrega, entrega.intentos.get()

    def test_hoy_atrasadas_y_proximas_con_los_datos_de_la_visita(self):
        de_hoy, _, _ = self.entrega()
        atrasado, _, intento_atrasado = self.entrega(sector="")
        IntentoEntrega.objects.filter(pk=intento_atrasado.pk).update(fecha_programada=hoy() - timedelta(days=2))
        manana, _, _ = self.entrega(fecha=hoy() + timedelta(days=1))
        ajeno, _, _ = self.entrega(encargado=self.equipo["encargado2"])
        respuesta = self.client.get(reverse("entregasapp:mis"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("no-store", respuesta["Cache-Control"])
        html = respuesta.content.decode()
        for texto in (de_hoy.apellidos, "+56 9 0000 0000", "Sector Verde · Dadinco", "Camino a Dadinco km 2",
                      "Casa roja, portón verde", "-36.512345, -72.211234 (±8 m)", "(entrega 4 de 12)",
                      "Pendiente de verificar", f"Atrasada desde el {(hoy() - timedelta(days=2)):%d/%m}",
                      atrasado.apellidos, manana.apellidos, "Próximas (1)", "Hoy (1)", "Atrasadas (1)"):
            with self.subTest(texto=texto):
                self.assertIn(texto, html)
        self.assertNotIn(ajeno.apellidos, html)
        # Las próximas no ofrecen registrar todavía.
        self.assertEqual(html.count("?resultado=entregada"), 2)

    def test_sin_entregas_lo_dice_con_texto(self):
        respuesta = self.client.get(reverse("entregasapp:mis"))
        self.assertContains(respuesta, "No tienes entregas asignadas")

    def test_el_inicio_del_encargado_abre_mis_entregas(self):
        _, _, intento = self.entrega()
        respuesta = self.client.get(reverse("coreapp:inicio"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "entregas/mis_entregas.html")
        self.assertContains(respuesta, "<h1>Mis entregas</h1>", html=False)
        self.assertContains(respuesta, reverse("entregasapp:registro", args=[intento.pk]))
        self.assertIn("no-store", respuesta["Cache-Control"])
        self.assertRedirects(self.client.get(reverse("entregasapp:indice")), reverse("entregasapp:mis"))

    def test_registrar_entregada_por_http_y_repetir_no_descuenta(self):
        _, entrega, intento = self.entrega()
        pagina = self.client.get(reverse("entregasapp:registro", args=[intento.pk]), {"resultado": "entregada"})
        self.assertContains(pagina, "Registrar entregada")
        self.assertEqual(pagina.content.decode().count('id="entregada_operacion_id"'), 1)
        operacion = str(uuid.uuid4())
        url = reverse("entregasapp:intento_entregada", args=[intento.pk])
        sin_confirmar = self.client.post(url, {"operacion_id": operacion})
        self.assertEqual(sin_confirmar.status_code, 400)
        respuesta = self.client.post(url, {"operacion_id": operacion, "confirmar": "on"}, follow=True)
        self.assertRedirects(respuesta, reverse("entregasapp:mis"))
        self.assertContains(respuesta, "Se descontaron 1 de 1 receta(s).")
        repetida = self.client.post(url, {"operacion_id": operacion, "confirmar": "on"}, follow=True)
        self.assertContains(repetida, "ya estaba registrada")
        self.assertEqual(Receta.objects.get().entregas_completadas, 4)
        entrega.refresh_from_db()
        self.assertEqual(entrega.estado, "entregada")

    def test_registrar_no_entregada_exige_motivo_y_nota_con_otro(self):
        _, entrega, intento = self.entrega()
        url = reverse("entregasapp:intento_no_entregada", args=[intento.pk])
        sin_motivo = self.client.post(url, {"operacion_id": uuid.uuid4()})
        self.assertEqual(sin_motivo.status_code, 400)
        otro = self.client.post(url, {"operacion_id": uuid.uuid4(), "motivo": "otro", "nota": ""})
        self.assertContains(otro, "escribe una nota breve", status_code=400)
        ok = self.client.post(url, {"operacion_id": uuid.uuid4(), "motivo": "sin_receptor"})
        self.assertRedirects(ok, reverse("entregasapp:mis"))
        entrega.refresh_from_db()
        self.assertEqual(entrega.estado, "pendiente_gestion")

    def test_intento_de_otro_encargado_o_de_manana_no_se_registra(self):
        _, _, ajeno = self.entrega(encargado=self.equipo["encargado2"])
        for nombre in ("registro", "intento_entregada", "intento_no_entregada"):
            with self.subTest(nombre=nombre):
                metodo = self.client.get if nombre == "registro" else self.client.post
                self.assertEqual(metodo(reverse(f"entregasapp:{nombre}", args=[ajeno.pk]),
                                        {"operacion_id": uuid.uuid4(), "confirmar": "on"}).status_code, 403)
        _, _, manana = self.entrega(fecha=hoy() + timedelta(days=1))
        pagina = self.client.get(reverse("entregasapp:registro", args=[manana.pk]))
        self.assertContains(pagina, "Podrás registrarla desde ese día")
        self.assertNotContains(pagina, "Registrar entregada")
        respuesta = self.client.post(reverse("entregasapp:intento_entregada", args=[manana.pk]),
                                     {"operacion_id": uuid.uuid4(), "confirmar": "on"})
        self.assertContains(respuesta, "Regístrala desde ese día", status_code=400)
        self.assertEqual(Entrega.objects.filter(estado="programada").count(), 2)
