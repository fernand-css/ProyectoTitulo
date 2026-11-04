"""Las consultas del resumen y de la lista de recetas coinciden con la insignia que muestra cada fila."""

from datetime import date
from random import Random
from unittest.mock import patch

from django.test import TestCase

from coreapp.utils.sinteticos import generar_ruts
from recetasapp import consultas, presentacion
from recetasapp.models import Paciente, Receta
from recetasapp.services import crear_receta
from .ayudas import actores

HOY = date(2026, 11, 2)


class ConsultasTests(TestCase):
    def setUp(self):
        reloj = patch("recetasapp.services.timezone.localdate", return_value=HOY)
        reloj.start()
        self.addCleanup(reloj.stop)
        self.qf = actores()["qf"]
        self.ruts = iter(generar_ruts(40, Random(11)))
        self.recetas = {}

    def receta(self, nombre, inicio, meses=6, maximo=6, completadas=0, paciente=None):
        paciente = paciente or Paciente.objects.create(
            rut=next(self.ruts), nombres=nombre, apellidos="Sintético", fecha_nacimiento=date(1950, 1, 1),
        )
        receta = crear_receta(self.qf, paciente_id=paciente.pk, codigo=f"C-{nombre}", fecha_inicio=inicio, vigencia_meses=meses, max_entregas=maximo)
        if completadas:
            # El contador solo lo mueve la entrega; aquí se fija directo para armar el escenario.
            Receta.objects.filter(pk=receta.pk).update(entregas_completadas=completadas)
            receta.refresh_from_db()
        self.recetas[nombre] = receta
        return receta

    def armar(self):
        self.receta("holgada", date(2026, 1, 1), meses=12)            # fin 2027-01-01: vigente, no vence pronto
        self.receta("borde30", date(2026, 6, 2))                      # fin 2026-12-02 = hoy + 30: por vencer
        self.receta("borde31", date(2026, 6, 3))                      # fin 2026-12-03 = hoy + 31: no
        self.receta("ultimodia", date(2026, 5, 3))                    # fin 2026-11-03: queda un día
        self.receta("venceHoy", date(2026, 5, 2))                     # fin 2026-11-02 = hoy: ya vencida
        self.receta("futura", date(2027, 1, 1))
        self.receta("agotada", date(2026, 9, 1), completadas=6)
        self.receta("vencida", date(2025, 1, 1))
        self.receta("vencidaYAgotada", date(2025, 1, 1), completadas=6)

    def claves(self, receta):
        """Qué filtros excluyentes la incluyen, según la base de datos."""
        return {
            clave for clave in ("vigente", "futura", "agotada", "vencida")
            if consultas.filtrar_recetas(Receta.objects.filter(pk=receta.pk), clave, HOY).exists()
        }

    def test_cada_receta_cae_en_exactamente_la_situacion_que_muestra_su_insignia(self):
        self.armar()
        for nombre, receta in self.recetas.items():
            with self.subTest(receta=nombre):
                self.assertEqual(self.claves(receta), {presentacion.situacion(receta, HOY)["clave"]})

    def test_por_vencer_es_la_parte_de_las_vigentes_que_vence_en_treinta_dias_o_menos(self):
        self.armar()
        esperadas = {"borde30", "ultimodia"}
        halladas = {n for n, r in self.recetas.items() if consultas.filtrar_recetas(Receta.objects.filter(pk=r.pk), "por_vencer", HOY).exists()}
        self.assertEqual(halladas, esperadas)
        for nombre in esperadas:
            self.assertEqual(presentacion.situacion(self.recetas[nombre], HOY)["clave"], "vigente")

    def test_los_conteos_suman_el_total_y_coinciden_con_las_listas(self):
        self.armar()
        conteos = consultas.contar_recetas(HOY)
        self.assertEqual(conteos["total"], 9)
        self.assertEqual(conteos["vigente"] + conteos["futura"] + conteos["agotada"] + conteos["vencida"], conteos["total"])
        self.assertEqual((conteos["vigente"], conteos["por_vencer"], conteos["futura"], conteos["agotada"], conteos["vencida"]), (4, 2, 1, 1, 3))
        for clave in ("vigente", "por_vencer", "futura", "agotada", "vencida"):
            with self.subTest(clave=clave):
                self.assertEqual(consultas.filtrar_recetas(Receta.objects.all(), clave, HOY).count(), conteos[clave])
        self.assertEqual(consultas.filtrar_recetas(Receta.objects.all(), "", HOY).count(), 9)

    def test_por_vencer_ordena_por_la_que_vence_primero_y_respeta_el_limite(self):
        self.armar()
        self.assertEqual([r.codigo for r in consultas.recetas_por_vencer(HOY)], ["C-ultimodia", "C-borde30"])
        self.assertEqual(len(consultas.recetas_por_vencer(HOY, limite=1)), 1)

    def test_pacientes_sin_vigente_incluye_a_quien_no_tiene_recetas_y_excluye_a_quien_tiene_una(self):
        self.armar()
        sin_recetas = Paciente.objects.create(rut=next(self.ruts), nombres="SinRecetas", apellidos="Sintético", fecha_nacimiento=date(1950, 1, 1))
        # Con una vencida y una vigente, el paciente sí puede retirar.
        mixto = Paciente.objects.create(rut=next(self.ruts), nombres="Mixto", apellidos="Sintético", fecha_nacimiento=date(1950, 1, 1))
        self.receta("mixtoVieja", date(2025, 1, 1), paciente=mixto)
        self.receta("mixtoVigente", date(2026, 1, 1), meses=12, paciente=mixto)
        nombres = set(consultas.pacientes_sin_vigente(HOY).values_list("nombres", flat=True))
        # Las cuatro vigentes (holgada, borde30, borde31, ultimodia) y «Mixto» pueden retirar; el resto no.
        self.assertEqual(nombres, {sin_recetas.nombres, "futura", "agotada", "vencida", "vencidaYAgotada", "venceHoy"})
        self.assertNotIn("Mixto", nombres)

    def test_ultima_carga_sin_cargas_es_none(self):
        self.assertIsNone(consultas.ultima_carga())
