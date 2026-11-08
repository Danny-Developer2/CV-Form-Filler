"""Pruebas del mapeo del CV a los campos del formulario."""

from __future__ import annotations

from cvformfiller.mapper import (
    _assign_education_rows,
    _duration,
    _education_level,
    _match_score,
    _normalize,
    _split_period,
    _years,
    map_cv_to_form,
)
from cvformfiller.models import CvData, Education, Experience, FieldType, FormField


def _field(name: str, label: str, row: str = "", column: str = "", page: int = 0) -> FormField:
    return FormField(
        name=name,
        type=FieldType.TEXT,
        rect=(10.0, 100.0, 110.0, 120.0),
        page=page,
        label=label,
        row_label=row,
        column_label=column or label,
    )


def _checkbox(
    name: str,
    label: str,
    line: str = "",
    right: str = "",
    page: int = 0,
) -> FormField:
    return FormField(
        name=name,
        type=FieldType.CHECKBOX,
        rect=(10.0, 100.0, 30.0, 120.0),
        page=page,
        label=label,
        row_label=label,
        column_label=label,
        line_label=line or label,
        right_label=right,
    )


def test_map_real_fixtures(mapping) -> None:
    valores = {item.field: item.value for item in mapping.fields}
    assert valores["Text12"] == "Juan"
    assert valores["Text10"] == "Perez"
    assert valores["Text11"] == "Lopez"
    assert valores["Text19"] == "+52 81 0000 0000"
    assert valores["Text14"] == "Ficticia, Nuevo León"
    assert valores["Text127"] == "Empresa ABC"
    assert valores["Text139"] == "Desarrollador Backend"
    assert valores["Text98"] == "Ingeniería Ficticia"
    assert valores["Text104"] == "Curso de Python"
    assert mapping.total_fields == 222
    assert mapping.filled_count == 39


def test_map_real_checkboxes(mapping) -> None:
    valores = {item.field: item.value for item in mapping.fields}
    assert valores["Check Box20"] == "Si"
    assert valores["Check Box25"] == "Si"
    assert valores["Check Box35"] == "Si"
    assert valores["Check Box45"] == "Si"
    assert valores["Check Box181"] == "Si"
    assert "Check Box21" not in valores
    assert "Check Box44" not in valores
    assert "Check Box182" not in valores


def test_map_real_missing(mapping) -> None:
    assert "Text30" in mapping.missing
    assert "Text31" in mapping.missing
    assert "Text38" in mapping.missing
    assert "Text40" in mapping.missing
    assert "Text41" in mapping.missing
    assert "Text80" in mapping.missing
    assert "Text11" not in mapping.missing


def test_map_synthetic() -> None:
    cv = CvData(
        nombre="Ana",
        apellidos="García López",
        experiencia=[Experience(puesto="Dev", empresa="Acme", periodo="2020 - 2022")],
        educacion=[Education(titulo="Licenciatura", institucion="UNAM", periodo="2016 - 2020")],
        idiomas=["Inglés: Avanzado"],
    )
    fields = [
        _field("f1", "Nombre(s)"),
        _field("f2", "Apellido Paterno"),
        _field("f3", "Apellido Materno"),
        _field("f4", "Teléfono"),
        _field("f5", "Domicilio"),
    ]
    result = map_cv_to_form(cv, fields)
    valores = {item.field: item.value for item in result.fields}
    assert valores["f1"] == "Ana"
    assert valores["f2"] == "García"
    assert valores["f3"] == "López"
    assert "f4" in result.missing
    assert "f5" in result.missing


def test_match_score_exact_and_partial() -> None:
    assert _match_score("Nombre", "nombre") == 1.0
    assert _match_score("Nombre(s)", "nombre") >= 0.9
    assert _match_score("Teléfono", "telefono") == 1.0
    assert _match_score("Correo electrónico", "correo electronico") == 1.0
    assert _match_score("Texto无关", "nombre") == 0.0


def test_match_score_short_alias() -> None:
    assert _match_score("Años", "a") == 0.0
    assert _match_score("A", "a") == 1.0
    assert _match_score("De", "de") == 1.0


def test_normalize() -> None:
    assert _normalize("¡Cantidad, de cosas!") == "cantidad de cosas"
    assert _normalize("") == ""


def test_split_period() -> None:
    assert _split_period("Abril 2024 - Mayo 2026") == ("Abril 2024", "Mayo 2026")
    assert _split_period("2022 - 2023") == ("2022", "2023")
    assert _split_period("2020") == ("2020", "")


def test_years_and_duration() -> None:
    assert _years("2019 - 2024") == ("2019", "2024")
    assert _years("2026 - 2026 (reformulación vigente)") == ("2026", "2026")
    assert _duration("2019", "2024") == "5"
    assert _duration("2026", "2026") == "1"
    assert _duration("", "") == ""


def test_education_level() -> None:
    assert _education_level("Licenciatura en Sistemas") == "profesional"
    assert _education_level("Preparatoria") == "preparatoria"
    assert _education_level("Secundaria") == "secundaria"
    assert _education_level("Curso de Python") == "comercial"


def test_assign_education_rows() -> None:
    rows = {
        "profesional": [_field("p1", "Profesional")],
        "comercial": [_field("c1", "Comercial u Otras")],
        "preparatoria": [_field("pr1", "Preparatoria")],
    }
    entradas = [
        Education(titulo="Ingeniería", institucion="UVM", periodo="2020 - 2024"),
        Education(titulo="Otra carrera", institucion="ABC", periodo="2019 - 2020"),
    ]
    asignaciones = _assign_education_rows(entradas, rows)
    assert asignaciones["profesional"].titulo == "Ingeniería"
    assert asignaciones["comercial"].titulo == "Otra carrera"


def test_map_checkboxes_synthetic() -> None:
    cv = CvData(
        nombre="Ana",
        sexo="Femenino",
        estado_civil="Casado",
        vive_con="Su familia",
        licencia="No",
        como_supo="Anuncio",
    )
    fields = [
        _checkbox("c1", "Sexo", line="Sexo", right="Masculino"),
        _checkbox("c2", "Sexo", line="Sexo", right="Femenino"),
        _checkbox("c3", "Estado Civil", line="Estado Civil", right="Soltero"),
        _checkbox("c4", "Estado Civil", line="Estado Civil", right="Casado"),
        _checkbox("c5", "Vive con", line="Vive con", right="Solo"),
        _checkbox("c6", "Vive con", line="Vive con", right="Su familia"),
        _checkbox("c7", "Tiene licencia", line="Tiene licencia de manejo", right="Si"),
        _checkbox("c8", "Tiene licencia", line="Tiene licencia de manejo", right="No"),
        _checkbox("c9", "¿Cómo supo?", line="¿Cómo supo de este empleo?", right="Anuncio"),
        _checkbox("c10", "¿Cómo supo?", line="¿Cómo supo de este empleo?", right="Otro medio"),
    ]
    result = map_cv_to_form(cv, fields)
    valores = {item.field: item.value for item in result.fields}
    assert valores["c2"] == "Si"
    assert valores["c4"] == "Si"
    assert valores["c6"] == "Si"
    assert valores["c8"] == "Si"
    assert valores["c9"] == "Si"
    assert "c1" not in valores
    assert "c3" not in valores
    assert "c5" not in valores
    assert "c7" not in valores
    assert "c10" not in valores


def test_map_checkboxes_without_cv_data() -> None:
    cv = CvData(nombre="Ana")
    fields = [
        _checkbox("c1", "Sexo", line="Sexo", right="Masculino"),
        _checkbox("c2", "Sexo", line="Sexo", right="Femenino"),
    ]
    result = map_cv_to_form(cv, fields)
    assert result.fields == []
    assert "c1" in result.missing
    assert "c2" in result.missing
