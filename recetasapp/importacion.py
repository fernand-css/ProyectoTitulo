"""Contrato propio de archivos sintéticos y conciliación sin copiar rechazos."""

import csv
import hashlib
import io
import re
import zipfile
from datetime import date
from random import Random

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Sum

from coreapp.auditoria import registrar_accion
from coreapp.roles import JEFA
from coreapp.utils.rut import normalizar_rut
from coreapp.utils.sinteticos import generar_ruts
from .models import ImportacionPadron, Paciente, Receta, ResultadoFilaImportacion
from .services import aplicar_fila, autorizar, calcular_fin, reintentar_conflictos

ENCABEZADOS = (
    "rut", "nombres", "apellidos", "fecha_nacimiento", "es_cronico", "es_postrado",
    "telefono", "direccion", "codigo_receta", "fecha_inicio", "vigencia_meses", "max_entregas",
)
MAX_BYTES = 5 * 1024 * 1024
MAX_FILAS = 10_000
CONTADORES = ("pacientes_creados", "pacientes_actualizados", "recetas_creadas", "recetas_actualizadas")


def _texto(valor):
    if valor is None:
        return ""
    if isinstance(valor, bool) or not isinstance(valor, (str, int)):
        raise ValidationError("Las celdas deben contener texto o números enteros, sin fórmulas.")
    return str(valor).strip()


def _fecha(valor):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
        raise ValueError
    return date.fromisoformat(valor)


def _entero(valor):
    if not re.fullmatch(r"[1-9][0-9]*", valor):
        raise ValueError
    return int(valor)


def validar_fila(valores):
    if len(valores) != len(ENCABEZADOS):
        raise ValidationError("La fila no tiene las doce columnas requeridas.")
    d = dict(zip(ENCABEZADOS, map(_texto, valores)))
    try:
        paciente = {
            "rut": normalizar_rut(d["rut"]), "nombres": d["nombres"], "apellidos": d["apellidos"],
            "fecha_nacimiento": _fecha(d["fecha_nacimiento"]),
            "telefono": d["telefono"], "direccion": d["direccion"],
        }
        for campo in ("es_cronico", "es_postrado"):
            if d[campo] not in ("0", "1"):
                raise ValueError
            paciente[campo] = d[campo] == "1"
        instancia = Paciente(**paciente)
        instancia.full_clean(validate_unique=False)
        paciente["nombres"], paciente["apellidos"] = instancia.nombres, instancia.apellidos
        receta = None
        campos_receta = ("codigo_receta", "fecha_inicio", "vigencia_meses", "max_entregas")
        if any(d[campo] for campo in campos_receta):
            if not all(d[campo] for campo in campos_receta):
                raise ValidationError("La receta requiere código, inicio, vigencia y máximo de entregas.")
            receta = {
                "codigo": d["codigo_receta"], "fecha_inicio": _fecha(d["fecha_inicio"]),
                "vigencia_meses": _entero(d["vigencia_meses"]), "max_entregas": _entero(d["max_entregas"]),
            }
            temporal = Receta(**receta, fecha_fin_exclusiva=calcular_fin(receta["fecha_inicio"], receta["vigencia_meses"]))
            temporal.full_clean(exclude=["paciente"], validate_unique=False)
        return paciente, receta
    except (ValueError, OverflowError, TypeError):
        raise ValidationError("Revisa las fechas ISO, los indicadores 0/1 y los enteros positivos.") from None


def leer_archivo(contenido, formato):
    if len(contenido) > MAX_BYTES:
        raise ValidationError("El archivo supera el límite de 5 MiB.")
    if formato == "csv":
        try:
            filas = []
            for fila in csv.reader(io.StringIO(contenido.decode("utf-8-sig"), newline=""), strict=True):
                filas.append(fila)
                if len(filas) > MAX_FILAS + 1:
                    raise ValidationError("El archivo supera las 10.000 filas de datos.")
        except (UnicodeError, csv.Error):
            raise ValidationError("El CSV debe ser UTF-8, separado por comas y tener comillas válidas.") from None
    elif formato == "xlsx":
        from openpyxl import load_workbook
        try:
            with zipfile.ZipFile(io.BytesIO(contenido)) as paquete:
                entradas = paquete.infolist()
                if len(entradas) > 1000 or sum(e.file_size for e in entradas) > 50 * 1024 * 1024:
                    raise ValidationError("El contenido descomprimido del Excel supera los límites admitidos.")
                if any("vbaproject" in e.filename.lower() for e in entradas):
                    raise ValidationError("No se admiten macros.")
            libro = load_workbook(io.BytesIO(contenido), read_only=True, data_only=False, keep_links=False)
            try:
                if libro.sheetnames != ["padron"]:
                    raise ValidationError("Excel debe tener una única hoja llamada padron.")
                hoja = libro["padron"]
                hoja.reset_dimensions()
                filas = []
                for celdas in hoja.iter_rows():
                    if len(celdas) > len(ENCABEZADOS):
                        raise ValidationError("Excel tiene columnas adicionales.")
                    filas.append([celda.value if celda.data_type != "f" else FormulaNoAdmitida() for celda in celdas])
                    if len(filas) > MAX_FILAS + 1:
                        raise ValidationError("El archivo supera las 10.000 filas de datos.")
            finally:
                libro.close()
        except ValidationError:
            raise
        except Exception:
            raise ValidationError("No se pudo leer el archivo Excel. Usa la plantilla .xlsx.") from None
    else:
        raise ValidationError("Selecciona CSV o Excel .xlsx.")
    if not filas or tuple(filas[0]) != ENCABEZADOS:
        raise ValidationError("Los encabezados deben coincidir con la plantilla, en el mismo orden.")
    if len(filas) < 2:
        raise ValidationError("El archivo no contiene filas de datos.")
    return filas[1:]


class FormulaNoAdmitida:
    """Marcador sin conservar el contenido de una fórmula de entrada."""


@reintentar_conflictos
def _prevalidar(filas):
    registros = []
    por_rut, por_codigo = {}, {}
    for numero, fila in enumerate(filas, 2):
        registro = {"numero": numero, "datos": None, "error": None, "firma": None}
        try:
            # La comparación incluye también filas con valores inválidos: ninguna
            # contradicción debe elegir silenciosamente una de sus versiones.
            valores = tuple(_texto(v) for v in fila)
            if len(valores) == len(ENCABEZADOS):
                rut = normalizar_rut(valores[0])
                valores = (rut,) + valores[1:]
                registro["firma"] = valores
                por_rut.setdefault(rut, []).append((registro, valores[:8]))
                if valores[8]:
                    por_codigo.setdefault(valores[8], []).append((registro, (rut,) + valores[8:]))
            registro["datos"] = validar_fila(fila)
        except ValidationError as error:
            # Mensajes de validadores pueden contener valores: no persistirlos.
            registro["error"] = ("datos_invalidos", "Revisa RUT, campos obligatorios, formatos y fechas de esta fila.")
        registros.append(registro)
    for agrupados in (por_rut, por_codigo):
        for elementos in agrupados.values():
            if len({firma for _, firma in elementos}) > 1:
                for registro, _ in elementos:
                    registro["error"] = ("duplicado_contradictorio", "Hay datos contradictorios para la misma identidad dentro del archivo.")
    vistas = set()
    for registro in registros:
        if registro["error"]:
            continue
        firma = registro["firma"]
        if firma in vistas:
            registro["omitida"] = True
        vistas.add(firma)
    return registros


@reintentar_conflictos
def _cerrar(actor, carga, estado, motivo=""):
    with transaction.atomic():
        carga.estado, carga.resumen_fallo = estado, motivo
        grupos = dict(carga.resultados.values("estado").annotate(n=Count("pk")).values_list("estado", "n"))
        for singular, campo in [("creada", "filas_creadas"), ("actualizada", "filas_actualizadas"), ("sin_cambios", "filas_sin_cambios"), ("omitida", "filas_omitidas"), ("rechazada", "filas_rechazadas")]:
            setattr(carga, campo, grupos.get(singular, 0))
        for campo, valor in carga.resultados.aggregate(**{c: Sum(c) for c in CONTADORES}).items():
            setattr(carga, campo, valor or 0)
        carga.modificado_por = actor
        carga.save()
        registrar_accion(actor, f"padron.carga_{'completada' if estado == 'completada' else 'fallida'}", carga)
    return carga


@reintentar_conflictos
@transaction.atomic
def _iniciar(actor, contenido, formato):
    autorizar(actor, JEFA)
    carga = ImportacionPadron.objects.create(
        creado_por=actor, modificado_por=actor, formato=formato,
        archivo_sha256=hashlib.sha256(contenido).hexdigest(),
    )
    registrar_accion(actor, "padron.carga_iniciada", carga)
    return carga


@reintentar_conflictos
@transaction.atomic
def _resultado(actor, carga, registro, error):
    ResultadoFilaImportacion.objects.create(
        importacion=carga, numero_fila=registro["numero"],
        estado="rechazada" if error else "omitida",
        codigo_motivo=error[0] if error else "duplicado_identico",
        mensaje=error[1] if error else "Fila idéntica omitida.",
        creado_por=actor, modificado_por=actor,
    )


@reintentar_conflictos
def _total(carga):
    carga.save(update_fields=["total_filas"])


def importar_padron(actor, archivo, formato):
    autorizar(actor, JEFA)
    if formato not in ImportacionPadron.Formato.values:
        raise ValidationError("Selecciona CSV o Excel .xlsx.")
    contenido = archivo.read(MAX_BYTES + 1)
    carga = _iniciar(actor, contenido, formato)
    try:
        filas = leer_archivo(contenido, formato)
    except ValidationError:
        return _cerrar(actor, carga, "fallida", "Archivo ilegible, vacío, fuera de límites o con estructura inválida. Revisa la plantilla.")
    carga.total_filas = len(filas)
    _total(carga)
    try:
        for registro in _prevalidar(filas):
            autorizar(actor, JEFA)
            error = registro["error"]
            if not error and not registro.get("omitida"):
                try:
                    aplicar_fila(actor, registro["datos"], carga=carga, numero_fila=registro["numero"])
                    continue
                except ValidationError:
                    error = ("conflicto_dominio", "La fila no se guardó. Revisa propietario, datos de receta e historial de entregas.")
            _resultado(actor, carga, registro, error)
    except Exception:
        # Los errores de infraestructura/auditoría interrumpen la carga. Nunca
        # convertirlos en rechazo de datos ni copiar excepciones a la bitácora.
        return _cerrar(actor, carga, "fallida", "La carga se interrumpió. Revisa las filas confirmadas antes de reintentar.")
    return _cerrar(actor, carga, "completada")


def filas_demo(cantidad=670, semilla=3, inicio=date(2026, 1, 1)):
    for indice, rut in enumerate(generar_ruts(cantidad, Random(semilla)), 1):
        yield [rut, f"Paciente sintético {indice}", "Demostración", "1940-06-15" if indice <= 600 else "1970-03-01",
               "1", "1" if indice > 600 else "0", "", "Sector sintético", f"DEMO-{indice:04}", inicio.isoformat(), "12", "12"]


def generar_archivo(formato, filas=()):
    filas = [ENCABEZADOS, *filas]
    if formato == "csv":
        salida = io.StringIO(newline="")
        escritor = csv.writer(salida)
        escritor.writerows(filas)
        return salida.getvalue().encode("utf-8-sig")
    if formato == "xlsx":
        from openpyxl import Workbook
        libro = Workbook(write_only=True)
        hoja = libro.create_sheet("padron")
        for fila in filas:
            hoja.append(list(fila))
        salida = io.BytesIO()
        libro.save(salida)
        return salida.getvalue()
    raise ValidationError("Selecciona CSV o Excel .xlsx.")
