"""Pruebas del inspector de formularios PDF."""

from __future__ import annotations

from pathlib import Path

import pytest

from cvformfiller.exceptions import FormInspectionError
from cvformfiller.form_inspector import (
    _field_type,
    _nearest_labels,
    _nearest_line_label,
    _right_label,
    inspect_form,
)
from cvformfiller.models import FieldType

FORM_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "formulario_empleo.pdf"


def test_inspect_form_fixture(form_fields) -> None:
    assert len(form_fields) == 222
    assert all(field.name for field in form_fields)
    assert all(field.rect for field in form_fields)


def test_inspect_form_types(form_fields) -> None:
    tipos = {field.type for field in form_fields}
    assert FieldType.TEXT in tipos
    assert FieldType.CHECKBOX in tipos


def test_inspect_form_key_labels(form_fields) -> None:
    por_nombre = {field.name: field for field in form_fields}
    assert por_nombre["Text12"].label == "Nombre(s)"
    assert por_nombre["Text10"].label == "Apellido Paterno"
    assert por_nombre["Text19"].label == "Teléfono"
    assert por_nombre["Text38"].label == "Clave Única de Registro de Población"
    assert por_nombre["Text80"].row_label == "Primaria"
    assert por_nombre["Text81"].column_label == "Dirección"
    assert por_nombre["Text127"].row_label == "Nombre de la Compañía"
    assert por_nombre["Text139"].row_label == "Puesto desempeñado"


def test_inspect_form_line_and_right_labels(form_fields) -> None:
    por_nombre = {field.name: field for field in form_fields}
    assert por_nombre["Check Box20"].line_label == "Sexo"
    assert por_nombre["Check Box20"].right_label == "Masculino"
    assert por_nombre["Check Box25"].line_label == "Vive con"
    assert por_nombre["Check Box25"].right_label == "Solo"
    assert por_nombre["Check Box35"].line_label == "Estado Civil"
    assert por_nombre["Check Box35"].right_label == "Soltero"
    assert por_nombre["Check Box44"].line_label == "Tiene licencia de manejo"
    assert por_nombre["Check Box44"].right_label == "No"
    assert por_nombre["Check Box45"].right_label == "Si"
    assert por_nombre["Check Box181"].line_label == "¿Como supo de este empleo?"
    assert por_nombre["Check Box181"].right_label == "Anuncio"


def test_inspect_form_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FormInspectionError):
        inspect_form(tmp_path / "no_existe.pdf")


def test_inspect_form_without_acroform(tmp_path: Path) -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    archivo = tmp_path / "sin_campos.pdf"
    with archivo.open("wb") as handle:
        writer.write(handle)
    with pytest.raises(FormInspectionError):
        inspect_form(archivo)


def test_field_type_text() -> None:
    assert _field_type({"/FT": "/Tx"}) is FieldType.TEXT


def test_field_type_checkbox() -> None:
    assert _field_type({"/FT": "/Btn"}) is FieldType.CHECKBOX


def test_field_type_radio() -> None:
    assert _field_type({"/FT": "/Btn", "/Ff": 1 << 15}) is FieldType.RADIO


def test_field_type_unknown() -> None:
    assert _field_type({"/FT": "/Sig"}) is FieldType.UNKNOWN
    assert _field_type({}) is FieldType.UNKNOWN


def test_nearest_labels_above() -> None:
    words = [
        {"text": "Nombre", "x0": 10.0, "x1": 50.0, "top": 50.0, "bottom": 59.0},
        {"text": "Extra", "x0": 60.0, "x1": 90.0, "top": 50.0, "bottom": 59.0},
    ]
    label, row, column, confidence = _nearest_labels((10.0, 25.0, 80.0, 40.0), 100.0, words)
    assert label == "Nombre Extra"
    assert row == label
    assert column == label
    assert confidence > 0.9


def test_nearest_labels_left() -> None:
    words = [
        {"text": "Domicilio", "x0": 5.0, "x1": 40.0, "top": 62.0, "bottom": 72.0},
    ]
    label, row, column, _ = _nearest_labels((60.0, 25.0, 120.0, 40.0), 100.0, words)
    assert label == "Domicilio"
    assert row == "Domicilio"


def test_nearest_line_label_above() -> None:
    words = [
        {"text": "Estado", "x0": 40.0, "x1": 60.0, "top": 60.0, "bottom": 68.0},
        {"text": "Civil", "x0": 62.0, "x1": 80.0, "top": 60.0, "bottom": 68.0},
        {"text": "Soltero", "x0": 90.0, "x1": 110.0, "top": 20.0, "bottom": 28.0},
    ]
    assert _nearest_line_label((45.0, 20.0, 60.0, 30.0), 100.0, words) == "Estado Civil"


def test_nearest_line_label_prefers_closest_line() -> None:
    words = [
        {"text": "Lejos", "x0": 0.0, "x1": 20.0, "top": 10.0, "bottom": 18.0},
        {"text": "Cerca", "x0": 40.0, "x1": 60.0, "top": 40.0, "bottom": 48.0},
    ]
    assert _nearest_line_label((45.0, 20.0, 60.0, 30.0), 100.0, words) == "Cerca"


def test_right_label_groups_option() -> None:
    words = [
        {"text": "Otro", "x0": 60.0, "x1": 75.0, "top": 72.0, "bottom": 80.0},
        {"text": "medio", "x0": 77.0, "x1": 95.0, "top": 72.0, "bottom": 80.0},
    ]
    assert _right_label((10.0, 20.0, 30.0, 30.0), 100.0, words) == "Otro medio"


def test_right_label_empty_without_candidates() -> None:
    words = [
        {"text": "Arriba", "x0": 10.0, "x1": 30.0, "top": 40.0, "bottom": 48.0},
    ]
    assert _right_label((10.0, 20.0, 30.0, 30.0), 100.0, words) == ""
