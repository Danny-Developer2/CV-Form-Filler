"""Pruebas del parser de CV."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from cvformfiller.cv_parser import (
    _extract_docx_text,
    _inferir_grado,
    _normalize_clave,
    _normalize_header,
    _parse_contact,
    _parse_datos_personales,
    _parse_location,
    _parse_nacionalidad,
    _parse_name,
    _parse_software,
    _split_sections,
    _title_case,
    parse_cv,
    parse_cv_text,
)
from cvformfiller.exceptions import CvParseError

CV_TEXT = """JUAN PEREZ LOPEZ | Curriculum Vitae
Desarrollador de Software
Ciudad Ficticia, N.L. | +52 81 0000 0000 | juan.perez@example.com | @juanperez
DATOS PERSONALES
Sexo: Masculino
Estado Civil: Soltero
Vive con: Solo
Tiene licencia de manejo: Si
¿Cómo supo de esta vacante?: Anuncio
PERFIL
Desarrollador de software.
HABILIDADES
Backend: Python, Java, SQL
EXPERIENCIA
Desarrollador Backend | Empresa ABC | Abril 2024 - Mayo 2026
Automatización con Python
Desarrollador Frontend | Empresa DEF | 2022 - 2023
Desarrollo web
EDUCACIÓN
Ingeniería Ficticia | Universidad Ficticia | 2019 - 2024
IDIOMAS
Español: Nativo | Inglés: Intermedio
"""


def test_parse_cv_fixture(cv_data) -> None:
    assert cv_data.nombre == "Juan"
    assert cv_data.apellidos == "Perez Lopez"
    assert cv_data.contacto.telefono == "+52 81 0000 0000"
    assert cv_data.contacto.email == "juan.perez@example.com"
    assert cv_data.ciudad == "Ficticia"
    assert cv_data.estado == "Nuevo León"
    assert "Ficticia" in cv_data.domicilio
    assert cv_data.sexo == "Masculino"
    assert cv_data.estado_civil == "Soltero"
    assert cv_data.vive_con == "Solo"
    assert cv_data.licencia == "Si"
    assert cv_data.como_supo == "Anuncio"
    assert len(cv_data.experiencia) == 3
    assert cv_data.experiencia[0].puesto == "Desarrollador Backend"
    assert cv_data.experiencia[0].empresa == "Empresa ABC"
    assert len(cv_data.educacion) == 2
    assert cv_data.educacion[0].grado == "Ingeniería"
    assert cv_data.idiomas == ["Español: Nativo", "Inglés: Intermedio"]
    assert "Python" in cv_data.habilidades
    assert "Python" in cv_data.software


def test_parse_cv_text_synthetic() -> None:
    cv = parse_cv_text(CV_TEXT)
    assert cv.nombre == "Juan"
    assert cv.apellidos == "Perez Lopez"
    assert cv.contacto.telefono == "+52 81 0000 0000"
    assert cv.contacto.email == "juan.perez@example.com"
    assert cv.contacto.web == "@juanperez"
    assert cv.ciudad == "Ficticia"
    assert cv.estado == "Nuevo León"
    assert cv.sexo == "Masculino"
    assert cv.estado_civil == "Soltero"
    assert cv.vive_con == "Solo"
    assert cv.licencia == "Si"
    assert cv.como_supo == "Anuncio"
    assert len(cv.experiencia) == 2
    assert cv.experiencia[1].puesto == "Desarrollador Frontend"
    assert cv.experiencia[1].periodo == "2022 - 2023"
    assert len(cv.educacion) == 1
    assert cv.educacion[0].institucion == "Universidad Ficticia"
    assert cv.idiomas == ["Español: Nativo", "Inglés: Intermedio"]


def test_parse_cv_missing_file(tmp_path: Path) -> None:
    with pytest.raises(CvParseError):
        parse_cv(tmp_path / "no_existe.pdf")


def test_parse_cv_unsupported_format(tmp_path: Path) -> None:
    archivo = tmp_path / "cv.txt"
    archivo.write_text("hola", encoding="utf-8")
    with pytest.raises(CvParseError):
        parse_cv(archivo)


def test_parse_cv_empty_pdf(tmp_path: Path) -> None:
    archivo = tmp_path / "vacio.pdf"
    archivo.write_bytes(b"%PDF-1.4\n%%EOF\n")
    with pytest.raises(CvParseError):
        parse_cv(archivo)


def test_extract_docx_text(tmp_path: Path) -> None:
    documento = tmp_path / "cv.docx"
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>Juan Perez</w:t></w:r></w:p>"
        "<w:p><w:r><w:t>Desarrollador</w:t></w:r></w:p></w:body></w:document>"
    )
    with zipfile.ZipFile(documento, "w") as archivo:
        archivo.writestr("word/document.xml", xml)
    assert "Juan Perez" in _extract_docx_text(documento)


def test_parse_name_two_tokens() -> None:
    nombre, apellidos = _parse_name(["Juan Perez", "Analista"])
    assert nombre == "Juan"
    assert apellidos == "Perez"


def test_parse_name_uppercase() -> None:
    nombre, apellidos = _parse_name(["JUAN PEREZ | Curriculum Vitae"])
    assert nombre == "Juan"
    assert apellidos == "Perez"


def test_title_case() -> None:
    assert _title_case("JUAN") == "Juan"
    assert _title_case("juan") == "Juan"
    assert _title_case("Juan") == "Juan"


def test_parse_contact_filters_date_ranges() -> None:
    contacto = _parse_contact("Ciudad Ficticia, N.L. | +52 81 0000 0000 | 2019 - 2024")
    assert contacto.telefono == "+52 81 0000 0000"


def test_parse_contact_without_phone() -> None:
    contacto = _parse_contact("Sin teléfono aquí")
    assert contacto.telefono == ""


def test_parse_location_fallback() -> None:
    ciudad, estado = _parse_location(["Ficticia, Estado Ficticio", "otra línea"])
    assert ciudad == "Ficticia"
    assert estado == "Estado Ficticio"


def test_split_sections() -> None:
    lines = ["CABECERA", "PERFIL", "Texto", "EXPERIENCIA", "Puesto | Empresa | 2020 - 2021"]
    secciones = _split_sections(lines)
    assert secciones["PERFIL"] == ["Texto"]
    assert "Puesto | Empresa | 2020 - 2021" in secciones["EXPERIENCIA"]


def test_parse_software_keywords() -> None:
    software = _parse_software("Python, Nmap, Burp Suite y Windows")
    assert software == ["Python", "Nmap", "Burp Suite", "Windows"]


def test_parse_nacionalidad() -> None:
    assert _parse_nacionalidad("Nacionalidad: Mexicana") == "Mexicana"
    assert _parse_nacionalidad("Sin dato") == ""


def test_inferir_grado() -> None:
    assert _inferir_grado("Licenciatura en Sistemas") == "Licenciatura"
    assert _inferir_grado("Ingeniería en Ciberseguridad") == "Ingeniería"
    assert _inferir_grado("Curso de Python") == ""


def test_normalize_header() -> None:
    assert _normalize_header("  Experiencia  ") == "EXPERIENCIA"
    assert _normalize_header("Educación") == "EDUCACIÓN"


def test_parse_datos_personales() -> None:
    lineas = [
        "Sexo: Masculino",
        "Estado Civil: Soltero",
        "Vive con: Solo",
        "Tiene licencia de manejo: Si",
        "¿Cómo supo de esta vacante?: Anuncio",
        "Otra línea sin dos puntos",
    ]
    datos = _parse_datos_personales(lineas)
    assert datos == {
        "sexo": "Masculino",
        "estado_civil": "Soltero",
        "vive_con": "Solo",
        "licencia": "Si",
        "como_supo": "Anuncio",
    }


def test_parse_datos_personales_vacios() -> None:
    assert _parse_datos_personales([]) == {}
    assert _parse_datos_personales(["Sexo:", "Sin dos puntos"]) == {}


def test_normalize_clave() -> None:
    assert _normalize_clave("  Estado  Civil ") == "estado civil"
    assert _normalize_clave("¿Cómo supo?") == "¿como supo?"
