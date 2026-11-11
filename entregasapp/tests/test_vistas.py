"""Pantallas de la farmacia y del domicilio por HTTP (RF-08-03 a RF-08-07, RF-08-11 a RF-08-13)."""

import uuid
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse

from entregasapp.models import Domicilio, Entrega, FotoDomicilio, InscripcionReparto
from entregasapp.services import (
    guardar_domicilio, inscribir_excepcion, programar_entrega, registrar_entregada, registrar_no_entregada,
)
from recetasapp.models import Receta
from .ayudas import archivo, equipo, hoy, imagen, paciente, receta
from .test_fotos import CarpetaPrivadaMixin

DOMICILIO = {"sector": "verde", "localidad": "Dadinco", "direccion": "Camino a Dadinco km 2", "referencias": "Casa roja",
             "latitud": "", "longitud": "", "precision_metros": ""}


class ProgramarVistaTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.client.force_login(self.equipo["qf"])
        self.persona = paciente(edad=86)
        self.vigente = receta(self.persona, "VIGENTE-1")
        receta(self.persona, "VENCIDA-1", inicio=hoy() - timedelta(days=300), fin=hoy())

    def test_buscar_revisar_y_confirmar_sin_rut_en_la_url(self):
        url = reverse("entregasapp:programar")
        busqueda = self.client.post(url, {"accion": "buscar", "buscar": self.persona.rut})
        self.assertContains(busqueda, self.persona.apellidos)
        self.assertNotIn(self.persona.rut, busqueda.request["PATH_INFO"] + busqueda.request.get("QUERY_STRING", ""))
        pagina = self.client.get(url, {"paciente": self.persona.pk})
        self.assertContains(pagina, "Revisar recetas")
        datos = {"paciente": self.persona.pk, "fecha": hoy().isoformat(), "encargado": self.equipo["encargado"].pk,
                 "operacion_id": str(uuid.uuid4())}
        revision = self.client.post(url, {**datos, "accion": "revisar"})
        self.assertContains(revision, "Receta VIGENTE-1")
        self.assertNotContains(revision, "VENCIDA-1")
        self.assertFalse(Entrega.objects.exists())
        confirmada = self.client.post(url, {**datos, "accion": "confirmar"})
        entrega = Entrega.objects.get()
        self.assertRedirects(confirmada, reverse("entregasapp:detalle", args=[entrega.pk]))
        self.assertEqual(list(entrega.recetas.values_list("receta_id", flat=True)), [self.vigente.pk])
        # Repetir el mismo POST no crea otra entrega.
        self.client.post(url, {**datos, "accion": "confirmar"})
        self.assertEqual(Entrega.objects.count(), 1)
        # Con otra operación, el sistema enlaza a la entrega abierta.
        otra = self.client.post(url, {**datos, "operacion_id": str(uuid.uuid4()), "accion": "confirmar"})
        self.assertRedirects(otra, reverse("entregasapp:detalle", args=[entrega.pk]))

    def test_fecha_pasada_y_paciente_no_elegible(self):
        url = reverse("entregasapp:programar")
        datos = {"paciente": self.persona.pk, "fecha": (hoy() - timedelta(days=1)).isoformat(),
                 "encargado": self.equipo["encargado"].pk, "operacion_id": str(uuid.uuid4()), "accion": "confirmar"}
        self.assertContains(self.client.post(url, datos), "La fecha debe ser hoy o posterior.")
        joven = paciente(edad=40)
        pagina = self.client.get(url, {"paciente": joven.pk})
        self.assertContains(pagina, "no es elegible")
        self.assertNotContains(pagina, "Revisar recetas")
        self.assertFalse(Entrega.objects.exists())

    def test_el_tecnico_ve_la_programacion_sin_botones_de_cambio(self):
        programar_entrega(self.equipo["qf"], self.persona.pk, hoy(), self.equipo["encargado"].pk, uuid.uuid4())
        self.client.force_login(self.equipo["tecnico"])
        lista = self.client.get(reverse("entregasapp:programacion"))
        self.assertContains(lista, self.persona.apellidos)
        self.assertNotContains(lista, "Programar entrega")
        entrega = Entrega.objects.get()
        detalle = self.client.get(reverse("entregasapp:detalle", args=[entrega.pk]))
        self.assertContains(detalle, "Historial de intentos")
        self.assertNotContains(detalle, "Reasignar entrega")
        self.assertNotContains(detalle, "Anular entrega")
        self.assertEqual(self.client.get(reverse("entregasapp:programar")).status_code, 403)


class GestionVistaTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.client.force_login(self.equipo["qf"])
        self.persona = paciente(edad=86)
        receta(self.persona)
        Domicilio.objects.create(paciente=self.persona, sector="verde", direccion="Camino sintético",
                                 direccion_padron=self.persona.direccion)
        self.entrega = programar_entrega(self.equipo["qf"], self.persona.pk, hoy(), self.equipo["encargado"].pk, uuid.uuid4())
        self.intento = self.entrega.intentos.get()
        registrar_no_entregada(self.equipo["encargado"], self.intento.pk, "domicilio_no_encontrado", "Sin numeración", uuid.uuid4())

    def test_pendientes_con_filtros_y_reasignar_desde_el_detalle(self):
        lista = self.client.get(reverse("entregasapp:pendientes"), {"motivo": "domicilio_no_encontrado", "sector": "verde"})
        self.assertContains(lista, self.persona.apellidos)
        self.assertContains(lista, "Domicilio no encontrado")
        self.assertContains(lista, "«Sin numeración»")
        vacia = self.client.get(reverse("entregasapp:pendientes"), {"motivo": "rechazo"})
        self.assertContains(vacia, "No hay pendientes con esos filtros")
        detalle = self.client.get(reverse("entregasapp:detalle", args=[self.entrega.pk]))
        self.assertContains(detalle, "Reasignar entrega")
        respuesta = self.client.post(reverse("entregasapp:reasignar", args=[self.entrega.pk]), {
            "fecha": (hoy() + timedelta(days=1)).isoformat(), "encargado": self.equipo["encargado2"].pk,
            "intento_id": self.intento.pk, "resultado_visto": "no_entregada", "operacion_id": str(uuid.uuid4())})
        self.assertRedirects(respuesta, reverse("entregasapp:detalle", args=[self.entrega.pk]))
        self.entrega.refresh_from_db()
        self.assertEqual((self.entrega.estado, self.entrega.intentos.count()), ("programada", 2))

    def test_anular_desde_el_detalle_exige_nota_con_otro(self):
        url = reverse("entregasapp:anular", args=[self.entrega.pk])
        self.assertContains(self.client.post(url, {"motivo": "otro", "nota": ""}), "escribe una nota breve")
        respuesta = self.client.post(url, {"motivo": "retirara_farmacia", "nota": ""})
        self.assertRedirects(respuesta, reverse("entregasapp:detalle", args=[self.entrega.pk]))
        self.entrega.refresh_from_db()
        self.assertEqual(self.entrega.estado, "anulada")

    def test_recetas_no_descontadas_y_marcar_revisada(self):
        otra = paciente(edad=90)
        vence = receta(otra)
        entrega = programar_entrega(self.equipo["qf"], otra.pk, hoy(), self.equipo["encargado"].pk, uuid.uuid4())
        Receta.objects.filter(pk=vence.pk).update(fecha_fin_exclusiva=hoy())
        registrar_entregada(self.equipo["encargado"], entrega.intentos.get().pk, uuid.uuid4())
        lista = self.client.get(reverse("entregasapp:pendientes"))
        self.assertContains(lista, "Recetas no descontadas (1)")
        self.assertContains(lista, "La receta está vencida; requiere renovación.")
        vinculo = entrega.recetas.get()
        self.client.post(reverse("entregasapp:receta_revisada", args=[vinculo.pk]))
        self.assertContains(self.client.get(reverse("entregasapp:pendientes")), "No queda ninguna receta por revisar.")


class DomicilioVistaTests(CarpetaPrivadaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.equipo = equipo()
        self.persona = paciente(edad=86)

    def test_el_formulario_parte_con_la_direccion_del_padron_y_guarda(self):
        self.client.force_login(self.equipo["encargado"])
        url = reverse("entregasapp:domicilio", args=[self.persona.pk])
        pagina = self.client.get(url)
        self.assertContains(pagina, "Registrar domicilio")
        self.assertContains(pagina, self.persona.direccion)
        self.assertContains(pagina, "Usar mi ubicación actual")
        self.assertContains(pagina, 'aria-live="polite"')
        self.assertContains(pagina, "js/entregas/ubicacion.js")
        respuesta = self.client.post(url, {**DOMICILIO, "latitud": "-36.5123", "longitud": "-72.2112", "precision_metros": "9"})
        self.assertRedirects(respuesta, url)
        domicilio = Domicilio.objects.get()
        self.assertEqual((domicilio.sector, str(domicilio.latitud)), ("verde", "-36.512300"))
        conflicto = self.client.post(url, {**DOMICILIO, "referencias": "Otra", "version": "7"})
        self.assertContains(conflicto, "El domicilio cambió; revisa los datos nuevos.", status_code=400)
        verificar = self.client.post(reverse("entregasapp:domicilio_verificar", args=[domicilio.pk]), {"version": domicilio.version})
        self.assertRedirects(verificar, url)
        self.assertContains(self.client.get(url), "Verificado el")

    def test_la_qf_edita_pero_no_ve_el_boton_de_verificar_y_el_tecnico_solo_consulta(self):
        domicilio = guardar_domicilio(self.equipo["encargado"], self.persona.pk, DOMICILIO)
        url = reverse("entregasapp:domicilio", args=[self.persona.pk])
        self.client.force_login(self.equipo["qf"])
        pagina = self.client.get(url)
        self.assertContains(pagina, "Guardar domicilio")
        self.assertNotContains(pagina, "Marcar verificado")
        self.assertEqual(self.client.post(reverse("entregasapp:domicilio_verificar", args=[domicilio.pk]),
                                          {"version": domicilio.version}).status_code, 403)
        self.client.force_login(self.equipo["tecnico"])
        pagina = self.client.get(url)
        self.assertContains(pagina, "Camino a Dadinco km 2")
        self.assertNotContains(pagina, "Guardar domicilio")
        self.assertNotContains(pagina, "Agregar foto")
        self.assertEqual(self.client.post(url, DOMICILIO).status_code, 403)

    def test_fotos_privadas_por_http(self):
        domicilio = guardar_domicilio(self.equipo["encargado"], self.persona.pk, DOMICILIO)
        self.client.force_login(self.equipo["encargado"])
        subida = self.client.post(reverse("entregasapp:foto_agregar", args=[domicilio.pk]),
                                  {"foto": archivo(imagen(exif_gps=True)), "descripcion": "Portón verde"})
        self.assertEqual(subida.status_code, 302)
        foto = FotoDomicilio.objects.get()
        pagina = self.client.get(reverse("entregasapp:domicilio", args=[self.persona.pk]))
        self.assertContains(pagina, 'alt="Portón verde"')
        self.assertContains(pagina, "No fotografíes personas ni patentes")
        respuesta = self.client.get(reverse("entregasapp:foto", args=[foto.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "image/jpeg")
        self.assertIn("no-store", respuesta["Cache-Control"])
        self.assertEqual(respuesta["X-Content-Type-Options"], "nosniff")
        contenido = b"".join(respuesta.streaming_content)  # al consumirla, el cliente de pruebas cierra el archivo
        self.assertTrue(contenido.startswith(b"\xff\xd8"))
        self.assertEqual(self.client.get(f"/media/{foto.archivo.name}").status_code, 404)
        self.client.logout()
        anonimo = self.client.get(reverse("entregasapp:foto", args=[foto.pk]))
        self.assertEqual(anonimo.status_code, 302)
        self.assertIn(reverse("usuariosapp:login"), anonimo["Location"])
        invalida = self.client.post(reverse("entregasapp:foto_agregar", args=[domicilio.pk]))
        self.assertEqual(invalida.status_code, 302)  # sin sesión: a iniciar sesión

    def test_foto_invalida_muestra_el_error(self):
        domicilio = guardar_domicilio(self.equipo["encargado"], self.persona.pk, DOMICILIO)
        self.client.force_login(self.equipo["encargado"])
        respuesta = self.client.post(reverse("entregasapp:foto_agregar", args=[domicilio.pk]),
                                     {"foto": archivo(b"%PDF-1.4", "plano.jpg"), "descripcion": "Plano"})
        self.assertContains(respuesta, "no es una foto JPEG o PNG válida", status_code=400)
        self.assertFalse(FotoDomicilio.objects.exists())

    def test_lista_de_domicilios_por_estado_y_sector(self):
        guardar_domicilio(self.equipo["encargado"], self.persona.pk, DOMICILIO)
        sin_registro = paciente(edad=95)
        self.client.force_login(self.equipo["tecnico"])
        lista = self.client.get(reverse("entregasapp:domicilios"))
        self.assertContains(lista, self.persona.apellidos)
        self.assertContains(lista, sin_registro.apellidos)
        self.assertContains(lista, "Registrar domicilio")
        filtrada = self.client.get(reverse("entregasapp:domicilios"), {"estado": "sin_registrar"})
        self.assertContains(filtrada, sin_registro.apellidos)
        self.assertNotContains(filtrada, self.persona.apellidos)
        buscada = self.client.post(reverse("entregasapp:domicilios"), {"buscar": sin_registro.rut})
        self.assertContains(buscada, sin_registro.apellidos)
        self.assertNotContains(buscada, self.persona.apellidos)


class FichaYRecetaTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.persona = paciente(edad=60, cronico=True)
        inscribir_excepcion(self.equipo["qf"], self.persona.pk, "sin_red_apoyo")
        self.receta = receta(self.persona, "FICHA-1")

    def test_la_pestana_datos_muestra_domicilio_y_entrega_abierta(self):
        self.client.force_login(self.equipo["qf"])
        url = reverse("recetasapp:paciente_detalle", args=[self.persona.pk]) + "?pestana=datos"
        pagina = self.client.get(url)
        self.assertContains(pagina, "Domicilio de reparto")
        self.assertContains(pagina, "Sin registrar")
        self.assertContains(pagina, "Sin red de apoyo")
        self.assertContains(pagina, "Programar entrega")
        entrega = programar_entrega(self.equipo["qf"], self.persona.pk, hoy(), self.equipo["encargado"].pk, uuid.uuid4())
        pagina = self.client.get(url)
        self.assertContains(pagina, reverse("entregasapp:detalle", args=[entrega.pk]))
        self.assertNotContains(pagina, "Programar entrega")

    def test_la_receta_en_despacho_avisa_y_no_ofrece_confirmar_en_farmacia(self):
        entrega = programar_entrega(self.equipo["qf"], self.persona.pk, hoy(), self.equipo["encargado"].pk, uuid.uuid4())
        self.client.force_login(self.equipo["tecnico"])
        detalle = self.client.get(reverse("recetasapp:receta_detalle", args=[self.receta.pk]))
        self.assertContains(detalle, "En entrega a domicilio abierta")
        self.assertNotContains(detalle, "Confirmar entrega")
        confirmar = self.client.get(reverse("recetasapp:entrega_confirmar", args=[self.receta.pk]))
        self.assertContains(confirmar, "La receta tiene una entrega a domicilio abierta")
        self.assertContains(confirmar, reverse("entregasapp:detalle", args=[entrega.pk]))
        self.assertNotContains(confirmar, "<form method=\"post\" class=\"panel\">")

    def test_la_pestana_entregas_rotula_las_entregas_a_domicilio(self):
        programar_entrega(self.equipo["qf"], self.persona.pk, hoy(), self.equipo["encargado"].pk, uuid.uuid4())
        intento = Entrega.objects.get().intentos.get()
        registrar_entregada(self.equipo["encargado"], intento.pk, uuid.uuid4())
        self.client.force_login(self.equipo["tecnico"])
        pagina = self.client.get(reverse("recetasapp:paciente_detalle", args=[self.persona.pk]) + "?pestana=entregas")
        self.assertContains(pagina, "A domicilio")


class ExcepcionesVistaTests(TestCase):
    def setUp(self):
        self.equipo = equipo()
        self.client.force_login(self.equipo["qf"])

    def test_buscar_inscribir_y_retirar(self):
        cronico = paciente(edad=62, cronico=True)
        mayor = paciente(edad=90)
        url = reverse("entregasapp:excepciones")
        busqueda = self.client.post(url, {"accion": "buscar", "buscar": cronico.rut})
        self.assertContains(busqueda, "Inscribir excepción")
        prefijo = f"p{cronico.pk}"
        inscrita = self.client.post(url, {"prefijo": prefijo, f"{prefijo}-paciente": cronico.pk,
                                          f"{prefijo}-motivo": "movilidad_reducida", f"{prefijo}-nota": ""})
        self.assertRedirects(inscrita, url)
        inscripcion = InscripcionReparto.objects.get()
        self.assertContains(self.client.get(url), "Movilidad reducida")
        preseleccion = self.client.get(url, {"paciente": mayor.pk})
        self.assertContains(preseleccion, "Ya es elegible por edad o postración")
        self.client.post(reverse("entregasapp:excepcion_retirar", args=[inscripcion.pk]))
        inscripcion.refresh_from_db()
        self.assertIsNotNone(inscripcion.retirada_en)
        sin_nota = self.client.post(url, {"prefijo": prefijo, f"{prefijo}-paciente": cronico.pk, f"{prefijo}-motivo": "otro"})
        self.assertContains(sin_nota, "escribe una nota breve", status_code=400)
        manipulado = self.client.post(url, {"prefijo": prefijo, f"{prefijo}-paciente": "abc", f"{prefijo}-motivo": "otro"})
        self.assertEqual(manipulado.status_code, 400)

    def test_tecnico_y_encargado_no_acceden(self):
        for actor in ("tecnico", "encargado"):
            self.client.force_login(self.equipo[actor])
            with self.subTest(actor=actor):
                self.assertEqual(self.client.get(reverse("entregasapp:excepciones")).status_code, 403)
