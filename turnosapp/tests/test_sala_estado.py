"""Proyección pública de sala: jornada chilena, privacidad y HTTP de solo lectura."""
import json
from datetime import datetime, timedelta, timezone as tz

from django.test import TestCase
from django.urls import reverse

from recetasapp.models import Receta
from turnosapp.cola import procesar_pendiente
from turnosapp.models import AnuncioSala, EventoTurno, Turno, Ventanilla
from turnosapp.sala import estado_sala
from .datos_cola import DatosCola


class EstadoSalaTests(DatosCola, TestCase):
    def test_estado_vacio_y_hora_del_servidor(self):
        with self.assertNumQueries(5):
            estado = estado_sala()
        self.assertEqual(estado["tipo"], "estado")
        self.assertEqual(estado["fecha"], "2026-11-02")
        self.assertEqual(estado["ahora"], "2026-11-02T12:00:00-03:00")
        self.assertEqual(estado["ultimo_id"], 0)
        self.assertEqual(estado["recientes"], [])
        self.assertEqual(estado["espera"], {"cantidad": 0, "numeros": [], "restantes": 0})
        self.assertTrue(all(v["estado"] == "sin_atencion" for v in estado["ventanillas"]))

    def test_tarjetas_llamado_disponible_y_sin_atencion(self):
        v1 = self.activar(1)
        turno = self.turno()
        procesar_pendiente(self.pendiente().pk)
        self.activar(2)
        v3 = self.activar(3)
        Ventanilla.objects.filter(pk=v3.pk).update(fecha_activacion=self.fecha - timedelta(days=1))
        tarjetas = {v["numero"]: v for v in estado_sala()["ventanillas"]}
        self.assertEqual(tarjetas[1], {"numero": 1, "estado": "llamado", "llamado": turno.numero,
            "desde": "2026-11-02T12:00:00-03:00"})
        self.assertEqual(tarjetas[2]["estado"], "disponible")
        self.assertEqual(tarjetas[3]["estado"], "sin_atencion")
        self.assertEqual(tarjetas[4]["estado"], "sin_atencion")
        # Deshabilitar no esconde la atención que sigue vigente.
        Ventanilla.objects.filter(pk=v1.pk).update(habilitada=False, automatico=False)
        self.assertEqual(estado_sala()["ventanillas"][0]["llamado"], turno.numero)

    def test_ventanilla_deshabilitada_o_pausada_y_retirada(self):
        ventanilla = self.activar()
        Ventanilla.objects.filter(pk=ventanilla.pk).update(automatico=False)
        Ventanilla.objects.filter(numero=2).update(habilitada=False)
        Ventanilla.objects.filter(numero=4).update(retirada=True, habilitada=False)
        tarjetas = estado_sala()["ventanillas"]
        self.assertEqual([v["numero"] for v in tarjetas], [1, 2, 3])
        self.assertTrue(all(v["estado"] == "sin_atencion" for v in tarjetas))

    def test_finalizacion_o_ausencia_limpian_tarjeta_sin_borrar_recientes(self):
        self.activar()
        self.turno()
        procesar_pendiente(self.pendiente().pk)
        for estado in ("atendido", "ausente"):
            with self.subTest(estado=estado):
                Turno.objects.update(estado=estado, ventanilla=None, operador=None, cerrado_en=self.ahora)
                publico = estado_sala()
                self.assertEqual(publico["ventanillas"][0]["estado"], "disponible")
                self.assertIsNone(publico["ventanillas"][0]["llamado"])
                self.assertEqual(len(publico["recientes"]), 1)

    def test_cuarenta_en_espera_en_orden_numerico_y_restantes(self):
        for _ in range(43):
            self.turno()
        publico = estado_sala()
        self.assertEqual(publico["espera"], {"cantidad": 43, "numeros": list(range(1, 41)), "restantes": 3})
        respuesta = self.client.get(reverse("turnosapp:sala"))
        self.assertContains(respuesta, "43 personas en espera")
        self.assertContains(respuesta, "y 3 más")
        self.assertNotContains(respuesta, "próximos")
        self.assertNotContains(respuesta, "estimado")

    def crear_historial(self, cantidad):
        self.activar()
        turno = self.turno()
        procesar_pendiente(self.pendiente().pk)
        primero = AnuncioSala.objects.get()
        for secuencia in range(2, cantidad + 1):
            instante = self.ahora + timedelta(seconds=secuencia)
            evento = EventoTurno.objects.create(turno=turno, secuencia=secuencia, accion="rellamado",
                instante=instante, ventanilla=primero.evento.ventanilla)
            AnuncioSala.objects.create(evento=evento, fecha=self.fecha, numero=turno.numero,
                ventanilla_numero=1, accion="rellamado", instante=instante)
        return turno

    def test_estado_guarda_veinte_recientes_y_html_muestra_seis(self):
        self.crear_historial(23)
        recientes = estado_sala()["recientes"]
        ids = list(AnuncioSala.objects.order_by("-id").values_list("pk", flat=True)[:20])
        self.assertEqual([a["id"] for a in recientes], ids)
        self.assertEqual(estado_sala()["ultimo_id"], ids[0])
        html = self.client.get(reverse("turnosapp:sala")).content.decode()
        lista = html.split('<ol id="sala-recientes">', 1)[1].split("</ol>", 1)[0]
        self.assertEqual(lista.count("<li>"), 6)

    def test_medianoche_cambia_jornada_sin_historial_ni_espera_anteriores(self):
        self.crear_historial(2)
        self.turno()
        antes = estado_sala(datetime(2026, 11, 3, 2, 59, 59, tzinfo=tz.utc))
        despues = estado_sala(datetime(2026, 11, 3, 3, 0, tzinfo=tz.utc))
        self.assertEqual(antes["fecha"], "2026-11-02")
        self.assertEqual(len(antes["recientes"]), 2)
        self.assertEqual(despues["fecha"], "2026-11-03")
        self.assertEqual(despues["recientes"], [])
        self.assertEqual(despues["ultimo_id"], 0)
        self.assertEqual(despues["espera"]["cantidad"], 0)
        self.assertTrue(all(v["llamado"] is None and v["estado"] == "sin_atencion" for v in despues["ventanillas"]))
        self.assertEqual(AnuncioSala.objects.count(), 2)

    def test_contrato_publico_tiene_solo_campos_permitidos(self):
        self.crear_historial(1)
        self.turno()
        estado = self.client.get(reverse("turnosapp:sala_estado")).json()
        self.assertEqual(set(estado), {"tipo", "ahora", "fecha", "ultimo_id", "ventanillas", "recientes", "espera"})
        self.assertEqual(set(estado["espera"]), {"cantidad", "numeros", "restantes"})
        for tarjeta in estado["ventanillas"]:
            self.assertEqual(set(tarjeta), {"numero", "estado", "llamado", "desde"})
        for anuncio in estado["recientes"]:
            self.assertEqual(set(anuncio), {"id", "numero", "ventanilla", "accion", "instante"})

    def test_html_y_json_no_filtran_identidad_categorias_ni_recetas(self):
        turno = self.crear_historial(1)
        paciente = turno.paciente
        paciente.nombres, paciente.apellidos = "PersonaSinteticaSalaUnica", "ApellidoPrivadoDemo"
        paciente.save()
        receta = Receta.objects.create(paciente=paciente, codigo="RECETA-PRIVADA-SALA-DEMO",
            fecha_inicio=self.fecha, fecha_fin_exclusiva=self.fecha + timedelta(days=30),
            vigencia_meses=1, max_entregas=3)
        privados = [paciente.rut, paciente.nombres, paciente.apellidos, receta.codigo,
            str(turno.operacion_id), str(turno.eventos.get().pk), "preferencial", "cronicos",
            '"paciente"', '"turno"', '"evento"', '"operacion"', '"tipo_atencion"', '"recetas"']
        for nombre in ("sala", "sala_estado"):
            respuesta = self.client.get(reverse("turnosapp:" + nombre))
            for privado in privados:
                with self.subTest(ruta=nombre, dato=privado):
                    self.assertNotContains(respuesta, privado)
        html = self.client.get(reverse("turnosapp:sala")).content.decode()
        inicial = html.split('<script id="sala-estado-inicial" type="application/json">', 1)[1].split("</script>", 1)[0]
        self.assertEqual(json.loads(inicial), estado_sala())
        self.assertNotIn("navbar", html)
        self.assertNotIn("</footer>", html)

    def test_publico_sin_cookies_no_store_y_sin_escrituras(self):
        for nombre in ("sala", "sala_estado"):
            for metodo in (self.client.get, self.client.head):
                with self.subTest(ruta=nombre, metodo=metodo.__name__):
                    with self.assertNumQueries(5):
                        respuesta = metodo(reverse("turnosapp:" + nombre))
                    self.assertEqual(respuesta.status_code, 200)
                    self.assertIn("no-store", respuesta["Cache-Control"])
                    self.assertFalse(respuesta.cookies)
        self.assertFalse(self.client.cookies)
        self.assertFalse(AnuncioSala.objects.exists())
        self.assertFalse(EventoTurno.objects.exists())

    def test_post_y_otros_metodos_no_mutan_el_estado(self):
        self.turno()
        for nombre in ("sala", "sala_estado"):
            for metodo in (self.client.post, self.client.put, self.client.delete):
                self.assertEqual(metodo(reverse("turnosapp:" + nombre), {"numero": 99}).status_code, 405)
        self.assertEqual(Turno.objects.get().estado, "esperando")
        self.assertFalse(AnuncioSala.objects.exists())

    def test_cuenta_inactiva_o_sin_perfil_no_impide_acceso_publico(self):
        from django.contrib.auth import get_user_model
        actor = get_user_model().objects.create_user(username="sala_sin_perfil_demo")
        for activo in (True, False):
            actor.is_active = activo
            actor.save()
            self.client.force_login(actor)
            for nombre in ("sala", "sala_estado"):
                self.assertEqual(self.client.get(reverse("turnosapp:" + nombre)).status_code, 200)

    def test_totem_y_panel_siguen_disponibles(self):
        self.assertEqual(self.client.get(reverse("turnosapp:totem")).status_code, 200)
        self.assertEqual(self.client.get(reverse("turnosapp:panel")).status_code, 302)
        self.client.force_login(self.personal["tecnico"])
        self.assertEqual(self.client.get(reverse("turnosapp:panel")).status_code, 200)

    def test_pantalla_base_tiene_estados_vacios_y_control_de_texto(self):
        respuesta = self.client.get(reverse("turnosapp:sala"))
        for texto in ("Aún no hay llamados hoy.", "Nadie en espera.", "Sonido desactivado.",
            "Sin atención", "Texto grande", 'aria-live="polite"', 'id="contenido"'):
            self.assertContains(respuesta, texto)

    def test_enlace_sala_solo_para_roles_autorizados_en_pestana_nueva(self):
        from coreapp.tests.test_plantillas import DocumentoHTML
        for nombre, permitido in (("qf", True), ("tecnico", True), ("admin", True), ("encargado", False)):
            self.client.force_login(self.personal[nombre])
            respuesta = self.client.get("/")
            self.assertEqual(respuesta.status_code, 200)
            enlaces = [atributos for etiqueta, atributos in DocumentoHTML(respuesta.content.decode()).elementos
                if etiqueta == "a" and atributos.get("href") == reverse("turnosapp:sala")]
            self.assertEqual(bool(enlaces), permitido)
            if permitido:
                self.assertEqual(enlaces[0]["target"], "_blank")
                self.assertIn("noopener", enlaces[0]["rel"].split())
        self.client.logout()
        self.assertNotContains(self.client.get(reverse("usuariosapp:login")), "Pantalla de sala", status_code=200)

    def test_menu_revalida_el_rol_pero_la_sala_sigue_publica(self):
        from django.contrib.auth.models import Group
        from coreapp.roles import ENCARGADO
        tecnico = self.personal["tecnico"]
        self.client.force_login(tecnico)
        self.assertContains(self.client.get("/"), "Pantalla de sala")
        tecnico.groups.set([Group.objects.get(name=ENCARGADO)])
        self.assertNotContains(self.client.get("/"), "Pantalla de sala")
        self.assertEqual(self.client.get(reverse("turnosapp:sala")).status_code, 200)

    def test_sala_tiene_estructura_accesible_sin_navegacion_privada(self):
        from coreapp.tests.test_plantillas import DocumentoHTML
        html = self.client.get(reverse("turnosapp:sala")).content.decode()
        elementos = DocumentoHTML(html).elementos
        ids = [a["id"] for _, a in elementos if "id" in a]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(sum(t == "main" for t, _ in elementos), 1)
        self.assertEqual(sum(t == "h1" for t, _ in elementos), 1)
        self.assertFalse(any(t in ("nav", "footer") for t, _ in elementos))
        ultimo = next(a for _, a in elementos if a.get("id") == "sala-ultimo")
        self.assertEqual((ultimo["role"], ultimo["aria-live"], ultimo["aria-atomic"]), ("status", "polite", "true"))
        for identificador in ("sala-activar-sonido", "sala-probar-sonido"):
            boton = next(a for t, a in elementos if t == "button" and a.get("id") == identificador)
            self.assertEqual(boton["type"], "button")
        self.assertIn('href="#contenido"', html)
        self.assertIn("data-texto-nivel", html)
        self.assertIn("js/sala.js", html)
        self.assertIn('data-estado-url="/turnos/sala/estado/"', html)
