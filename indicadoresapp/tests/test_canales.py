"""Entregas por canal, motivos, entregas por día, ausentes y cifras clave (RF-13-12 a RF-13-19). Datos sintéticos."""

import uuid
from datetime import datetime, time, timedelta

from django.test import TestCase
from django.utils import timezone

from entregasapp.models import IntentoEntrega, RecetaEntrega
from entregasapp.services import guardar_domicilio, programar_entrega, registrar_entregada, registrar_no_entregada
from indicadoresapp import ausentes, canales, tablero
from indicadoresapp.mermas import CRONICO, GENERAL, Periodo
from indicadoresapp.views import _filas_canales
from recetasapp.models import EntregaReceta
from recetasapp.services import retirar_preparado
from turnosapp.models import CierreAtencion, DetalleCierre, OperacionAtencion, Turno
from .ayudas import entregada_en_la_atencion, equipo, hoy, paciente, preparada, receta


def no_entregada_en_la_atencion(preparacion, usuario, causa):
    """Cierre «atendido» de la receta sin entregarla, con su causa del RF-05-14 (vacía = cierre anterior)."""
    vinculo = preparacion.turno_receta
    operacion = OperacionAtencion.objects.create(id=uuid.uuid4(), actor=usuario, tipo="cierre",
                                                 turno_id=vinculo.turno_id, huella="x" * 64, resultado={})
    cierre = CierreAtencion.objects.create(turno=vinculo.turno, actor=usuario, operacion=operacion,
                                           resultado="sin_entrega", motivo="Motivo de prueba")
    DetalleCierre.objects.create(cierre=cierre, turno_receta=vinculo, entregada=False, causa=causa,
                                 motivo="Texto libre sintético anterior" if not causa else "Motivo de prueba")


class FarmaciaTests(TestCase):
    def setUp(self):
        self.e = equipo()
        self.tecnico = self.e["tecnico"]
        self.periodo = Periodo(hoy() - timedelta(days=29), hoy())

    def test_criterio_de_la_tabla(self):
        for _ in range(2):
            entregada_en_la_atencion(preparada(paciente(), estado="atendido", usuario=self.tecnico), self.tecnico)
        no_entregada_en_la_atencion(preparada(paciente(), estado="atendido", usuario=self.tecnico), self.tecnico, "sin_stock")
        primera = preparada(paciente(), estado="ausente", usuario=self.tecnico)
        preparada(paciente(), estado="ausente", usuario=self.tecnico)
        retirar_preparado(self.tecnico, primera.pk, uuid.uuid4())
        datos = canales.resumir(self.periodo)
        self.assertEqual((datos.farmacia_entregadas, datos.farmacia_no_entregadas, datos.farmacia_total), (2, 3, 5))
        self.assertEqual(datos.farmacia_retiradas_despues, 1)
        fila = _filas_canales(datos)[0]
        self.assertEqual((fila["texto"], fila["porcentaje"]), ("Farmacia", "40,0 %"))
        motivos = {clave: cantidad for clave, _, cantidad in datos.motivos_farmacia}
        self.assertEqual((motivos["ausente"], motivos["sin_stock"], motivos["otro"]), (2, 1, 0))
        dia = datos.por_dia[hoy()]
        self.assertEqual((dia.farmacia_atencion_o_ficha, dia.farmacia_retiradas_despues, dia.farmacia_no_entregadas), (2, 1, 3))

    def test_turno_activo_no_cuenta_y_se_anota(self):
        preparada(paciente(), estado="esperando", usuario=self.tecnico)
        datos = canales.resumir(self.periodo)
        self.assertEqual((datos.farmacia_total, datos.farmacia_en_espera), (0, 1))

    def test_confirmada_desde_la_ficha_suma_por_su_fecha(self):
        fila = EntregaReceta.objects.create(receta=receta(paciente()), numero=1)
        EntregaReceta.objects.filter(pk=fila.pk).update(
            creado_en=timezone.make_aware(datetime.combine(hoy() - timedelta(days=3), time(11))))
        datos = canales.resumir(self.periodo)
        self.assertEqual((datos.farmacia_entregadas, datos.farmacia_no_entregadas), (1, 0))
        self.assertEqual(datos.por_dia[hoy() - timedelta(days=3)].farmacia_atencion_o_ficha, 1)

    def test_retiro_posterior_cuenta_el_dia_del_retiro(self):
        antigua = preparada(paciente(), estado="ausente", dias_atras=5, usuario=self.tecnico)
        retirar_preparado(self.tecnico, antigua.pk, uuid.uuid4())
        datos = canales.resumir(self.periodo)
        self.assertEqual(datos.por_dia[hoy() - timedelta(days=5)].farmacia_no_entregadas, 1)
        self.assertEqual(datos.por_dia[hoy()].farmacia_retiradas_despues, 1)

    def test_cierre_anterior_sin_causa_cuenta_como_otro_y_no_muestra_el_texto(self):
        no_entregada_en_la_atencion(preparada(paciente(), estado="atendido", usuario=self.tecnico), self.tecnico, "")
        datos = canales.resumir(self.periodo)
        motivos = {clave: cantidad for clave, _, cantidad in datos.motivos_farmacia}
        self.assertEqual(motivos["otro"], 1)
        self.assertNotIn("Texto libre sintético", str(datos))

    def test_filtro_de_tipo(self):
        preparada(paciente(cronico=True), estado="ausente", usuario=self.tecnico)
        preparada(paciente(cronico=False), estado="ausente", usuario=self.tecnico)
        preparada(paciente(cronico=False), estado="ausente", usuario=self.tecnico)
        base = self.periodo
        self.assertEqual(canales.resumir(Periodo(base.inicio, base.fin, CRONICO)).farmacia_no_entregadas, 1)
        self.assertEqual(canales.resumir(Periodo(base.inicio, base.fin, GENERAL)).farmacia_no_entregadas, 2)


class DomicilioTests(TestCase):
    def setUp(self):
        self.e = equipo()
        self.periodo = Periodo(hoy() - timedelta(days=29), hoy())

    def visita(self, recetas):
        persona = paciente(edad=88)
        for _ in range(recetas):
            receta(persona)
        guardar_domicilio(self.e["qf"], persona.pk, {"sector": "verde", "localidad": "Localidad demo 1",
                                                     "direccion": "Camino sintético km 2", "referencias": "Portón sintético"})
        entrega = programar_entrega(self.e["qf"], persona.pk, hoy(), self.e["encargado"].pk, uuid.uuid4())
        return entrega.intentos.get()

    def test_criterio_de_la_tabla_y_motivos_por_visita(self):
        entregada = self.visita(2)
        registrar_entregada(self.e["encargado"], entregada.pk, uuid.uuid4())
        primera = RecetaEntrega.objects.filter(entrega_id=entregada.entrega_id).order_by("pk").first()
        RecetaEntrega.objects.filter(pk=primera.pk).update(
            resultado=RecetaEntrega.Resultado.NO_DESCONTADA, entrega_receta=None, causa="Receta no vigente (prueba)")
        fallida = self.visita(3)
        registrar_no_entregada(self.e["encargado"], fallida.pk, IntentoEntrega.Motivo.CAMINO, "", uuid.uuid4())
        datos = canales.resumir(self.periodo)
        self.assertEqual((datos.domicilio_entregadas, datos.domicilio_no_entregadas, datos.domicilio_total), (1, 4, 5))
        self.assertEqual(datos.domicilio_no_descontadas, 1)
        self.assertEqual(_filas_canales(datos)[1]["porcentaje"], "20,0 %")
        motivos = {clave: cantidad for clave, _, cantidad in datos.motivos_domicilio}
        self.assertEqual((motivos["camino_intransitable"], datos.visitas_fallidas), (1, 1))
        self.assertEqual(datos.efectividad_domicilio, 20)

    def test_visita_sin_resultado_no_cuenta(self):
        self.visita(1)
        datos = canales.resumir(self.periodo)
        self.assertEqual(datos.domicilio_total, 0)


class AusentesTests(TestCase):
    def setUp(self):
        self.lunes = hoy() - timedelta(days=hoy().weekday())

    def turno(self, estado, numero, hora=10, fecha=None):
        persona = paciente()
        fecha = fecha or self.lunes
        momento = timezone.make_aware(datetime.combine(fecha, time(hora, 15)))
        turno = Turno.objects.create(paciente=persona, rut=persona.rut, fecha=fecha, letra="G", numero=numero,
                                     tipo_atencion="general", estado=estado,
                                     cerrado_en=None if estado in ("esperando", "llamado") else momento)
        Turno.objects.filter(pk=turno.pk).update(creado_en=momento)
        return turno

    def test_celda_por_dia_y_hora_de_emision(self):
        for numero, estado in enumerate(("ausente", "atendido", "atendido", "esperando"), start=1):
            self.turno(estado, numero)
        datos = ausentes.resumir(Periodo(self.lunes, hoy()))
        self.assertEqual([fila["dia"] for fila in datos.filas], ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"])
        self.assertEqual(datos.horas, list(range(8, 20)))
        celda = datos.filas[0]["celdas"][datos.horas.index(10)]
        self.assertEqual((celda["emitidos"], celda["ausentes"], celda["porcentaje"]), (4, 1, 25))
        self.assertEqual((datos.emitidos, datos.ausentes), (4, 1))
        self.assertEqual(datos.por_dia[self.lunes], (4, 1))

    def test_fin_de_semana_y_horas_fuera_del_horario_se_agregan(self):
        sabado = self.lunes - timedelta(days=2)
        self.turno("ausente", 1, hora=21, fecha=sabado)
        datos = ausentes.resumir(Periodo(sabado, hoy()))
        self.assertIn("Sábado", [fila["dia"] for fila in datos.filas])
        self.assertNotIn("Domingo", [fila["dia"] for fila in datos.filas])
        self.assertEqual(datos.horas[-1], 21)


class CifrasClaveTests(TestCase):
    def setUp(self):
        self.e = equipo()
        self.tecnico = self.e["tecnico"]

    def test_estante_mas_de_14_dias(self):
        for _ in range(3):
            preparada(paciente(), dias_atras=20, usuario=self.tecnico)
        preparada(paciente(), dias_atras=3, usuario=self.tecnico)
        datos = tablero.armar(Periodo(hoy() - timedelta(days=29), hoy()))
        estante = {cifra.clave: cifra for cifra in datos.cifras}["estante"]
        self.assertEqual((estante.valor, estante.detalle), ("3", "de 4 recetas sin retirar"))

    def test_sin_datos_del_periodo_anterior(self):
        entregada_en_la_atencion(preparada(paciente(), estado="atendido", usuario=self.tecnico), self.tecnico)
        datos = tablero.armar(Periodo(hoy() - timedelta(days=9), hoy()))
        cifras = {cifra.clave: cifra for cifra in datos.cifras}
        self.assertEqual(cifras["entregadas"].valor, "1")
        self.assertEqual(cifras["entregadas"].comparacion, "Sin datos del período anterior")
        self.assertEqual(cifras["efectividad"].detalle, "Sin visitas en el período")

    def test_comparacion_con_palabras(self):
        for _ in range(2):
            entregada_en_la_atencion(preparada(paciente(), estado="atendido", usuario=self.tecnico), self.tecnico)
        entregada_en_la_atencion(preparada(paciente(), estado="atendido", dias_atras=12, usuario=self.tecnico), self.tecnico)
        periodo = Periodo(hoy() - timedelta(days=9), hoy())
        datos = tablero.armar(periodo)
        entregadas = {cifra.clave: cifra for cifra in datos.cifras}["entregadas"]
        self.assertEqual(entregadas.comparacion, f"100,0 % más que {periodo.anterior_equivalente().rango}")
        self.assertEqual((entregadas.tendencia, entregadas.sentido), ("buena", "sube"))
