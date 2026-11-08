"""Pruebas de los modelos de datos."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cvformfiller.models import (
    Contacto,
    CvData,
    Education,
    Experience,
    FieldType,
    FillReport,
    FormField,
    MappedField,
    MappingResult,
)


def test_field_type_values() -> None:
    assert FieldType.TEXT.value == "text"
    assert FieldType.CHECKBOX.value == "checkbox"
    assert FieldType.RADIO.value == "radio"
    assert FieldType.UNKNOWN.value == "unknown"


def test_contacto_defaults() -> None:
    contacto = Contacto()
    assert contacto.telefono == ""
    assert contacto.email == ""
    assert contacto.web == ""


def test_cv_data_is_frozen() -> None:
    cv = CvData(nombre="Juan")
    with pytest.raises(ValidationError):
        cv.nombre = "Pedro"  # type: ignore[misc]


def test_experience_is_frozen() -> None:
    experience = Experience(puesto="Dev")
    with pytest.raises(ValidationError):
        experience.puesto = "QA"  # type: ignore[misc]


def test_education_is_frozen() -> None:
    education = Education(titulo="Licenciatura")
    with pytest.raises(ValidationError):
        education.titulo = "Ingeniería"  # type: ignore[misc]


def test_form_field_is_frozen() -> None:
    field = FormField(name="Text1", type=FieldType.TEXT, rect=(0, 0, 10, 10), page=0)
    with pytest.raises(ValidationError):
        field.name = "Text2"  # type: ignore[misc]


def test_cv_data_checkbox_defaults() -> None:
    cv = CvData()
    assert cv.sexo == ""
    assert cv.estado_civil == ""
    assert cv.vive_con == ""
    assert cv.licencia == ""
    assert cv.como_supo == ""


def test_form_field_label_defaults() -> None:
    field = FormField(name="Check Box1", type=FieldType.CHECKBOX, rect=(0, 0, 10, 10), page=0)
    assert field.label == ""
    assert field.line_label == ""
    assert field.right_label == ""


def test_mapping_result_fill_ratio() -> None:
    result = MappingResult(
        fields=[MappedField(field="Text1", label="Nombre", value="Juan", source="nombre")],
        total_fields=4,
        filled_count=1,
    )
    assert result.fill_ratio == 0.25


def test_mapping_result_fill_ratio_zero() -> None:
    assert MappingResult().fill_ratio == 0.0


def test_fill_report_defaults() -> None:
    report = FillReport(output="salida.pdf")
    assert report.fields_filled == 0
    assert report.font_size == 10.0
    assert report.dry_run is False
    assert report.errors == []
