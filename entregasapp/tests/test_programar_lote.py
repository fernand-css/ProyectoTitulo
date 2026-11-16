"""RF-08-17: programar varios pacientes a la vez (ampliación del 2026-11-13).

Servicio: cada paciente se programa por separado con las reglas del RF-08-06; los omitidos llevan su motivo y no
revierten a los demás; reenviar el lote, completo o por partes, no duplica. Vistas: selección (casillas o todos los
filtrados), revisión firmada, confirmación por tramos de hasta 25 (JSON) o completa (sin JavaScript).
"""

import json
import re
import uuid
from datetime import timedelta

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from coreapp.models import RegistroAuditoria
from coreapp.roles import ENCARGADO, JEFA
from entregasapp.models import Entrega, IntentoEntrega, RecetaEntrega
from entregasapp.services import (
    OMITIDO_ABIERTA, OMITIDO_NO_ELEGIBLE, OMITIDO_SIN_RECETAS, guardar_domicilio, inscribir_excepcion,
    operacion_de_lote, programar_entrega, programar_lote, recetas_para_despacho, recetas_para_despacho_lote,
    retirar_excepcion,
)
from entregasapp.views import SAL_LOTE
from recetasapp.models import Paciente, PreparacionReceta
from .ayudas import cuenta, equipo, hoy, paciente, receta
from .test_programacion import turno

VARIOS = reverse("entregasapp:programar_varios")
TRAMO = reverse("entregasapp:programar_tramo")


def contexto_de(html):
    return re.search(r'name="contexto" value="([^"]+)"', html).group(1)


class RecetasLoteTests(TestCase):
    def setUp(self):
        self.equipo = equipo()

    def crear_variedad(self):
        """Pacientes con recetas vigentes, vencidas, agotadas, futuras, en turno activo y pendientes de retiro."""
        pacientes = []
        for indice in range(4):
            persona = paciente(edad=60, cronico=True)
            inscribir_excepcion(self.equipo["qf"], persona.pk, "discapacidad")
            receta(persona, f"VIG-{persona.pk}")
            receta(persona, f"VEN-{persona.pk}", inicio=hoy() - timedelta(days=200), fin=hoy())
            receta(persona, f"AGO-{persona.pk}", maximo=2, completadas=2)
            receta(persona, f"FUT-{persona.pk}", inicio=hoy() + timedelta(days=3))
            if indice == 1:
                turno(persona, [receta(persona, f"TUR-{persona.pk}")])
            if indice == 2:
                _, (vinculo,) = turno(persona, [receta(persona, f"RET-{persona.pk}")], estado="ausente")
                ahora = timezone.now()
                PreparacionReceta.objects.create(
                    turno_receta=vinculo, recibida_en=ahora - timedelta(minutes=5), lista_en=ahora,
                    lista_por=self.equipo["tecnico"], inicio_medido=ahora - timedelta(minutes=4), duracion_segundos=240)
            pacientes.append(persona)
        pacientes.append(paciente(edad=85))  # sin recetas
        return pacientes

    def test_coincide_con_el_calculo_por_paciente_en_varias_fechas(self):
        pacientes = self.crear_variedad()
        for fecha in (hoy(), hoy() + timedelta(days=3)):
            with self.subTest(fecha=fecha):
                lote = recetas_para_despacho_lote(pacientes, fecha)
                for persona in pacientes:
                    self.assertEqual([r.pk for r in lote[persona.pk]], [r.pk for r in recetas_para_despacho(persona, fecha)])
        self.assertEqual(recetas_para_despacho_lote([], hoy()), {})

    def test_numero_de_consultas_constante(self):
        pocos = self.crear_variedad()
        with CaptureQueriesContext(connection) as primero:
            recetas_para_despacho_lote([p.pk for p in pocos], hoy())
        muchos = pocos + self.crear_variedad() + self.crear_variedad()
        with CaptureQueriesContext(connection) as segundo:
            recetas_para_despacho_lote([p.pk for p in muchos], hoy())
        self.assertEqual(len(primero), len(segundo))
        self.assertLessEqual(len(segundo), 3)


class ProgramarLoteServicioTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.qf = self.equipo["qf"]
        self.encargado = self.equipo["encargado"]
        self.ok = [paciente(edad=85) for _ in range(3)]
        for persona in self.ok:
            receta(persona)
            receta(persona)
        self.con_abierta = paciente(edad=90)
        receta(self.con_abierta)
        self.abierta = programar_entrega(self.qf, self.con_abierta.pk, hoy(), self.encargado.pk, uuid.uuid4())
        self.sin_recetas = paciente(edad=88)
        self.no_elegible = paciente(edad=60, cronico=True)
        receta(self.no_elegible)

    def ids(self):
        return [self.ok[0].pk, self.con_abierta.pk, self.ok[1].pk, self.sin_recetas.pk, self.no_elegible.pk, self.ok[2].pk]

    def test_programa_a_cada_uno_y_omite_con_motivo_sin_revertir_a_los_demas(self):
        lote = uuid.uuid4()
        manana = hoy() + timedelta(days=1)
        resultados = programar_lote(self.qf, self.ids(), manana, self.encargado.pk, lote)
        self.assertEqual([r.paciente_id for r in resultados], self.ids())
        programados = [r for r in resultados if r.programado]
        self.assertEqual({r.paciente_id for r in programados}, {p.pk for p in self.ok})
        self.assertTrue(all(r.recetas == 2 for r in programados))
        motivos = {r.paciente_id: r.motivo for r in resultados if not r.programado}
        self.assertEqual(motivos, {self.con_abierta.pk: OMITIDO_ABIERTA, self.sin_recetas.pk: OMITIDO_SIN_RECETAS,
                                   self.no_elegible.pk: OMITIDO_NO_ELEGIBLE})
        for persona in self.ok:
            entrega = Entrega.objects.get(paciente=persona)
            self.assertEqual(entrega.operacion_id, operacion_de_lote(lote, persona.pk))
            intento = entrega.intentos.get()
            self.assertEqual((intento.fecha_programada, intento.encargado_id), (manana, self.encargado.pk))
        self.assertEqual(Entrega.objects.filter(estado__in=Entrega.ABIERTAS).count(), 4)

    def test_reenviar_el_lote_completo_o_por_partes_no_duplica(self):
        lote = uuid.uuid4()
        primera = programar_lote(self.qf, self.ids()[:3], hoy(), self.encargado.pk, lote)
        completa = programar_lote(self.qf, self.ids(), hoy(), self.encargado.pk, lote)
        otra_vez = programar_lote(self.qf, self.ids(), hoy(), self.encargado.pk, lote)
        self.assertEqual(Entrega.objects.count(), 4)
        self.assertEqual(IntentoEntrega.objects.count(), 4)
        self.assertEqual(RecetaEntrega.objects.count(), 7)
        por_paciente = {r.paciente_id: r.entrega_id for r in completa if r.programado}
        self.assertEqual(por_paciente, {r.paciente_id: r.entrega_id for r in otra_vez if r.programado})
        self.assertEqual(por_paciente[self.ok[0].pk], primera[0].entrega_id)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="entrega.programada").count(), 4)

    def test_otro_lote_omite_a_los_ya_programados(self):
        programar_lote(self.qf, self.ids(), hoy(), self.encargado.pk, uuid.uuid4())
        segundo = programar_lote(self.qf, self.ids(), hoy(), self.equipo["encargado2"].pk, uuid.uuid4())
        self.assertFalse(any(r.programado for r in segundo))
        self.assertEqual({r.motivo for r in segundo if r.paciente_id in {p.pk for p in self.ok}}, {OMITIDO_ABIERTA})

    def test_fecha_pasada_encargado_invalido_y_actor_sin_rol_no_cambian_nada(self):
        antes = Entrega.objects.count()
        inactivo = cuenta("encargado_inactivo_lote", ENCARGADO, activa=False)
        for fecha, encargado in ((hoy() - timedelta(days=1), self.encargado), (hoy(), inactivo), (hoy(), self.qf)):
            with self.subTest(fecha=fecha, encargado=encargado.username), self.assertRaises(ValidationError):
                programar_lote(self.qf, self.ids(), fecha, encargado.pk, uuid.uuid4())
        with self.assertRaises(PermissionDenied):
            programar_lote(self.equipo["tecnico"], self.ids(), hoy(), self.encargado.pk, uuid.uuid4())
        self.assertEqual(Entrega.objects.count(), antes)

    def test_una_excepcion_retirada_sale_como_no_elegible_y_un_id_inexistente_como_no_disponible(self):
        excepcion = paciente(edad=60)
        receta(excepcion)
        inscripcion = inscribir_excepcion(self.qf, excepcion.pk, "discapacidad")
        retirar_excepcion(self.qf, inscripcion.pk)
        resultados = programar_lote(self.qf, [excepcion.pk, 999_999], hoy(), self.encargado.pk, uuid.uuid4())
        self.assertEqual([r.motivo for r in resultados], [OMITIDO_NO_ELEGIBLE, "El paciente no está disponible"])

    def ocupado_para(self, persona, veces):
        """programar_entrega que falla `veces` veces con la base ocupada para `persona`; anota cada llamada."""
        from django.db import OperationalError
        import entregasapp.services as servicios

        real, llamadas = servicios.programar_entrega, []

        def falso(actor, paciente_id, *args, **kwargs):
            llamadas.append(paciente_id)
            if paciente_id == persona.pk and llamadas.count(persona.pk) <= veces:
                raise OperationalError("La operación está ocupada. Inténtalo nuevamente con la misma confirmación.")
            return real(actor, paciente_id, *args, **kwargs)
        return falso, llamadas

    def test_un_paciente_con_la_base_ocupada_se_reintenta_al_final_del_tramo(self):
        from unittest import mock

        falso, llamadas = self.ocupado_para(self.ok[1], veces=1)
        with mock.patch("entregasapp.services.programar_entrega", falso), \
                mock.patch("entregasapp.services.time.sleep") as pausa:
            resultados = programar_lote(self.qf, self.ids(), hoy(), self.encargado.pk, uuid.uuid4())
        self.assertEqual([r.paciente_id for r in resultados], self.ids())  # el orden no cambia
        self.assertEqual(llamadas, [*self.ids(), self.ok[1].pk])  # vuelve después de los demás
        self.assertTrue(next(r for r in resultados if r.paciente_id == self.ok[1].pk).programado)
        self.assertEqual(Entrega.objects.filter(paciente=self.ok[1]).count(), 1)
        pausa.assert_called_once()

    def test_si_la_base_sigue_ocupada_sale_como_reintentar_sin_detener_a_los_demas(self):
        from unittest import mock
        from entregasapp.services import OMITIDO_REINTENTAR, VUELTAS_OCUPADOS

        falso, llamadas = self.ocupado_para(self.ok[1], veces=99)
        with mock.patch("entregasapp.services.programar_entrega", falso), mock.patch("entregasapp.services.time.sleep"):
            resultados = programar_lote(self.qf, self.ids(), hoy(), self.encargado.pk, uuid.uuid4())
        self.assertEqual(llamadas.count(self.ok[1].pk), 1 + VUELTAS_OCUPADOS)
        por_paciente = {r.paciente_id: r for r in resultados}
        self.assertEqual(por_paciente[self.ok[1].pk].motivo, OMITIDO_REINTENTAR)
        self.assertTrue(por_paciente[self.ok[0].pk].programado and por_paciente[self.ok[2].pk].programado)
        self.assertFalse(Entrega.objects.filter(paciente=self.ok[1]).exists())

    def test_la_auditoria_tiene_una_programacion_por_entrega_sin_datos_personales(self):
        programar_lote(self.qf, self.ids(), hoy(), self.encargado.pk, uuid.uuid4())
        eventos = RegistroAuditoria.objects.filter(accion="entrega.programada")
        self.assertEqual(sorted(int(e.objeto_id) for e in eventos), sorted(Entrega.objects.values_list("pk", flat=True)))
        volcado = json.dumps(list(RegistroAuditoria.objects.values()), default=str)
        for persona in Paciente.objects.all():
            self.assertNotIn(persona.rut, volcado)
            self.assertNotIn(persona.apellidos, volcado)


class ProgramarVariosVistaTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.qf = self.equipo["qf"]
        self.encargado = self.equipo["encargado"]
        self.client.force_login(self.qf)

    def revisar(self, datos, fecha=None, encargado=None):
        respuesta = self.client.post(VARIOS, {**datos, "fecha": (fecha or hoy()).isoformat(),
                                              "encargado": (encargado or self.encargado).pk})
        return respuesta

    def confirmar_por_tramos(self, contexto, cantidad, tramo=25):
        resultados = []
        for desde in range(0, cantidad, tramo):
            respuesta = self.client.post(TRAMO, {"contexto": contexto, "desde": desde, "hasta": min(desde + tramo, cantidad)})
            self.assertEqual(respuesta.status_code, 200, respuesta.content)
            self.assertIn("no-store", respuesta["Cache-Control"])
            resultados += respuesta.json()["resultados"]
        return resultados

    def test_acepta_120_filtrados_con_4_abiertas_y_2_sin_recetas(self):
        """Criterio de aceptación: «Seleccionar los N filtrados» con 120, de los cuales 6 no se programan."""
        pacientes = []
        for indice in range(120):
            persona = paciente(edad=85)
            if indice >= 2:
                receta(persona)
            guardar_domicilio(self.qf, persona.pk, {"sector": "verde", "localidad": "Dadinco", "direccion": "Camino km 1"})
            pacientes.append(persona)
        for persona in pacientes[2:6]:
            programar_entrega(self.qf, persona.pk, hoy(), self.equipo["encargado2"].pk, uuid.uuid4())
        otro_sector = paciente(edad=85)
        receta(otro_sector)
        manana = hoy() + timedelta(days=1)
        filtros = {"todos": "1", "sector": "verde", "ids": [otro_sector.pk]}  # con «todos», los ids se ignoran
        paso1 = self.client.post(VARIOS, filtros)
        self.assertContains(paso1, "Programar 120 entregas")
        revision = self.revisar(filtros, fecha=manana)
        html = revision.content.decode()
        self.assertEqual(revision.status_code, 200)
        self.assertIn("Se programarán 114 pacientes con 114 recetas.", html)
        self.assertIn("No se programarán (", html)
        self.assertEqual(html.count(OMITIDO_ABIERTA), 4)
        self.assertEqual(html.count(OMITIDO_SIN_RECETAS), 2)
        self.assertIn("entrega 1 de 6", html)
        self.assertIn('data-total="120"', html)
        resultados = self.confirmar_por_tramos(contexto_de(html), 114)
        self.assertEqual(sum(r["estado"] == "programado" for r in resultados), 114)
        self.assertEqual(IntentoEntrega.objects.filter(fecha_programada=manana, encargado=self.encargado).count(), 114)
        self.assertFalse(Entrega.objects.filter(paciente=otro_sector).exists())
        programacion = self.client.get(reverse("entregasapp:programacion"), {
            "encargado": self.encargado.pk, "desde": manana.isoformat(), "hasta": manana.isoformat()})
        self.assertContains(programacion, "114")
        texto_json = json.dumps(resultados)
        for persona in pacientes[:10]:
            self.assertNotIn(persona.rut, texto_json)
            self.assertNotIn(persona.apellidos, texto_json)

    def test_seleccion_por_casillas_y_reenvio_del_mismo_tramo(self):
        personas = [paciente(edad=85) for _ in range(3)]
        for persona in personas:
            receta(persona)
        datos = {"ids": [personas[0].pk, personas[1].pk, personas[0].pk, "x", personas[2].pk]}
        paso1 = self.client.post(VARIOS, datos)
        self.assertContains(paso1, "Programar 3 entregas")
        self.assertEqual(paso1.content.decode().count('name="ids"'), 3)
        html = self.revisar(datos).content.decode()
        contexto = contexto_de(html)
        primera = self.client.post(TRAMO, {"contexto": contexto, "desde": 0, "hasta": 2}).json()["resultados"]
        repetida = self.client.post(TRAMO, {"contexto": contexto, "desde": 0, "hasta": 2}).json()["resultados"]
        self.assertEqual(primera, repetida)
        resto = self.client.post(TRAMO, {"contexto": contexto, "desde": 2, "hasta": 3}).json()["resultados"]
        self.assertEqual(Entrega.objects.count(), 3)
        self.assertTrue(all(r["estado"] == "programado" for r in primera + resto))

    def test_sin_seleccion_vuelve_a_la_lista_con_aviso(self):
        respuesta = self.client.post(VARIOS, {"ids": []}, follow=True)
        self.assertRedirects(respuesta, reverse("entregasapp:programar"))
        self.assertContains(respuesta, "Marca al menos un paciente")
        respuesta = self.client.post(VARIOS, {"todos": "1", "localidad": "no-existe"})
        self.assertRedirects(respuesta, reverse("entregasapp:programar"), fetch_redirect_response=False)

    def test_fecha_pasada_y_encargado_inactivo_se_rechazan_en_la_revision(self):
        persona = paciente(edad=85)
        receta(persona)
        inactivo = cuenta("encargado_inactivo_vista", ENCARGADO, activa=False)
        for fecha, encargado in ((hoy() - timedelta(days=1), self.encargado), (hoy(), inactivo)):
            with self.subTest(fecha=fecha):
                respuesta = self.revisar({"ids": [persona.pk]}, fecha=fecha, encargado=encargado)
                self.assertEqual(respuesta.status_code, 400)
                self.assertNotIn('name="contexto"', respuesta.content.decode())
        self.assertFalse(Entrega.objects.exists())

    def test_firma_alterada_actor_distinto_tramo_invalido_y_tecnico(self):
        persona = paciente(edad=85)
        receta(persona)
        contexto = contexto_de(self.revisar({"ids": [persona.pk]}).content.decode())
        casos = {
            "alterada": {"contexto": contexto[:-3] + "abc", "desde": 0, "hasta": 1},
            "vacía": {"contexto": "", "desde": 0, "hasta": 1},
            "fuera de rango": {"contexto": contexto, "desde": 0, "hasta": 2},
            "invertido": {"contexto": contexto, "desde": 1, "hasta": 0},
            "no numérico": {"contexto": contexto, "desde": "a", "hasta": 1},
        }
        for nombre, datos in casos.items():
            with self.subTest(caso=nombre):
                respuesta = self.client.post(TRAMO, datos)
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("error", respuesta.json())
        otra_qf = cuenta("otra_qf_lote", JEFA)
        self.client.force_login(otra_qf)
        respuesta = self.client.post(TRAMO, {"contexto": contexto, "desde": 0, "hasta": 1})
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("otra cuenta", respuesta.json()["error"])
        self.client.force_login(self.equipo["tecnico"])
        self.assertEqual(self.client.post(TRAMO, {"contexto": contexto, "desde": 0, "hasta": 1}).status_code, 403)
        self.assertEqual(self.client.post(VARIOS, {"ids": [persona.pk]}).status_code, 403)
        self.assertFalse(Entrega.objects.exists())

    def test_tramo_de_mas_de_25_y_fecha_pasada_firmada_se_rechazan(self):
        personas = [paciente(edad=85) for _ in range(26)]
        for persona in personas:
            receta(persona)
        contexto = contexto_de(self.revisar({"ids": [p.pk for p in personas]}).content.decode())
        self.assertEqual(self.client.post(TRAMO, {"contexto": contexto, "desde": 0, "hasta": 26}).status_code, 400)
        ayer = signing.dumps({"lote": str(uuid.uuid4()), "ids": [personas[0].pk], "fecha": (hoy() - timedelta(days=1)).isoformat(),
                              "encargado": self.encargado.pk, "actor": self.qf.pk, "omitidos": []}, salt=SAL_LOTE, compress=True)
        respuesta = self.client.post(TRAMO, {"contexto": ayer, "desde": 0, "hasta": 1})
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("hoy o posterior", respuesta.json()["error"])
        self.assertFalse(Entrega.objects.exists())

    def test_sin_javascript_confirma_el_lote_completo_y_dibuja_el_resumen(self):
        personas = [paciente(edad=85) for _ in range(3)]
        for persona in personas[:2]:
            receta(persona)
        Paciente.objects.filter(pk=personas[2].pk).update(apellidos="Sin Recetas Sintético")
        html = self.revisar({"ids": [p.pk for p in personas]}).content.decode()
        respuesta = self.client.post(TRAMO, {"contexto": contexto_de(html)})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Se programaron 2 de 3")
        self.assertContains(respuesta, "Sin Recetas Sintético")
        self.assertContains(respuesta, OMITIDO_SIN_RECETAS)
        self.assertEqual(Entrega.objects.count(), 2)
        # Sin JavaScript, una firma alterada vuelve a la lista con el aviso.
        respuesta = self.client.post(TRAMO, {"contexto": "alterada"}, follow=True)
        self.assertContains(respuesta, "fue alterada")

    def test_la_revision_marca_al_que_se_programo_entre_medio(self):
        persona = paciente(edad=85)
        receta(persona)
        html = self.revisar({"ids": [persona.pk]}).content.decode()
        programar_entrega(self.qf, persona.pk, hoy(), self.equipo["encargado2"].pk, uuid.uuid4())
        resultado = self.client.post(TRAMO, {"contexto": contexto_de(html), "desde": 0, "hasta": 1}).json()["resultados"]
        self.assertEqual(resultado, [{"paciente": persona.pk, "estado": "omitido", "motivo": OMITIDO_ABIERTA}])
        self.assertEqual(Entrega.objects.count(), 1)
