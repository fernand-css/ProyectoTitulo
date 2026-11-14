"""RF-08-16: lista de elegibles de «Programar entrega» con búsqueda y filtros (ampliación del 2026-11-13).

La lista abre con todos los elegibles en páginas de 50, se filtra por sector, motivo del reparto, estado del
domicilio y localidad, y se actualiza por POST (fragmento) sin poner el RUT ni el nombre en la URL. Sin JavaScript,
la misma búsqueda funciona con «Buscar» (`accion=buscar`).
"""

import re
import uuid

from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from coreapp.tests.test_plantillas import DocumentoHTML
from entregasapp.consultas import elegibles, localidades_elegibles, motivos_de
from entregasapp.services import guardar_domicilio, inscribir_excepcion, programar_entrega, verificar_domicilio
from recetasapp.models import Paciente
from .ayudas import equipo, hoy, nacimiento_para, paciente, receta

LISTA = reverse("entregasapp:programar_lista")
PROGRAMAR = reverse("entregasapp:programar")


def domicilio(actor, persona, sector="verde", localidad="Dadinco"):
    return guardar_domicilio(actor, persona.pk, {"sector": sector, "localidad": localidad,
                                                 "direccion": "Camino sintético km 3", "referencias": "Portón sintético"})


def ids_de(html):
    """Pacientes seleccionables de la lista (casillas activas)."""
    return sorted(int(valor) for valor in re.findall(r'data-paciente="(\d+)"', html))


class ListaYFiltrosTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.qf = self.equipo["qf"]
        self.client.force_login(self.qf)
        self.verde = paciente(edad=85)
        self.azul = paciente(edad=90)
        self.sin_domicilio = paciente(edad=82)
        self.postrado = paciente(edad=50, postrado=True)
        self.postrado_mayor = paciente(edad=88, postrado=True)  # dos motivos a la vez
        self.cronico = paciente(edad=60, cronico=True)
        inscribir_excepcion(self.qf, self.cronico.pk, "sin_red_apoyo")
        self.no_elegible = paciente(edad=40)
        domicilio(self.qf, self.verde, "verde", "Dadinco")
        domicilio(self.qf, self.azul, "azul", "  dadinco ")  # otra grafía de la misma localidad
        domicilio(self.qf, self.postrado, "verde", "Huechupín")
        domicilio(self.qf, self.postrado_mayor, "", "Huechupín")  # domicilio sin sector
        verificar_domicilio(self.equipo["encargado"], domicilio(self.qf, self.cronico, "rojo", "Zemita").pk, 1)

    def fragmento(self, **datos):
        respuesta = self.client.post(LISTA, datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("no-store", respuesta["Cache-Control"])
        return respuesta.content.decode()

    def test_cada_filtro_solo_y_combinado_devuelve_exactamente_lo_esperado(self):
        todos = [self.verde, self.azul, self.sin_domicilio, self.postrado, self.postrado_mayor, self.cronico]
        localidad_dadinco = dict((rotulo, clave) for clave, rotulo in localidades_elegibles())["Dadinco"]
        casos = {
            "todos": ({}, todos),
            "verde": ({"sector": "verde"}, [self.verde, self.postrado]),
            "sin sector": ({"sector": "sin"}, [self.sin_domicilio, self.postrado_mayor]),
            "postrado": ({"motivo": "postrado"}, [self.postrado, self.postrado_mayor]),
            "80 o más": ({"motivo": "edad"}, [self.verde, self.azul, self.sin_domicilio, self.postrado_mayor]),
            "excepción": ({"motivo": "excepcion"}, [self.cronico]),
            "verificado": ({"estado": "verificado"}, [self.cronico]),
            "pendiente": ({"estado": "pendiente"}, [self.verde, self.azul, self.postrado, self.postrado_mayor]),
            "sin registrar": ({"estado": "sin_registrar"}, [self.sin_domicilio]),
            "localidad con otra grafía": ({"localidad": localidad_dadinco}, [self.verde, self.azul]),
            "verde + 80 + pendiente + Dadinco": (
                {"sector": "verde", "motivo": "edad", "estado": "pendiente", "localidad": localidad_dadinco}, [self.verde]),
            "azul + postrado": ({"sector": "azul", "motivo": "postrado"}, []),
        }
        for nombre, (datos, esperados) in casos.items():
            with self.subTest(caso=nombre):
                self.assertEqual(ids_de(self.fragmento(**datos)), sorted(p.pk for p in esperados))
                self.assertEqual(sorted(elegibles(hoy(), **datos).values_list("pk", flat=True)), sorted(p.pk for p in esperados))

    def test_localidades_agrupadas_sin_distinguir_mayusculas_ni_espacios(self):
        rotulos = [rotulo for _, rotulo in localidades_elegibles()]
        self.assertEqual(rotulos, ["Dadinco", "Huechupín", "Zemita"])
        html = self.client.get(PROGRAMAR).content.decode()
        self.assertEqual(html.count(">Dadinco</option>"), 1)

    def test_busqueda_por_apellido_y_por_rut(self):
        Paciente.objects.filter(pk=self.verde.pk).update(apellidos="González Sintético")
        Paciente.objects.filter(pk=self.azul.pk).update(apellidos="Gonzalo Sintético")
        for parcial in ("G", "Go", "Gon", "Gonz"):
            with self.subTest(buscar=parcial):
                self.assertEqual(ids_de(self.fragmento(buscar=parcial)), sorted([self.verde.pk, self.azul.pk]))
        self.assertEqual(ids_de(self.fragmento(buscar=self.postrado.rut)), [self.postrado.pk])
        self.assertEqual(ids_de(self.fragmento(buscar="Gonz", sector="azul")), [self.azul.pk])

    def test_un_paciente_con_dos_motivos_aparece_en_ambos_y_muestra_los_dos(self):
        self.assertIn(self.postrado_mayor.pk, ids_de(self.fragmento(motivo="postrado")))
        self.assertIn(self.postrado_mayor.pk, ids_de(self.fragmento(motivo="edad")))
        self.assertEqual(motivos_de(self.postrado_mayor), ["Postrado", "80 años o más"])
        self.assertEqual(motivos_de(self.cronico), ["Excepción"])
        self.assertIn("Postrado · 80 años o más", self.fragmento(motivo="postrado"))

    def test_paciente_con_entrega_abierta_rotulado_enlazado_y_sin_casilla_activa(self):
        receta(self.verde)
        entrega = programar_entrega(self.qf, self.verde.pk, hoy(), self.equipo["encargado"].pk, uuid.uuid4())
        html = self.fragmento()
        self.assertNotIn(self.verde.pk, ids_de(html))
        self.assertIn(reverse("entregasapp:detalle", args=[entrega.pk]), html)
        self.assertIn("Ya tiene una entrega abierta", html)
        casilla = re.search(rf'<input[^>]*id="sel-{self.verde.pk}"[^>]*>', html).group(0)
        self.assertIn("disabled", casilla)
        self.assertNotIn('name="ids"', casilla)

    def test_sin_resultados_lo_dice_y_ofrece_excepciones(self):
        html = self.fragmento(buscar="Nadie con este apellido")
        self.assertIn("No encontramos pacientes del reparto", html)
        self.assertIn(reverse("entregasapp:excepciones"), html)
        self.assertIn('data-total="0"', html)

    def test_el_respaldo_sin_javascript_da_lo_mismo_que_el_fragmento(self):
        datos = {"sector": "verde", "motivo": "postrado"}
        respaldo = self.client.post(PROGRAMAR, {"accion": "buscar", **datos})
        self.assertEqual(respaldo.status_code, 200)
        self.assertEqual(ids_de(respaldo.content.decode()), ids_de(self.fragmento(**datos)))
        self.assertIn("1 paciente del reparto", respaldo.content.decode())

    def test_la_pagina_y_el_fragmento_tienen_estructura_accesible(self):
        for html in (self.client.get(PROGRAMAR).content.decode(), self.fragmento()):
            documento = DocumentoHTML(html)
            ids = [atributos["id"] for _, atributos in documento.elementos if "id" in atributos]
            self.assertEqual(len(ids), len(set(ids)))
            etiquetados = {a["for"] for e, a in documento.elementos if e == "label" and "for" in a}
            for etiqueta, atributos in documento.elementos:
                if etiqueta in ("input", "select") and atributos.get("type") not in ("hidden", "submit"):
                    self.assertIn(atributos.get("id"), etiquetados, atributos)
        pagina = self.client.get(PROGRAMAR).content.decode()
        self.assertIn('role="status"', pagina)
        self.assertIn(f'Seleccionar a {self.verde.apellidos}, {self.verde.nombres}', pagina)


class PaginacionYPrivacidadTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.client.force_login(self.equipo["qf"])
        self.personas = [paciente(edad=85) for _ in range(55)]
        paciente(edad=40)  # no elegible

    def test_abre_con_todos_los_elegibles_en_paginas_de_50(self):
        respuesta = self.client.get(PROGRAMAR)
        html = respuesta.content.decode()
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("55 pacientes del reparto", html)
        self.assertIn("Seleccionar los 55 filtrados", html)
        self.assertEqual(len(ids_de(html)), 50)
        self.assertIn("Página 1 de 2", html)
        segunda = self.client.post(LISTA, {"pagina": 2}).content.decode()
        self.assertEqual(len(ids_de(segunda)), 5)
        self.assertIn('data-pagina="2"', segunda)
        self.assertEqual(set(ids_de(html)) | set(ids_de(segunda)), {p.pk for p in self.personas})

    def test_la_paginacion_va_por_post_y_la_url_no_lleva_rut_ni_nombres(self):
        html = self.client.post(LISTA, {"buscar": self.personas[0].apellidos}).content.decode()
        enlaces = re.findall(r'(?:href|action|formaction)="([^"]*)"', html + self.client.get(PROGRAMAR).content.decode())
        for enlace in enlaces:
            with self.subTest(enlace=enlace):
                self.assertNotRegex(enlace, r"\d{1,2}\.?\d{3}\.?\d{3}-[\dkK]")
                self.assertNotIn("Reparto", enlace)
                self.assertNotIn("buscar=", enlace)
        self.assertIn('name="pagina"', self.client.get(PROGRAMAR).content.decode())
        self.assertNotIn("?page=", self.client.get(PROGRAMAR).content.decode())

    def test_numero_de_consultas_constante_por_pagina(self):
        def consultas_de_la_lista():
            with CaptureQueriesContext(connection) as capturadas:
                self.client.post(LISTA, {})
            return len(capturadas)

        con_55 = consultas_de_la_lista()
        for _ in range(30):
            persona = paciente(edad=87)
            domicilio(self.equipo["qf"], persona, "azul", f"Localidad {persona.pk % 4}")
        self.assertEqual(consultas_de_la_lista(), con_55)


class PermisosListaTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        paciente(edad=85)

    def test_solo_la_qf_y_el_superusuario(self):
        for actor, esperado in ((self.equipo["qf"], 200), (self.equipo["admin"], 200), (self.equipo["tecnico"], 403),
                                (self.equipo["encargado"], 403)):
            with self.subTest(actor=actor.username):
                self.client.force_login(actor)
                self.assertEqual(self.client.post(LISTA, {}).status_code, esperado)
                self.assertEqual(self.client.get(PROGRAMAR).status_code, esperado)
        self.client.logout()
        respuesta = self.client.post(LISTA, {})
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("usuariosapp:login"), respuesta["Location"])

    def test_el_fragmento_exige_csrf_y_no_acepta_get(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.equipo["qf"])
        self.assertEqual(cliente.post(LISTA, {"buscar": "Reparto"}).status_code, 403)
        self.client.force_login(self.equipo["qf"])
        self.assertEqual(self.client.get(LISTA).status_code, 405)

    def test_el_flujo_individual_y_la_preseleccion_del_spec_10_no_cambian(self):
        persona = paciente(edad=86)
        receta(persona)
        self.client.force_login(self.equipo["qf"])
        respuesta = self.client.get(PROGRAMAR + f"?paciente={persona.pk}")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Revisar recetas")

    def test_un_paciente_que_cumple_80_hoy_aparece_en_la_lista(self):
        cumple = paciente(nacimiento=nacimiento_para(80))
        casi = paciente(nacimiento=nacimiento_para(80, dias_extra=1))  # 79 años y 364 días
        self.client.force_login(self.equipo["qf"])
        lista = ids_de(self.client.post(LISTA, {"motivo": "edad"}).content.decode())
        self.assertIn(cumple.pk, lista)
        self.assertNotIn(casi.pk, lista)
