"""Dashboard, descargas, derivación por la interfaz y rol Director del CESFAM (RF-13-08 a RF-13-22)."""

import io
import uuid
import zipfile
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse

from coreapp.models import RegistroAuditoria
from coreapp.navegacion import armar_menu
from coreapp.roles import DIRECTOR, JEFA, ROLES_INTERNOS
from entregasapp.models import Entrega
from usuariosapp.services import crear_roles
from .ayudas import cuenta, equipo, hoy, paciente, preparada

PANEL = reverse("indicadoresapp:mermas")


class AccesoTests(TestCase):
    def setUp(self):
        self.e = equipo()
        self.director = cuenta("director", DIRECTOR)

    def test_panel_por_rol(self):
        esperado = {"qf": 200, "admin": 200, "tecnico": 403, "encargado": 403}
        for rol, codigo in esperado.items():
            self.client.force_login(self.e[rol])
            self.assertEqual(self.client.get(PANEL).status_code, codigo, rol)
        self.client.force_login(self.director)
        respuesta = self.client.get(PANEL)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("no-store", respuesta["Cache-Control"])
        self.client.logout()
        self.assertEqual(self.client.get(PANEL).status_code, 302)

    def test_inicio_del_director_es_el_panel_y_el_resto_403(self):
        self.client.force_login(self.director)
        inicio = self.client.get("/")
        self.assertEqual(inicio.status_code, 200)
        self.assertContains(inicio, "Mermas y entregas")
        for ruta in ("/recetas/", "/recetas/pacientes/", "/turnos/panel/", "/entregas/", "/usuarios/gestion/",
                     reverse("indicadoresapp:mermas_derivar", args=[paciente().pk])):
            self.assertEqual(self.client.get(ruta).status_code, 403, ruta)

    def test_menu_del_director_solo_mermas_y_perfil(self):
        menu = armar_menu(DIRECTOR)
        claves = [opcion.clave for grupo in menu.grupos for opcion in grupo.opciones]
        self.assertEqual(claves, ["mermas"])
        self.assertIsNotNone(menu.perfil)
        self.assertIn("mermas", [o.clave for g in armar_menu(JEFA).grupos for o in g.opciones])

    def test_crear_roles_crea_cuatro_grupos(self):
        self.assertEqual(set(crear_roles()), set(ROLES_INTERNOS))
        self.assertIn(DIRECTOR, ROLES_INTERNOS)

    def test_la_qf_no_ve_ni_gestiona_cuentas_de_director(self):
        from usuariosapp.services import cuentas_gestionables

        self.assertNotIn(self.director, cuentas_gestionables(self.e["qf"]))
        self.client.force_login(self.e["qf"])
        respuesta = self.client.get(reverse("usuariosapp:gestion_usuarios"))
        self.assertNotContains(respuesta, self.director.username)


class PanelTests(TestCase):
    def setUp(self):
        self.e = equipo()
        self.director = cuenta("director_panel", DIRECTOR)
        self.persona = paciente(edad=85, cronico=True)
        preparada(self.persona, usuario=self.e["tecnico"])

    def test_dashboard_sin_datos_personales_para_ningun_rol(self):
        for usuario in (self.e["qf"], self.director):
            self.client.force_login(usuario)
            respuesta = self.client.get(PANEL)
            self.assertContains(respuesta, "Mermas y entregas")
            for texto in ("Recetas entregadas", "Entregas por canal", "Por qué no se entregó", "Entregas por día",
                          "Qué pasó con las recetas preparadas", "Cuánto llevan en el estante", "Crónico y general",
                          "Ausentes por día y hora", "Descargar CSV"):
                self.assertContains(respuesta, texto)
            for dato in (self.persona.rut, self.persona.rut.split("-")[0], self.persona.nombres, self.persona.apellidos):
                self.assertNotContains(respuesta, dato)
            self.assertNotContains(respuesta, "Detalle por paciente")
            self.assertNotContains(respuesta, "alveolo")

    def test_enlace_a_pendientes_solo_para_la_qf(self):
        pendientes = reverse("recetasapp:preparacion_pendientes")
        self.client.force_login(self.e["qf"])
        self.assertContains(self.client.get(PANEL), f'href="{pendientes}"')
        self.client.force_login(self.director)
        self.assertNotContains(self.client.get(PANEL), f'href="{pendientes}"')

    def test_ocho_periodos_y_el_mes_por_omision(self):
        self.client.force_login(self.e["qf"])
        respuesta = self.client.get(PANEL)
        self.assertEqual(respuesta.context["periodo"].clase, "mes")
        self.assertContains(respuesta, 'aria-current="page">Mes</a>', html=False)
        for texto in ("1 día", "3 días", "7 días", "14 días", "Semestre", "Año", "Personalizado"):
            self.assertContains(respuesta, f">{texto}</a>", html=False)
        self.assertContains(respuesta, "calendario-celda")

    def test_filtro_invalido_muestra_error_y_omision(self):
        self.client.force_login(self.e["qf"])
        respuesta = self.client.get(PANEL, {"periodo": "personalizado", "desde": f"{hoy():%Y-%m-%d}", "hasta": "2999-01-01"})
        self.assertContains(respuesta, "no puede ser posterior a hoy")
        self.assertEqual(respuesta.context["periodo"].clase, "mes")

    def test_semestre_y_anio_van_en_columnas(self):
        self.client.force_login(self.e["qf"])
        for clase in ("semestre", "anio"):
            respuesta = self.client.get(PANEL, {"periodo": clase})
            self.assertIsNone(respuesta.context["calendario"])
            self.assertIsNotNone(respuesta.context["evolucion"])

    def test_periodo_vacio(self):
        self.client.force_login(self.e["qf"])
        respuesta = self.client.get(PANEL, {"periodo": "7d", "tipo": "general"})
        self.assertContains(respuesta, "No hay turnos, recetas ni visitas en este período")


class ReportesTests(TestCase):
    def setUp(self):
        self.e = equipo()
        self.director = cuenta("director_reportes", DIRECTOR)
        self.personas = [paciente(edad=85, cronico=indice % 2 == 0) for indice in range(3)]
        for persona in self.personas:
            preparada(persona, usuario=self.e["tecnico"])

    def personales(self):
        datos = []
        for persona in self.personas:
            cuerpo = persona.rut.split("-")[0]
            datos += [persona.rut, cuerpo, persona.apellidos, persona.nombres]
        return datos

    def texto_excel(self, contenido):
        with zipfile.ZipFile(io.BytesIO(contenido)) as archivo:
            return "".join(archivo.read(nombre).decode("utf-8", "ignore") for nombre in archivo.namelist())

    def texto_pdf(self, contenido):
        # El PDF se genera sin compresión: su texto está en claro dentro del archivo.
        self.assertTrue(contenido.startswith(b"%PDF"))
        return contenido.decode("latin-1")

    def descargar(self, formato, **parametros):
        respuesta = self.client.get(reverse("indicadoresapp:mermas_reporte", args=[formato]), parametros)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("attachment", respuesta["Content-Disposition"])
        self.assertIn("mermas_", respuesta["Content-Disposition"])
        self.assertIn("no-store", respuesta["Cache-Control"])
        return respuesta.content

    def test_tres_formatos_sin_datos_personales_y_auditados(self):
        for usuario in (self.e["qf"], self.director):
            self.client.force_login(usuario)
            for formato in ("xlsx", "csv", "pdf"):
                contenido = self.descargar(formato)
                if formato == "xlsx":
                    texto = self.texto_excel(contenido)
                    self.assertIn("Sin retirar", texto)
                elif formato == "pdf":
                    texto = self.texto_pdf(contenido)
                    self.assertIn("Sin retirar", texto)
                else:
                    texto = contenido.decode("utf-8-sig")
                for dato in self.personales():
                    self.assertNotIn(dato, texto, (formato, dato))
        self.assertEqual(RegistroAuditoria.objects.filter(accion__startswith="mermas.reporte_").count(), 6)

    def test_csv_con_bom_punto_y_coma_y_una_fila_por_dia(self):
        self.client.force_login(self.e["qf"])
        desde = hoy() - timedelta(days=9)
        contenido = self.descargar("csv", periodo="personalizado", desde=f"{desde:%Y-%m-%d}", hasta=f"{hoy():%Y-%m-%d}")
        self.assertTrue(contenido.startswith("﻿".encode("utf-8")))
        lineas = contenido.decode("utf-8-sig").split("\r\n")[:-1]
        cabeza = lineas[0].split(";")
        self.assertEqual(cabeza[:3], ["fecha", "farmacia_entregadas_atencion_o_ficha", "farmacia_retiradas_despues"])
        self.assertEqual(len(lineas), 11)
        self.assertEqual(lineas[1].split(";")[0], f"{desde:%Y-%m-%d}")
        fila_de_hoy = lineas[-1].split(";")
        self.assertEqual(fila_de_hoy[cabeza.index("merma")], "3")
        self.assertEqual(fila_de_hoy[cabeza.index("farmacia_paciente_ausente")], "3")

    def test_excel_trae_sus_hojas_y_graficos(self):
        self.client.force_login(self.e["qf"])
        contenido = self.descargar("xlsx", periodo="anio")
        with zipfile.ZipFile(io.BytesIO(contenido)) as archivo:
            self.assertEqual(len([n for n in archivo.namelist() if n.startswith("xl/charts/chart")]), 5)
            libro = archivo.read("xl/workbook.xml").decode("utf-8")
        for hoja in ("Resumen", "Por día", "Ausentes por hora"):
            self.assertIn(hoja, libro)

    def test_formato_desconocido_y_tecnico(self):
        self.client.force_login(self.e["qf"])
        self.assertEqual(self.client.get(reverse("indicadoresapp:mermas_reporte", args=["doc"])).status_code, 404)
        self.client.force_login(self.e["tecnico"])
        self.assertEqual(self.client.get(reverse("indicadoresapp:mermas_reporte", args=["csv"])).status_code, 403)


class DerivarVistaTests(TestCase):
    def setUp(self):
        self.e = equipo()
        self.client.force_login(self.e["qf"])

    def url(self, persona):
        return reverse("indicadoresapp:mermas_derivar", args=[persona.pk])

    def test_deriva_y_redirige_a_la_entrega(self):
        persona = paciente(edad=85)
        preparada(persona, usuario=self.e["tecnico"])
        pagina = self.client.get(self.url(persona))
        self.assertContains(pagina, "Programar entrega a domicilio")
        # RF-13-22: «Volver» regresa a «Pendientes de retiro».
        self.assertContains(pagina, f'href="{reverse("recetasapp:preparacion_pendientes")}"')
        respuesta = self.client.post(self.url(persona), {
            "fecha": f"{hoy():%Y-%m-%d}", "encargado": self.e["encargado"].pk, "operacion_id": uuid.uuid4(),
        })
        entrega = Entrega.objects.get(paciente=persona)
        self.assertRedirects(respuesta, reverse("entregasapp:detalle", args=[entrega.pk]), fetch_redirect_response=False)

    def test_no_elegible_pide_motivo(self):
        persona = paciente(edad=60)
        preparada(persona, usuario=self.e["tecnico"])
        self.assertContains(self.client.get(self.url(persona)), "Motivo de la excepción de reparto")
        respuesta = self.client.post(self.url(persona), {
            "fecha": f"{hoy():%Y-%m-%d}", "encargado": self.e["encargado"].pk, "operacion_id": uuid.uuid4(),
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Entrega.objects.exists())

    def test_director_no_deriva(self):
        persona = paciente(edad=85)
        preparada(persona, usuario=self.e["tecnico"])
        self.client.force_login(cuenta("director_derivar", DIRECTOR))
        respuesta = self.client.post(self.url(persona), {
            "fecha": f"{hoy():%Y-%m-%d}", "encargado": self.e["encargado"].pk, "operacion_id": uuid.uuid4(),
        })
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Entrega.objects.exists())
