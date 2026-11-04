"""Ficha del paciente con pestañas: Recetas, Entregas y Datos, cada una en su propia dirección."""

import re
from datetime import date, datetime
from random import Random
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from coreapp.utils.sinteticos import generar_ruts
from recetasapp.models import EntregaReceta, Paciente
from recetasapp.services import crear_receta
from .ayudas import actores

HOY = date(2026, 11, 2)


@override_settings(SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class FichaConPestanasTests(TestCase):
    def setUp(self):
        reloj = patch("recetasapp.services.timezone.localdate", return_value=HOY)
        reloj.start()
        self.addCleanup(reloj.stop)
        self.actores = actores()
        self.ruts = iter(generar_ruts(10, Random(21)))
        self.paciente = self.nuevo("Ana", telefono="+56 9 5555 0001", direccion="Dadinco, km 2, casa roja", es_cronico=True)
        self.vigente = self.receta(self.paciente, "FICHA-1", date(2026, 6, 1))
        self.vencida = self.receta(self.paciente, "FICHA-0", date(2025, 1, 1))
        self.client.force_login(self.actores["tecnico"])

    def nuevo(self, nombre, **campos):
        return Paciente.objects.create(rut=next(self.ruts), nombres=nombre, apellidos="Sintética", fecha_nacimiento=date(1950, 1, 1), **campos)

    def receta(self, paciente, codigo, inicio):
        return crear_receta(self.actores["qf"], paciente_id=paciente.pk, codigo=codigo, fecha_inicio=inicio, vigencia_meses=6, max_entregas=6)

    def entrega(self, receta, numero, dia, responsable="tecnico"):
        entrega = EntregaReceta.objects.create(receta=receta, numero=numero, creado_por=self.actores[responsable])
        EntregaReceta.objects.filter(pk=entrega.pk).update(creado_en=timezone.make_aware(datetime(2026, 10, dia, 10, 30)))
        return entrega

    def ficha(self, **parametros):
        return self.client.get(reverse("recetasapp:paciente_detalle", args=[self.paciente.pk]), parametros)

    def pestanas(self, respuesta):
        html = respuesta.content.decode()
        inicio = html.index('aria-label="Secciones de la ficha del paciente"')
        bloque = html[inicio:html.index("</nav>", inicio)]
        return [(m.group(1), 'aria-current="page"' in m.group(0)) for m in re.finditer(r'<a href="([^"]+)"[^>]*>', bloque)], bloque

    def test_abre_en_recetas_y_ofrece_tres_pestanas_con_su_propia_direccion(self):
        base = reverse("recetasapp:paciente_detalle", args=[self.paciente.pk])
        respuesta = self.ficha()
        enlaces, bloque = self.pestanas(respuesta)
        self.assertEqual(enlaces, [(base, True), (f"{base}?pestana=entregas", False), (f"{base}?pestana=datos", False)])
        self.assertRegex(bloque, r'Recetas <span class="pestana-cantidad">2</span>')
        self.assertRegex(bloque, r'Entregas <span class="pestana-cantidad">0</span>')
        self.assertContains(respuesta, "Receta FICHA-1")
        self.assertContains(respuesta, "1</strong> vigente de 2 recetas")
        self.assertEqual(respuesta.context["pestana"], "recetas")

    def test_las_recetas_vigentes_van_primero(self):
        recetas = self.ficha().context["recetas"]
        self.assertEqual([r.codigo for r in recetas], ["FICHA-1", "FICHA-0"])

    def test_la_pestana_entregas_lista_de_la_mas_reciente_a_la_mas_antigua_con_su_responsable(self):
        self.entrega(self.vigente, 1, 5)
        self.entrega(self.vigente, 2, 20, responsable="qf")
        respuesta = self.ficha(pestana="entregas")
        enlaces, bloque = self.pestanas(respuesta)
        self.assertEqual([actual for _, actual in enlaces], [False, True, False])
        self.assertRegex(bloque, r'Entregas <span class="pestana-cantidad">2</span>')
        self.assertEqual([e.numero for e in respuesta.context["entregas"]], [2, 1])
        html = respuesta.content.decode()
        self.assertIn("20 oct 2026, 10:30", html)
        self.assertIn("2 de 6", html)
        self.assertIn("sintetico_qf", html)
        self.assertIn(reverse("recetasapp:receta_detalle", args=[self.vigente.pk]), html)
        self.assertNotIn("Cuando el Técnico selle", html)

    def test_la_pestana_entregas_sin_entregas_lo_explica(self):
        respuesta = self.ficha(pestana="entregas")
        self.assertContains(respuesta, "Aún no hay entregas confirmadas")
        self.assertEqual(respuesta.context["entregas"], [])

    def test_la_ficha_no_mezcla_las_entregas_de_otro_paciente(self):
        otra = self.nuevo("Berta")
        receta = self.receta(otra, "OTRA-1", date(2026, 6, 1))
        self.entrega(receta, 1, 6)
        self.assertEqual(self.ficha(pestana="entregas").context["entregas"], [])
        self.assertNotContains(self.ficha(pestana="entregas"), "OTRA-1")

    def test_la_pestana_datos_muestra_los_datos_de_contacto_y_la_condicion(self):
        respuesta = self.ficha(pestana="datos")
        self.assertContains(respuesta, "Dadinco, km 2, casa roja")
        self.assertContains(respuesta, "+56 9 5555 0001")
        self.assertContains(respuesta, "1 de enero de 1950")
        self.assertContains(respuesta, "<dd>Crónico</dd>")
        self.assertNotContains(respuesta, "Receta FICHA-1")
        sin_datos = self.nuevo("Carla")
        respuesta = self.client.get(reverse("recetasapp:paciente_detalle", args=[sin_datos.pk]), {"pestana": "datos"})
        self.assertContains(respuesta, "No registrado")
        self.assertContains(respuesta, "No registrada")
        self.assertContains(respuesta, "Sin condición registrada")

    def test_una_pestana_desconocida_abre_recetas(self):
        for valor in ("inventada", "", "Entregas", "../datos"):
            with self.subTest(pestana=valor):
                self.assertEqual(self.ficha(pestana=valor).context["pestana"], "recetas")

    def test_el_rut_aparece_una_sola_vez_y_en_el_encabezado_en_cada_pestana(self):
        for valor in ("", "entregas", "datos"):
            with self.subTest(pestana=valor):
                html = self.ficha(pestana=valor).content.decode()
                self.assertEqual(html.count("RUT "), 1)

    def test_las_migas_y_el_menu_dicen_pacientes(self):
        html = self.ficha().content.decode()
        self.assertIn(f'<li><a href="{reverse("recetasapp:pacientes")}">Pacientes</a></li>', html)
        self.assertNotIn(">Padrón<", html)
        self.assertIn("Sintética", html)

    def test_solo_quien_puede_crear_ve_el_boton_crear_receta(self):
        nueva = reverse("recetasapp:receta_nueva")
        self.assertNotContains(self.ficha(), f'href="{nueva}"')
        self.client.force_login(self.actores["qf"])
        self.assertContains(self.ficha(), f'href="{nueva}"')

    def test_el_encargado_no_entra_a_ninguna_pestana(self):
        self.client.force_login(self.actores["encargado"])
        for valor in ("", "entregas", "datos"):
            self.assertEqual(self.ficha(pestana=valor).status_code, 403)
