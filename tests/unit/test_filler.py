"""Pruebas del rellenado del PDF."""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader

from cvformfiller.exceptions import FillError
from cvformfiller.filler import _build_values, fill_form
from cvformfiller.models import FieldType, FormField, MappedField

FORM_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "formulario_empleo.pdf"


def test_fill_form_real(form_fields, mapping, tmp_path: Path) -> None:
    salida = tmp_path / "salida.pdf"
    report = fill_form(
        FORM_FIXTURE,
        form_fields,
        mapping.fields,
        salida,
        font_size=10.0,
        missing_fields=mapping.missing,
    )
    assert salida.exists()
    assert report.fields_filled == 39
    assert report.fields_missing == len(mapping.missing)
    assert report.font_size == 10.0

    reader = PdfReader(salida)
    campos = reader.get_fields() or {}
    assert str(campos["Text12"].get("/V")) == "Juan"
    assert str(campos["Text10"].get("/V")) == "Perez"
    assert str(campos["Text11"].get("/V")) == "Lopez"
    assert str(campos["Text19"].get("/V")) == "+52 81 0000 0000"
    assert str(campos["Text127"].get("/V")) == "Empresa ABC"
    # Las casillas se marcan con /Yes y las no coincidentes quedan vacías.
    assert str(campos["Check Box20"].get("/V")) == "/Yes"
    assert str(campos["Check Box25"].get("/V")) == "/Yes"
    assert str(campos["Check Box35"].get("/V")) == "/Yes"
    assert str(campos["Check Box45"].get("/V")) == "/Yes"
    assert str(campos["Check Box181"].get("/V")) == "/Yes"
    assert campos["Check Box21"].get("/V") is None
    assert campos["Check Box44"].get("/V") is None
    # Campos sin datos en el CV quedan vacíos.
    assert campos["Text38"].get("/V") is None


def test_fill_form_does_not_modify_original(form_fields, mapping, tmp_path: Path) -> None:
    original = PdfReader(FORM_FIXTURE)
    antes = len(original.pages)
    fill_form(FORM_FIXTURE, form_fields, mapping.fields, tmp_path / "salida.pdf")
    despues = PdfReader(FORM_FIXTURE)
    assert len(despues.pages) == antes
    assert (despues.get_fields() or {})["Text12"].get("/V") is None


def test_fill_form_dry_run(form_fields, mapping, tmp_path: Path) -> None:
    salida = tmp_path / "salida.pdf"
    report = fill_form(FORM_FIXTURE, form_fields, mapping.fields, salida, dry_run=True)
    assert report.dry_run is True
    assert not salida.exists()


def test_fill_form_refuses_to_overwrite_original(form_fields, mapping) -> None:
    with pytest.raises(FillError):
        fill_form(FORM_FIXTURE, form_fields, mapping.fields, FORM_FIXTURE)


def test_fill_form_invalid_font_size(form_fields, mapping, tmp_path: Path) -> None:
    with pytest.raises(FillError):
        fill_form(FORM_FIXTURE, form_fields, mapping.fields, tmp_path / "s.pdf", font_size=0)


def test_fill_form_missing_file(form_fields, mapping, tmp_path: Path) -> None:
    with pytest.raises(FillError):
        fill_form(tmp_path / "no.pdf", form_fields, mapping.fields, tmp_path / "s.pdf")


def test_build_values_checkbox() -> None:
    fields = [
        FormField(name="Check Box20", type=FieldType.CHECKBOX, rect=(0, 0, 10, 10), page=0),
        FormField(name="Text1", type=FieldType.TEXT, rect=(0, 0, 10, 10), page=0),
    ]
    mapping = [
        MappedField(field="Check Box20", label="Masculino", value="sí", source="sexo"),
        MappedField(field="Text1", label="Nombre", value="Juan", source="nombre"),
    ]
    valores = _build_values(fields, mapping, 10.0)
    assert valores["Check Box20"] == "/Yes"
    assert valores["Text1"] == ("Juan", "/Helv", 10.0)


def test_build_values_checkbox_off() -> None:
    fields = [
        FormField(name="Check Box20", type=FieldType.CHECKBOX, rect=(0, 0, 10, 10), page=0),
    ]
    mapping = [
        MappedField(field="Check Box20", label="Masculino", value="no", source="sexo"),
    ]
    assert _build_values(fields, mapping, 10.0) == {}
