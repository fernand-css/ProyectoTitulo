"""Canal público real ASGI y ciclo de vida del vigilante con base compartida."""
import asyncio
import json
import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from channels.db import database_sync_to_async
from channels.exceptions import ChannelFull
from channels.routing import URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings

from turnosapp.atencion import rellamar
from turnosapp.cola import procesar_pendiente
from turnosapp.models import AnuncioSala, EventoTurno
from turnosapp.routing import websocket_urlpatterns
from turnosapp.vigilante import VigilanteSala
from .datos_cola import DatosCola


@override_settings(ALLOWED_HOSTS=["testserver"], SALA_INTERVALO=0.03)
class CanalSalaTests(DatosCola, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.vigilante = VigilanteSala()
        sustitucion = patch("turnosapp.consumers.vigilante", self.vigilante)
        sustitucion.start()
        self.addCleanup(sustitucion.stop)
        self.aplicacion = AllowedHostsOriginValidator(URLRouter(websocket_urlpatterns))
        self.clientes = []

    async def conectar(self, direccion="127.0.0.1", origen="http://testserver"):
        cliente = WebsocketCommunicator(self.aplicacion, "/ws/sala/", headers=[(b"origin", origen.encode())])
        cliente.scope["client"] = (direccion, 12345)
        self.clientes.append(cliente)
        aceptada, codigo = await cliente.connect()
        return cliente, aceptada, codigo

    async def cerrar(self):
        for cliente in self.clientes:
            await cliente.disconnect()
        self.assertFalse(self.vigilante.conexiones)
        self.assertIsNone(self.vigilante.tarea)

    async def recibir_tipo(self, cliente, tipo):
        for _ in range(10):
            mensaje = await cliente.receive_json_from(timeout=2)
            if mensaje["tipo"] == tipo:
                return mensaje
        self.fail(f"No llegó el mensaje {tipo}")

    async def test_estado_inicial_e_historial_sin_reemitir(self):
        await database_sync_to_async(self.activar)()
        await database_sync_to_async(self.turno)()
        await database_sync_to_async(procesar_pendiente)((await database_sync_to_async(self.pendiente)()).pk)
        cliente, aceptada, _ = await self.conectar()
        try:
            self.assertTrue(aceptada)
            estado = await cliente.receive_json_from()
            self.assertEqual(estado["tipo"], "estado")
            self.assertEqual(len(estado["recientes"]), 1)
            self.assertTrue(await cliente.receive_nothing(timeout=0.1))
        finally:
            await self.cerrar()

    async def test_cuatro_llamados_en_orden_una_vez_para_dos_pantallas(self):
        for numero in range(1, 5):
            await database_sync_to_async(self.activar)(numero)
            await database_sync_to_async(self.turno)()
        clientes = [(await self.conectar())[0] for _ in range(2)]
        try:
            for cliente in clientes:
                await cliente.receive_json_from()
            pendiente = await database_sync_to_async(self.pendiente)()
            await database_sync_to_async(procesar_pendiente)(pendiente.pk)
            ids = await database_sync_to_async(lambda: list(AnuncioSala.objects.order_by("id").values_list("pk", flat=True)))()
            for cliente in clientes:
                anuncios = [await self.recibir_tipo(cliente, "anuncio") for _ in range(4)]
                self.assertEqual([a["id"] for a in anuncios], ids)
                self.assertEqual(set(anuncios[0]), {"tipo", "id", "numero", "ventanilla", "accion", "instante"})
                self.assertEqual((await self.recibir_tipo(cliente, "estado"))["ultimo_id"], ids[-1])
                self.assertTrue(await cliente.receive_nothing(timeout=0.1))
        finally:
            await self.cerrar()

    async def test_mensajes_validos_invalidos_y_binarios_se_ignoran(self):
        cliente, _, _ = await self.conectar()
        try:
            await cliente.receive_json_from()
            await cliente.send_json_to({"accion": "llamar", "numero": 99})
            await cliente.send_to(text_data="esto no es JSON")
            await cliente.send_to(bytes_data=b"ignorar")
            self.assertTrue(await cliente.receive_nothing(timeout=0.1))
            self.assertFalse(await database_sync_to_async(AnuncioSala.objects.exists)())
            self.assertFalse(await database_sync_to_async(EventoTurno.objects.exists)())
        finally:
            await self.cerrar()

    async def test_origen_no_permitido_o_ausente_rechazado(self):
        for origen in ("http://ajeno.invalid", "null", ""):
            cliente, aceptada, _ = await self.conectar(origen=origen)
            self.assertFalse(aceptada)
        await self.cerrar()

    async def test_limite_cinco_por_direccion_y_recuperacion_de_cupo(self):
        try:
            for _ in range(5):
                cliente, aceptada, _ = await self.conectar()
                self.assertTrue(aceptada)
                await cliente.receive_json_from()
            rechazado, aceptada, codigo = await self.conectar()
            self.assertFalse(aceptada)
            self.assertEqual(codigo, 1013)
            await self.clientes.pop(0).disconnect()
            nuevo, aceptada, _ = await self.conectar()
            self.assertTrue(aceptada)
            await nuevo.receive_json_from()
            self.assertEqual(len(self.vigilante.conexiones), 5)
        finally:
            await self.cerrar()

    async def test_limite_veinte_total_no_afecta_conexiones_existentes(self):
        try:
            for indice in range(20):
                cliente, aceptada, _ = await self.conectar(direccion=f"127.0.0.{indice // 5 + 1}")
                self.assertTrue(aceptada)
                await cliente.receive_json_from()
            cliente, aceptada, codigo = await self.conectar(direccion="127.0.0.5")
            self.assertFalse(aceptada)
            self.assertEqual(codigo, 1013)
            self.assertEqual(len(self.vigilante.conexiones), 20)
            await self.vigilante.revisar(latido=True)
            for cliente in self.clientes[:20]:
                self.assertEqual((await cliente.receive_json_from())["tipo"], "latido")
        finally:
            await self.cerrar()

    async def test_mensaje_excesivo_cierra_sin_registrar_contenido(self):
        cliente, _, _ = await self.conectar()
        try:
            await cliente.receive_json_from()
            await cliente.send_to(text_data="x" * 4097)
            mensaje = await cliente.receive_output()
            self.assertEqual(mensaje, {"type": "websocket.close", "code": 1009})
        finally:
            await self.cerrar()

    async def test_vigilante_compartido_se_detiene_solo_con_la_ultima_pantalla(self):
        primero, _, _ = await self.conectar()
        await primero.receive_json_from()
        tarea = self.vigilante.tarea
        segundo, _, _ = await self.conectar()
        await segundo.receive_json_from()
        self.assertIs(self.vigilante.tarea, tarea)
        await primero.disconnect()
        self.clientes.remove(primero)
        self.assertFalse(tarea.done())
        await self.cerrar()
        self.assertTrue(tarea.done())

    async def test_fallo_lectura_reintenta_sin_cerrar_y_no_filtra_excepcion(self):
        cliente, _, _ = await self.conectar()
        try:
            await cliente.receive_json_from()
            with patch("turnosapp.vigilante.leer_sala", side_effect=RuntimeError("DETALLE-PRIVADO-DEMO")):
                with self.assertLogs("turnosapp.vigilante", level="ERROR") as registros:
                    await asyncio.sleep(0.12)
                self.assertNotIn("DETALLE-PRIVADO-DEMO", " ".join(registros.output))
            self.assertFalse(self.vigilante.tarea.done())
            await self.vigilante.revisar(latido=True)
            self.assertEqual((await cliente.receive_json_from())["tipo"], "latido")
        finally:
            await self.cerrar()

    async def test_anuncio_menor_confirmado_despues_se_entrega_solo_una_vez(self):
        await database_sync_to_async(self.activar)()
        turno = await database_sync_to_async(self.turno)()
        await database_sync_to_async(procesar_pendiente)((await database_sync_to_async(self.pendiente)()).pk)
        # Simula visibilidad tardía conservando el id reservado y el evento.
        oculto = await database_sync_to_async(AnuncioSala.objects.get)()
        await database_sync_to_async(AnuncioSala.objects.filter(pk=oculto.pk).delete)()
        cliente, _, _ = await self.conectar()
        try:
            await cliente.receive_json_from()
            await database_sync_to_async(rellamar)(self.personal["tecnico"], turno.pk, uuid.uuid4())
            mayor = await self.recibir_tipo(cliente, "anuncio")
            await self.recibir_tipo(cliente, "estado")
            nuevo, _, _ = await self.conectar(direccion="127.0.0.2")
            await nuevo.receive_json_from()
            await database_sync_to_async(oculto.save)(force_insert=True)
            for pantalla in (cliente, nuevo):
                tarde = await self.recibir_tipo(pantalla, "anuncio")
                self.assertEqual(tarde["id"], oculto.pk)
                self.assertLess(tarde["id"], mayor["id"])
                await self.recibir_tipo(pantalla, "estado")
                self.assertTrue(await pantalla.receive_nothing(timeout=0.1))
        finally:
            await self.cerrar()

    async def test_latido_periodico(self):
        with override_settings(SALA_LATIDO=0.06):
            cliente, _, _ = await self.conectar()
            try:
                await cliente.receive_json_from()
                mensaje = await self.recibir_tipo(cliente, "latido")
                self.assertEqual(set(mensaje), {"tipo", "ahora"})
            finally:
                await self.cerrar()

    async def test_saturacion_cierra_en_vez_de_perder_anuncios_silenciosamente(self):
        cliente, _, _ = await self.conectar()
        try:
            await cliente.receive_json_from()
            suscripcion = next(iter(self.vigilante.conexiones.values()))
            suscripcion.capa = AsyncMock()
            suscripcion.capa.send.side_effect = ChannelFull()
            await self.vigilante.revisar(latido=True)
            self.assertEqual((await cliente.receive_output())["code"], 1013)
            self.assertFalse(self.vigilante.conexiones)
        finally:
            await self.cerrar()

    async def test_sin_pantallas_no_lee_base_ni_inicia_tarea(self):
        with patch("turnosapp.vigilante.leer_sala") as lectura:
            await self.vigilante.revisar()
            lectura.assert_not_called()
        self.assertIsNone(self.vigilante.tarea)

    async def test_error_inicial_rechaza_sin_consumir_cupo(self):
        with patch("turnosapp.vigilante.leer_sala", side_effect=RuntimeError("detalle sintético")):
            with self.assertLogs("turnosapp.consumers", level="ERROR") as registros:
                _, aceptada, codigo = await self.conectar()
        self.assertFalse(aceptada)
        self.assertEqual(codigo, 1011)
        self.assertNotIn("detalle sintético", " ".join(registros.output))
        await self.cerrar()

    async def test_cambio_de_jornada_limpia_estado_sin_reemitir_historial(self):
        await database_sync_to_async(self.activar)()
        await database_sync_to_async(self.turno)()
        await database_sync_to_async(procesar_pendiente)((await database_sync_to_async(self.pendiente)()).pk)
        cliente, _, _ = await self.conectar()
        try:
            await cliente.receive_json_from()
            with patch("turnosapp.vigilante.timezone.now", return_value=self.ahora + timedelta(days=1)):
                await self.vigilante.revisar()
                estado = await self.recibir_tipo(cliente, "estado")
                self.assertEqual(estado["recientes"], [])
                self.assertEqual(estado["fecha"], "2026-11-03")
                self.assertTrue(all(v["llamado"] is None for v in estado["ventanillas"]))
        finally:
            await self.cerrar()
