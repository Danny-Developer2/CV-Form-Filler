"""Mapeo de los datos del CV a los campos del formulario.

El mapper combina cuatro heurísticas:

1. Normalización y similitud de etiquetas (sin acentos, puntuación ni mayúsculas).
2. Proximidad geométrica ya resuelta por el inspector (etiqueta, fila y columna).
3. Posición y orden dentro de tablas repetidas (experiencia y escolaridad).
4. Casillas de verificación: se rellena la casilla cuya etiqueta de opción
   (localizada por proximidad a la derecha del campo) coincide con el valor del
   CV para el concepto (sexo, estado civil, vive con, licencia y cómo supo).

Los campos sin datos en el CV se dejan vacíos y se registran en ``missing``.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable

from cvformfiller.models import (
    CvData,
    Education,
    FieldType,
    FormField,
    MappedField,
    MappingResult,
)
from cvformfiller.utils.logger import get_logger

logger = get_logger(__name__)


class _Rule:
    """Regla de mapeo de un concepto del CV a una etiqueta del formulario."""

    __slots__ = ("concept", "aliases", "getter")

    def __init__(
        self,
        concept: str,
        aliases: list[str],
        getter: Callable[[CvData], str],
    ) -> None:
        self.concept = concept
        self.aliases = aliases
        self.getter = getter


class _CheckboxRule:
    """Regla de mapeo de un concepto del CV a una casilla del formulario.

    ``aliases`` identifica la etiqueta conceptual de la casilla (por ejemplo
    ``Estado Civil``) y ``options`` las etiquetas de opción válidas (por ejemplo
    ``Soltero``). La casilla se localiza por proximidad a la etiqueta de la
    opción y se rellena con el estado ``/Yes`` cuando el valor del CV coincide
    con esa opción.
    """

    __slots__ = ("concept", "aliases", "options", "getter")

    def __init__(
        self,
        concept: str,
        aliases: list[str],
        options: list[str],
        getter: Callable[[CvData], str],
    ) -> None:
        self.concept = concept
        self.aliases = aliases
        self.options = options
        self.getter = getter


def _ciudad_value(cv: CvData) -> str:
    """Compone ciudad y estado cuando el campo del formulario los pide juntos."""
    if cv.ciudad and cv.estado:
        return f"{cv.ciudad}, {cv.estado}"
    return cv.ciudad or cv.estado


_SIMPLE_RULES: list[_Rule] = [
    _Rule("nombre", ["nombre", "nombres", "nombre completo"], lambda cv: cv.nombre),
    _Rule(
        "apellido_paterno",
        ["apellido paterno", "apellido", "paterno"],
        lambda cv: _first_surname(cv.apellidos),
    ),
    _Rule(
        "apellido_materno",
        ["apellido materno", "materno"],
        lambda cv: _second_surname(cv.apellidos),
    ),
    _Rule(
        "telefono",
        ["telefono", "tel", "telefono particular", "telefono celular", "celular"],
        lambda cv: cv.contacto.telefono,
    ),
    _Rule(
        "email",
        ["correo electronico", "correo", "email", "e-mail"],
        lambda cv: cv.contacto.email,
    ),
    _Rule(
        "domicilio",
        ["domicilio", "direccion", "calle", "domicilio particular"],
        lambda cv: cv.domicilio,
    ),
    _Rule(
        "ciudad",
        ["ciudad", "ciudad estado", "municipio"],
        _ciudad_value,
    ),
    _Rule("codigo_postal", ["codigo postal", "cp"], lambda cv: ""),
    _Rule(
        "fecha_nacimiento",
        ["fecha de nacimiento", "fecha nacimiento", "nacimiento"],
        lambda cv: cv.fecha_nacimiento,
    ),
    _Rule("lugar_nacimiento", ["lugar de nacimiento", "lugar nacimiento"], lambda cv: ""),
    _Rule("nacionalidad", ["nacionalidad"], lambda cv: cv.nacionalidad),
    _Rule("curp", ["curp", "clave unica de registro de poblacion"], lambda cv: cv.curp),
    _Rule(
        "rfc",
        ["rfc", "reg fed de contribuyentes", "registro federal de contribuyentes"],
        lambda cv: cv.rfc,
    ),
    _Rule(
        "nss",
        ["nss", "numero de seguridad social", "seguridad social"],
        lambda cv: cv.nss,
    ),
    _Rule("afore", ["afore"], lambda cv: ""),
    _Rule("cartilla", ["cartilla de servicio militar", "cartilla"], lambda cv: ""),
    _Rule("pasaporte", ["pasaporte", "pasaporte no"], lambda cv: ""),
    _Rule(
        "idiomas",
        ["idiomas", "que idiomas habla", "idioma"],
        lambda cv: ", ".join(cv.idiomas),
    ),
    _Rule(
        "software",
        ["software que conoce", "software", "programas que maneja", "herramientas"],
        lambda cv: ", ".join(cv.software),
    ),
    _Rule("funciones_oficina", ["funciones de oficina que domina"], lambda cv: ""),
    _Rule(
        "otros_trabajos",
        ["otros trabajos o funciones que domina"],
        lambda cv: "",
    ),
    _Rule(
        "maquina_oficina",
        ["maquina de oficina o taller que sepa manejar"],
        lambda cv: "",
    ),
]

_CHECKBOX_RULES: list[_CheckboxRule] = [
    _CheckboxRule("sexo", ["sexo"], ["masculino", "femenino"], lambda cv: cv.sexo),
    _CheckboxRule(
        "estado_civil",
        ["estado civil"],
        [
            "soltero",
            "soltera",
            "casado",
            "casada",
            "divorciado",
            "divorciada",
            "viudo",
            "viuda",
            "otro",
            "otra",
        ],
        lambda cv: cv.estado_civil,
    ),
    _CheckboxRule(
        "vive_con",
        ["vive con"],
        ["solo", "sus padres", "su familia", "parientes", "otros"],
        lambda cv: cv.vive_con,
    ),
    _CheckboxRule(
        "licencia",
        ["tiene licencia", "licencia de manejo"],
        ["si", "no"],
        lambda cv: cv.licencia,
    ),
    _CheckboxRule(
        "como_supo",
        ["como supo"],
        ["anuncio", "otro medio"],
        lambda cv: cv.como_supo,
    ),
]

_ROW_ALIASES: dict[str, list[str]] = {
    "primaria": ["primaria"],
    "secundaria": ["secundaria o prevocacional", "secundaria", "prevocacional"],
    "preparatoria": ["preparatoria o vocacional", "preparatoria", "vocacional"],
    "profesional": ["profesional"],
    "comercial": ["comercial u otras", "comercial", "otras"],
}

_COLUMN_ORDER = ["nombre", "direccion", "de", "a", "anos", "titulo"]
_COLUMN_ALIASES = {
    "nombre": ["nombre", "escuela"],
    "direccion": ["direccion"],
    "de": ["de", "inicio"],
    "a": ["a", "fin"],
    "anos": ["anos", "anios", "duracion"],
    "titulo": ["titulo recibido", "titulo", "grado"],
}

_EDUCATION_LEVELS = [
    ("profesional", ("licenciatura", "ingenieria", "maestria", "doctorado", "profesional")),
    ("preparatoria", ("preparatoria", "bachillerato", "vocacional")),
    ("secundaria", ("secundaria", "prevocacional")),
    ("primaria", ("primaria",)),
]


def map_cv_to_form(cv: CvData, fields: list[FormField]) -> MappingResult:
    """Mapea los datos del CV a los campos del formulario."""
    mapped: list[MappedField] = []
    missing: list[str] = []
    used: set[str] = set()

    _map_experiencia(cv, fields, mapped, missing, used)
    _map_escolaridad(cv, fields, mapped, missing, used)
    _map_estudios_actuales(cv, fields, mapped, missing, used)
    _map_simple(cv, fields, mapped, missing, used)
    _map_checkboxes(cv, fields, mapped, missing, used)

    mapped.sort(key=lambda item: (item.field, item.source))
    missing = sorted(set(missing))
    logger.debug("mapeados %d campos, %d faltantes", len(mapped), len(missing))
    return MappingResult(
        fields=mapped,
        missing=missing,
        total_fields=len(fields),
        filled_count=len(mapped),
    )


def _map_simple(
    cv: CvData,
    fields: list[FormField],
    mapped: list[MappedField],
    missing: list[str],
    used: set[str],
) -> None:
    """Asigna los conceptos simples por similitud de etiquetas."""
    candidatos: list[tuple[float, int, FormField, str, str]] = []
    for priority, rule in enumerate(_SIMPLE_RULES):
        valor = rule.getter(cv)
        for field in fields:
            if field.name in used:
                continue
            score = _field_concept_score(field, rule.aliases)
            if score >= 0.5:
                candidatos.append((score, priority, field, rule.concept, valor))

    candidatos.sort(
        key=lambda item: (-item[0], item[1], item[2].page, -item[2].rect[1], item[2].rect[0])
    )
    assigned: set[str] = set()
    for score, _priority, field, concept, valor in candidatos:
        if concept in assigned or field.name in used:
            continue
        assigned.add(concept)
        used.add(field.name)
        if valor:
            mapped.append(
                MappedField(
                    field=field.name,
                    label=field.label,
                    value=valor,
                    source=concept,
                    confidence=round(score, 3),
                )
            )
        else:
            missing.append(field.name)


def _map_checkboxes(
    cv: CvData,
    fields: list[FormField],
    mapped: list[MappedField],
    missing: list[str],
    used: set[str],
) -> None:
    """Rellena las casillas cuya opción coincide con el valor del CV.

    Para cada regla se localizan las casillas cuya etiqueta conceptual coincide
    con el concepto (``Sexo``, ``Estado Civil``, ``Vive con``, ``Tiene licencia``
    o ``¿Cómo supo?``) y se comprueba la etiqueta de la opción situada a la
    derecha del campo. Solo se marca la primera casilla cuya opción coincide con
    el valor del CV; el resto quedan sin marcar.
    """
    for rule in _CHECKBOX_RULES:
        valor = rule.getter(cv)
        coincidencias = [
            field
            for field in fields
            if field.type is FieldType.CHECKBOX
            and field.name not in used
            and _checkbox_concept_score(field, rule.aliases) >= 0.5
        ]
        if not coincidencias:
            continue
        if not valor:
            for field in coincidencias:
                used.add(field.name)
                missing.append(field.name)
            continue
        for field in coincidencias:
            opcion = _checkbox_option(field, rule.options)
            if opcion and _option_matches(valor, opcion):
                used.add(field.name)
                mapped.append(
                    MappedField(
                        field=field.name,
                        label=field.label,
                        value="Si",
                        source=rule.concept,
                        confidence=0.9,
                    )
                )
                break


def _checkbox_concept_score(field: FormField, aliases: list[str]) -> float:
    """Calcula la similitud entre las etiquetas del campo y los alias."""
    best = 0.0
    for text in (field.line_label, field.label, field.row_label, field.column_label):
        for alias in aliases:
            best = max(best, _match_score(text, alias))
    return best


def _checkbox_option(field: FormField, options: list[str]) -> str:
    """Devuelve la opción de la casilla que coincide con una opción conocida."""
    for text in (field.right_label, field.label, field.row_label, field.column_label):
        for option in options:
            if _match_score(text, option) >= 0.5:
                return option
    return ""


def _option_matches(valor: str, opcion: str) -> bool:
    """Indica si el valor del CV coincide con la opción de la casilla."""
    return _match_score(valor, opcion) >= 0.85


def _map_experiencia(
    cv: CvData,
    fields: list[FormField],
    mapped: list[MappedField],
    missing: list[str],
    used: set[str],
) -> None:
    """Rellena la tabla de empleo actual y anteriores."""
    if not cv.experiencia:
        return
    companias = _find_row_fields(fields, ["compania", "nombre de la compania", "empresa"], used)
    puestos = _find_row_fields(
        fields, ["puesto desempenado", "puesto desempenado actual", "cargo"], used
    )
    periodos = _find_period_fields(fields, used, companias)
    for index, experience in enumerate(cv.experiencia):
        if index < len(companias):
            _assign(mapped, used, companias[index], experience.empresa, "experiencia_empresa")
        if index < len(puestos):
            _assign(mapped, used, puestos[index], experience.puesto, "experiencia_puesto")
        start, end = _split_period(experience.periodo)
        if 2 * index < len(periodos):
            _assign(mapped, used, periodos[2 * index], start, "experiencia_periodo_inicio")
        if 2 * index + 1 < len(periodos):
            _assign(mapped, used, periodos[2 * index + 1], end, "experiencia_periodo_fin")
    for field in [*companias, *puestos, *periodos]:
        used.add(field.name)


def _map_escolaridad(
    cv: CvData,
    fields: list[FormField],
    mapped: list[MappedField],
    missing: list[str],
    used: set[str],
) -> None:
    """Rellena la tabla de escolaridad por nivel y columna."""
    if not cv.educacion:
        return
    rows = _group_rows(fields, used)
    if not rows:
        return
    asignaciones = _assign_education_rows(cv.educacion, rows)
    for row_key, entry in asignaciones.items():
        columnas = _columns_for_row(rows[row_key])
        start, end = _years(entry.periodo)
        valores = {
            "nombre": entry.titulo,
            "direccion": entry.institucion,
            "de": start,
            "a": end,
            "anos": _duration(start, end),
            "titulo": entry.grado or entry.titulo,
        }
        for column_key, field in columnas.items():
            _assign(mapped, used, field, valores.get(column_key, ""), f"escolaridad_{column_key}")
    for row_key, row_fields in rows.items():
        if row_key not in asignaciones:
            for field in row_fields:
                if field.name not in used:
                    used.add(field.name)
                    missing.append(field.name)


def _map_estudios_actuales(
    cv: CvData,
    fields: list[FormField],
    mapped: list[MappedField],
    missing: list[str],
    used: set[str],
) -> None:
    """Rellena los estudios en curso con la entrada más reciente del CV."""
    if not cv.educacion:
        return
    current = _current_education(cv.educacion)
    if current is None:
        return
    for field in fields:
        if field.name in used:
            continue
        row = _normalize(field.row_label)
        if row in {"escuela", "institucion", "plantel"}:
            _assign(mapped, used, field, current.institucion, "estudios_escuela")
        elif row in {"curso o carrera", "curso", "carrera"}:
            _assign(mapped, used, field, current.titulo, "estudios_curso")
        elif row in {"horario", "grado"}:
            used.add(field.name)
            missing.append(field.name)


def _assign(
    mapped: list[MappedField],
    used: set[str],
    field: FormField,
    value: str,
    source: str,
) -> None:
    """Registra un campo como rellenado si tiene valor."""
    if field.name in used:
        return
    used.add(field.name)
    if value:
        mapped.append(
            MappedField(
                field=field.name,
                label=field.label,
                value=value,
                source=source,
                confidence=0.9,
            )
        )


def _field_concept_score(field: FormField, aliases: list[str]) -> float:
    """Calcula la similitud máxima entre las etiquetas del campo y los alias."""
    best = 0.0
    combined = f"{field.row_label} {field.column_label}"
    for alias in aliases:
        best = max(best, _match_score(field.label, alias))
        best = max(best, _match_score(field.column_label, alias) * 0.9)
        best = max(best, _match_score(field.row_label, alias) * 0.6)
        best = max(best, _match_score(combined, alias) * 0.5)
    return best


def _match_score(text: str, alias: str) -> float:
    """Similitud entre una etiqueta y un alias (1.0 = exacto)."""
    normalized = _normalize(text)
    alias = _normalize(alias)
    if not normalized or not alias:
        return 0.0
    if len(alias) <= 2:
        return 1.0 if normalized == alias else 0.0
    if normalized == alias:
        return 1.0
    if normalized.startswith(alias):
        return 0.9
    tokens = normalized.split()
    if alias in tokens:
        return 0.85
    if alias in normalized:
        return 0.7
    alias_tokens = set(alias.split())
    common = set(tokens) & alias_tokens
    if common:
        return 0.5 * len(common) / len(alias_tokens)
    return 0.0


def _normalize(text: str) -> str:
    """Normaliza una etiqueta: minúsculas, sin acentos ni puntuación."""
    if not text:
        return ""
    value = text.lower()
    value = unicodedata.normalize("NFD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.replace("(", "").replace(")", "")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _first_surname(apellidos: str) -> str:
    """Devuelve el primer apellido."""
    parts = apellidos.split()
    return parts[0] if parts else ""


def _second_surname(apellidos: str) -> str:
    """Devuelve el segundo apellido si existe."""
    parts = apellidos.split()
    return parts[1] if len(parts) > 1 else ""


def _find_row_fields(
    fields: list[FormField], aliases: list[str], used: set[str]
) -> list[FormField]:
    """Busca campos cuya etiqueta de fila coincida con los alias, ordenados."""
    encontrados: list[FormField] = []
    for field in fields:
        if field.name in used:
            continue
        for alias in aliases:
            if _match_score(field.row_label, alias) >= 0.9:
                encontrados.append(field)
                break
    encontrados.sort(key=lambda field: (field.page, field.rect[0], field.rect[1]))
    return encontrados


def _find_period_fields(
    fields: list[FormField], used: set[str], reference: list[FormField]
) -> list[FormField]:
    """Busca los campos de periodo (``de``/``a``) en la banda superior de la tabla."""
    pagina = reference[0].page if reference else None
    candidatos: list[FormField] = []
    for field in fields:
        if field.name in used or field.type.value != "text":
            continue
        if pagina is not None and field.page != pagina:
            continue
        if _normalize(field.label) in {"de", "a"} or _normalize(field.column_label) in {"de", "a"}:
            candidatos.append(field)
    if not candidatos:
        return []
    bandas: dict[int, list[FormField]] = {}
    for field in candidatos:
        bandas.setdefault(round(field.rect[3] / 10), []).append(field)
    mejor = max(bandas.values(), key=lambda grupo: max(f.rect[3] for f in grupo))
    mejor.sort(key=lambda field: field.rect[0])
    return mejor


def _group_rows(fields: list[FormField], used: set[str]) -> dict[str, list[FormField]]:
    """Agrupa campos por la fila de la tabla de escolaridad."""
    rows: dict[str, list[FormField]] = {}
    for field in fields:
        if field.name in used:
            continue
        for row_key, aliases in _ROW_ALIASES.items():
            if any(_match_score(field.row_label, alias) >= 0.8 for alias in aliases):
                rows.setdefault(row_key, []).append(field)
                break
    for row_fields in rows.values():
        row_fields.sort(key=lambda field: (field.page, field.rect[0], field.rect[1]))
    return rows


def _columns_for_row(row_fields: list[FormField]) -> dict[str, FormField]:
    """Asigna columnas a los campos de una fila por etiqueta o por posición."""
    columnas: dict[str, FormField] = {}
    for index, field in enumerate(row_fields):
        column_key = ""
        for key, aliases in _COLUMN_ALIASES.items():
            if any(_match_score(field.column_label, alias) >= 0.8 for alias in aliases):
                column_key = key
                break
        if not column_key and index < len(_COLUMN_ORDER):
            column_key = _COLUMN_ORDER[index]
        if column_key and column_key not in columnas:
            columnas[column_key] = field
    return columnas


def _assign_education_rows(
    educacion: list[Education], rows: dict[str, list[FormField]]
) -> dict[str, Education]:
    """Asigna cada entrada del CV a una fila de la tabla de escolaridad."""
    disponibles = [
        key
        for key in ["profesional", "comercial", "preparatoria", "secundaria", "primaria"]
        if key in rows
    ]
    asignaciones: dict[str, Education] = {}
    for entry in educacion:
        level = _education_level(entry.titulo)
        candidatos = [level] + [key for key in disponibles if key != level]
        for row_key in candidatos:
            if row_key in disponibles and row_key not in asignaciones:
                asignaciones[row_key] = entry
                break
    return asignaciones


def _education_level(titulo: str) -> str:
    """Deduce el nivel educativo a partir del título."""
    low = _normalize(titulo)
    for level, keywords in _EDUCATION_LEVELS:
        if any(keyword in low for keyword in keywords):
            return level
    return "comercial"


def _current_education(educacion: list[Education]) -> Education | None:
    """Devuelve la entrada educativa más reciente o en curso."""
    for entry in educacion:
        periodo = entry.periodo.lower()
        if "actual" in periodo or "vigente" in periodo or "presente" in periodo:
            return entry
    return educacion[-1] if educacion else None


def _split_period(periodo: str) -> tuple[str, str]:
    """Divide un periodo ``de - a`` en sus dos extremos."""
    parts = re.split(r"[-–—]", periodo, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return periodo.strip(), ""


def _years(periodo: str) -> tuple[str, str]:
    """Extrae el año de inicio y fin de un periodo."""
    years = re.findall(r"\b(19|20)(\d{2})\b", periodo)
    if not years:
        return "", ""
    full_years = [f"{prefix}{suffix}" for prefix, suffix in years]
    return full_years[0], full_years[-1]


def _duration(start: str, end: str) -> str:
    """Calcula la duración en años entre dos años."""
    try:
        inicio = int(start)
        fin = int(end)
    except (TypeError, ValueError):
        return ""
    if fin < inicio:
        return ""
    return str(max(1, fin - inicio))


__all__ = ["map_cv_to_form"]
