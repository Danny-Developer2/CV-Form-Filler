"""Extracción y normalización de un CV (PDF o DOCX) a un modelo de datos.

El parser es heurístico: reconoce secciones por su encabezado, separa campos por
``|`` y valida patrones (correo, teléfono, CURP, RFC, NSS). No registra nunca
los datos personales en el log.
"""

from __future__ import annotations

import re
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pdfplumber
from pydantic import ValidationError

from cvformfiller.exceptions import CvParseError
from cvformfiller.models import Contacto, CvData, Education, Experience
from cvformfiller.utils.logger import get_logger

logger = get_logger(__name__)

_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\s()./-]{5,}\d")
_DATE_RANGE_RE = re.compile(r"^\d{4}\s*[-–—]\s*\d{4}$")
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_CURP_RE = re.compile(r"\b[A-Z]{4}\d{6}[HM][A-Z]{2}[A-Z]{3}[A-Z0-9]{2}\b")
_RFC_RE = re.compile(r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b")
_NSS_RE = re.compile(r"\b\d{2}\s?\d{2}\s?\d{2}\s?\d{4}\s?\d{2}\b|\b\d{11}\b")
_BIRTH_DATE_RE = re.compile(
    r"\b\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\b|\b\d{1,2}/\d{1,2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b",
    re.IGNORECASE,
)
_CITY_STATE_RE = re.compile(
    r"Ciudad\s+([A-Za-zÁÉÍÓÚáéíóúÑñ]+(?:\s+[A-Za-zÁÉÍÓÚáéíóúÑñ]+){0,3})\s*,\s*"
    r"((?:[A-Z]\.){1,4}|[A-Z]{2,5})",
    re.IGNORECASE,
)
_CITY_STATE_FALLBACK_RE = re.compile(
    r"([A-Za-zÁÉÍÓÚáéíóúÑñ]+(?:\s+[A-Za-zÁÉÍÓÚáéíóúÑñ]+){0,2})\s*,\s*"
    r"([A-Za-zÁÉÍÓÚáéíóúÑñ.]+(?:\s+[A-Za-zÁÉÍÓÚáéíóúÑñ.]+){0,3})"
)

_KNOWN_HEADERS = [
    "PERFIL",
    "HABILIDADES",
    "EXPERIENCIA",
    "EDUCACIÓN",
    "EDUCACION",
    "FORMACIÓN",
    "FORMACION",
    "CERTIFICACIONES",
    "IDIOMAS",
    "PROYECTOS",
    "REFERENCIAS",
    "OTROS",
    "RESUMEN",
    "DATOS PERSONALES",
]

_STATE_EXPANSIONS = {
    "N.L.": "Nuevo León",
    "Jal.": "Jalisco",
    "CDMX": "Ciudad de México",
    "Mor.": "Morelos",
    "Pue.": "Puebla",
    "Ver.": "Veracruz",
    "Yuc.": "Yucatán",
    "Qro.": "Querétaro",
    "S.L.P.": "San Luis Potosí",
    "SIN.": "Sinaloa",
    "SON.": "Sonora",
    "TAB.": "Tabasco",
    "TAM.": "Tamaulipas",
    "COAH.": "Coahuila",
    "CHIH.": "Chihuahua",
    "DGO.": "Durango",
    "GTO.": "Guanajuato",
    "HGO.": "Hidalgo",
    "MICH.": "Michoacán",
    "NAY.": "Nayarit",
    "OAX.": "Oaxaca",
    "TLAX.": "Tlaxcala",
    "ZAC.": "Zacatecas",
    "BC.": "Baja California",
    "BCS.": "Baja California Sur",
    "CAMP.": "Campeche",
    "COL.": "Colima",
    "AGS.": "Aguascalientes",
}

_SOFTWARE_KEYWORDS = [
    "Python",
    ".NET",
    "C#",
    "Angular",
    "React",
    "Docker",
    "Azure",
    "AWS",
    "Kali Linux",
    "Nmap",
    "Nessus",
    "Burp Suite",
    "Metasploit",
    "GNU/Linux",
    "Windows",
    "Git",
    "GitHub",
    "SQL",
    "API REST",
    "HTML",
    "CSS",
    "JavaScript",
    "TypeScript",
    "Node.js",
    "Linux",
    "Wireshark",
    "OWASP",
    "VMware",
    "VirtualBox",
    "Postman",
    "Jenkins",
    "Kubernetes",
    "Terraform",
    "MongoDB",
    "MySQL",
    "PostgreSQL",
    "Redis",
    "Claude",
    "pentesting",
]


def parse_cv(path: Path) -> CvData:
    """Extrae y normaliza el CV desde ``path`` (PDF o DOCX)."""
    if not path.exists():
        raise CvParseError(f"el CV no existe: {path}")
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text = _extract_pdf_text(path)
    elif suffix in {".docx", ".doc"}:
        text = _extract_docx_text(path)
    else:
        raise CvParseError(f"formato de CV no admitido: {suffix or path.name}")
    if not text.strip():
        raise CvParseError("el CV está vacío o no tiene capa de texto")
    return parse_cv_text(text)


def parse_cv_text(text: str) -> CvData:
    """Construye un :class:`CvData` a partir del texto plano del CV."""
    lines = _clean_lines(text)
    nombre, apellidos = _parse_name(lines)
    contacto = _parse_contact(text)
    ciudad, estado = _parse_location(lines)
    domicilio = f"{ciudad}, {estado}" if ciudad and estado else (ciudad or estado)
    secciones = _split_sections(lines)

    experiencia = _parse_experiencia(secciones.get("EXPERIENCIA", []))
    educacion = _parse_educacion(secciones.get("EDUCACION", []))
    idiomas = _parse_idiomas(secciones.get("IDIOMAS", []))
    habilidades = _parse_habilidades(secciones.get("HABILIDADES", []))
    software = _parse_software(text)
    datos_personales = _parse_datos_personales(secciones.get("DATOS PERSONALES", []))

    curp = _first_match(_CURP_RE, text)
    rfc = _first_match(_RFC_RE, text)
    nss = _first_match(_NSS_RE, text)
    fecha_nacimiento = _first_match(_BIRTH_DATE_RE, text)
    nacionalidad = _parse_nacionalidad(text)

    try:
        return CvData(
            nombre=nombre,
            apellidos=apellidos,
            contacto=contacto,
            fecha_nacimiento=fecha_nacimiento,
            domicilio=domicilio,
            ciudad=ciudad,
            estado=estado,
            nacionalidad=nacionalidad,
            curp=curp,
            rfc=rfc,
            nss=nss,
            sexo=datos_personales.get("sexo", ""),
            estado_civil=datos_personales.get("estado_civil", ""),
            vive_con=datos_personales.get("vive_con", ""),
            licencia=datos_personales.get("licencia", ""),
            como_supo=datos_personales.get("como_supo", ""),
            experiencia=experiencia,
            educacion=educacion,
            idiomas=idiomas,
            habilidades=habilidades,
            software=software,
        )
    except ValidationError as exc:  # pragma: no cover - validación defensiva
        raise CvParseError(f"el CV no pasó la validación: {exc}") from exc


def _extract_pdf_text(path: Path) -> str:
    """Extrae el texto de un PDF con pdfplumber."""
    try:
        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except CvParseError:
        raise
    except Exception as exc:
        raise CvParseError(f"no se pudo leer el PDF del CV: {exc}") from exc


def _extract_docx_text(path: Path) -> str:
    """Extrae el texto de un DOCX sin dependencias externas."""
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
        root = ET.fromstring(xml)
    except Exception as exc:
        raise CvParseError(f"no se pudo leer el DOCX del CV: {exc}") from exc
    paragraphs: list[str] = []
    for paragraph in root.iter(f"{_W_NS}p"):
        parts = [node.text or "" for node in paragraph.iter(f"{_W_NS}t")]
        paragraphs.append("".join(parts))
    return "\n".join(paragraphs)


def _clean_lines(text: str) -> list[str]:
    """Divide el texto en líneas no vacías y sin espacios sobrantes."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def _title_case(value: str) -> str:
    """Convierte a título solo si la cadena está en mayúsculas o minúsculas."""
    if not value:
        return ""
    if value.isupper() or value.islower():
        return value.title()
    return value


def _parse_name(lines: list[str]) -> tuple[str, str]:
    """Obtiene nombre y apellidos de la cabecera del CV."""
    candidate = ""
    for index, line in enumerate(lines[:6]):
        low = line.lower()
        if "curriculum" in low or "vitae" in low:
            if "|" in line or "·" in line or "—" in line:
                candidate = re.split(r"[|·—]", line)[0]
                break
            if index > 0:
                candidate = lines[index - 1]
                break
    if not candidate:
        candidate = lines[0] if lines else ""
    candidate = candidate.strip(" |·—-")
    candidate = re.sub(r"\b(curriculum|vitae|cv)\b", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"\s+", " ", candidate).strip(" |·—-")
    tokens = candidate.split()
    if len(tokens) >= 3:
        apellidos = " ".join(tokens[-2:])
        nombre = " ".join(tokens[:-2])
    elif len(tokens) == 2:
        nombre, apellidos = tokens[0], tokens[1]
    elif len(tokens) == 1:
        nombre, apellidos = tokens[0], ""
    else:
        nombre, apellidos = "", ""
    return _title_case(nombre), _title_case(apellidos)


def _parse_contact(text: str) -> Contacto:
    """Extrae teléfono, correo y presencia web del CV."""
    email_match = _EMAIL_RE.search(text)
    email = email_match.group(0) if email_match else ""

    telefono = ""
    for candidato in _PHONE_RE.finditer(text):
        candidate = candidato.group(0).strip()
        digits = re.sub(r"\D", "", candidate)
        if len(digits) < 7 or _DATE_RANGE_RE.match(candidate):
            continue
        telefono = candidate
        break

    web = ""
    for pattern in (
        r"(?:github\.com|linkedin\.com)/[A-Za-z0-9_.-]+",
        r"(?<![A-Za-z0-9._%+-])@[A-Za-z0-9_.-]+",
    ):
        web_match = re.search(pattern, text, re.IGNORECASE)
        if web_match:
            web = web_match.group(0)
            break

    return Contacto(telefono=telefono, email=email, web=web)


def _parse_location(lines: list[str]) -> tuple[str, str]:
    """Extrae ciudad y estado del encabezado del CV."""
    for line in lines[:6]:
        match = _CITY_STATE_RE.search(line)
        if match:
            ciudad = match.group(1).strip()
            estado = _expand_state(match.group(2).strip())
            return ciudad, estado
    for line in lines[:6]:
        match = _CITY_STATE_FALLBACK_RE.search(line)
        if match:
            ciudad = match.group(1).strip()
            estado = _expand_state(match.group(2).strip())
            return ciudad, estado
    return "", ""


def _expand_state(value: str) -> str:
    """Expande abreviaturas comunes de estado mexicano."""
    if not value:
        return ""
    return _STATE_EXPANSIONS.get(value, value)


def _normalize_header(line: str) -> str:
    """Normaliza una línea para compararla con los encabezados conocidos."""
    return re.sub(r"\s+", " ", line).strip().upper()


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    """Agrupa las líneas del CV por sección (perfil, experiencia, etc.)."""
    secciones: dict[str, list[str]] = {}
    actual = "CABECERA"
    for line in lines:
        normalized = _normalize_header(line)
        header = ""
        for known in _KNOWN_HEADERS:
            if normalized == known or normalized.startswith(f"{known} "):
                header = known
                break
        if header:
            if header in {"EDUCACIÓN", "EDUCACION", "FORMACIÓN", "FORMACION"}:
                actual = "EDUCACION"
            else:
                actual = header
            secciones.setdefault(actual, [])
            continue
        secciones.setdefault(actual, []).append(line)
    return secciones


def _has_year(value: str) -> bool:
    """Indica si una cadena contiene un año de 4 dígitos."""
    return bool(_YEAR_RE.search(value))


def _parse_experiencia(lines: list[str]) -> list[Experience]:
    """Convierte las líneas de la sección de experiencia en entradas."""
    entradas: list[dict[str, str]] = []
    actual: dict[str, str] | None = None
    for line in lines:
        if "|" in line and _has_year(line):
            parts = [part.strip() for part in line.split("|") if part.strip()]
            if len(parts) >= 3:
                puesto, empresa, periodo = parts[0], parts[1], " | ".join(parts[2:])
            elif len(parts) == 2:
                if _has_year(parts[1]):
                    puesto, empresa, periodo = parts[0], "", parts[1]
                else:
                    puesto, empresa, periodo = parts[0], parts[1], ""
            else:
                continue
            actual = {
                "puesto": puesto,
                "empresa": empresa,
                "periodo": periodo,
                "descripcion": "",
            }
            entradas.append(actual)
        elif actual is not None:
            descripcion = line.lstrip("-•* ").strip()
            if descripcion:
                actual["descripcion"] = f"{actual['descripcion']} {descripcion}".strip()
    return [Experience(**item) for item in entradas]


def _parse_educacion(lines: list[str]) -> list[Education]:
    """Convierte las líneas de la sección de educación en entradas."""
    entradas: list[Education] = []
    for line in lines:
        if "|" not in line:
            continue
        parts = [part.strip() for part in line.split("|") if part.strip()]
        if len(parts) < 2:
            continue
        titulo = parts[0]
        institucion = parts[1]
        periodo = " | ".join(parts[2:]) if len(parts) > 2 else ""
        grado = _inferir_grado(titulo)
        entradas.append(
            Education(
                titulo=titulo,
                institucion=institucion,
                periodo=periodo,
                grado=grado,
            )
        )
    return entradas


def _inferir_grado(titulo: str) -> str:
    """Deduce el grado académico a partir del título."""
    low = titulo.lower()
    for keyword, grado in (
        ("doctorado", "Doctorado"),
        ("maestría", "Maestría"),
        ("maestria", "Maestría"),
        ("licenciatura", "Licenciatura"),
        ("ingeniería", "Ingeniería"),
        ("ingenieria", "Ingeniería"),
        ("bachillerato", "Bachillerato"),
        ("preparatoria", "Bachillerato"),
        ("técnico", "Técnico"),
        ("tecnico", "Técnico"),
    ):
        if keyword in low:
            return grado
    return ""


def _parse_idiomas(lines: list[str]) -> list[str]:
    """Extrae la lista de idiomas y niveles."""
    idiomas: list[str] = []
    for line in lines:
        for parte in line.split("|"):
            parte = parte.strip()
            if parte:
                idiomas.append(parte)
    return idiomas


def _parse_habilidades(lines: list[str]) -> list[str]:
    """Aplana las categorías de habilidades en elementos individuales."""
    habilidades: list[str] = []
    for line in lines:
        if ":" in line:
            _, items = line.split(":", 1)
        else:
            items = line
        for item in items.split(","):
            item = item.strip()
            if item:
                habilidades.append(item)
    return habilidades


def _parse_software(text: str) -> list[str]:
    """Busca herramientas y tecnologías conocidas en el texto del CV."""
    encontrados: list[str] = []
    vistos: set[str] = set()
    for keyword in _SOFTWARE_KEYWORDS:
        pattern = rf"(?<![A-Za-z0-9]){re.escape(keyword)}(?![A-Za-z0-9])"
        if re.search(pattern, text, re.IGNORECASE):
            clave = keyword.lower()
            if clave not in vistos:
                vistos.add(clave)
                encontrados.append(keyword)
    return encontrados


def _parse_nacionalidad(text: str) -> str:
    """Busca una declaración explícita de nacionalidad."""
    match = re.search(r"Nacionalidad[:\s]+([A-Za-zÁÉÍÓÚáéíóúÑñ]+)", text, re.IGNORECASE)
    if match:
        return _title_case(match.group(1))
    if re.search(r"\bMexican[oa]\b", text, re.IGNORECASE):
        return "Mexicana"
    return ""


def _parse_datos_personales(lines: list[str]) -> dict[str, str]:
    """Extrae los conceptos de casillas (sexo, estado civil, etc.) del CV.

    Lee líneas ``Clave: valor`` de la sección de datos personales y devuelve un
    diccionario con las claves normalizadas (``sexo``, ``estado_civil``,
    ``vive_con``, ``licencia`` y ``como_supo``).
    """
    datos: dict[str, str] = {}
    for line in lines:
        if ":" not in line:
            continue
        clave, valor = line.split(":", 1)
        clave_norm = _normalize_clave(clave)
        valor = valor.strip()
        if not valor:
            continue
        if clave_norm == "sexo":
            datos["sexo"] = valor
        elif clave_norm == "estado civil":
            datos["estado_civil"] = valor
        elif clave_norm == "vive con":
            datos["vive_con"] = valor
        elif clave_norm.startswith("tiene licencia"):
            datos["licencia"] = valor
        elif "como supo" in clave_norm:
            datos["como_supo"] = valor
    return datos


def _normalize_clave(value: str) -> str:
    """Normaliza una clave de datos personales: minúsculas y sin acentos."""
    value = unicodedata.normalize("NFD", value.lower())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", value).strip()


def _first_match(pattern: re.Pattern[str], text: str) -> str:
    """Devuelve el primer resultado de un patrón o cadena vacía."""
    match = pattern.search(text)
    return match.group(0) if match else ""
