"""Pruebas de la verificación del PDF rellenado."""

from __future__ import annotations

from pathlib import Path

import pytest

from cvformfiller.exceptions import VerificationError
from cvformfiller.filler import fill_form
from cvformfiller.models import MappedField
from cvformfiller.verifier import verify_fill

FORM_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "formulario_empleo.pdf"


@pytest.fixture(scope="module")
def filled_pdf(tmp_path_factory, form_fields, mapping) -> Path:
    """PDF rellenado una vez para todas las pruebas del módulo."""
    salida = tmp_path_factory.mktemp("relleno") / "salida.pdf"
    fill_form(FORM_FIXTURE, form_fields, mapping.fields, salida)
    return salida


def test_verify_real_fill(filled_pdf, form_fields, mapping) -> None:
    report = verify_fill(filled_pdf, form_fields, mapping.fields)
    assert report.ok is True
    assert report.checks_failed == 0
    assert report.checks_passed >= len(mapping.fields)
    assert report.rendered_pages == 2


def test_verify_missing_file(form_fields, mapping, tmp_path: Path) -> None:
    with pytest.raises(VerificationError):
        verify_fill(tmp_path / "no.pdf", form_fields, mapping.fields)


def test_verify_detects_wrong_value(filled_pdf, form_fields, mapping) -> None:
    manipulado = [
        MappedField(
            field="Text12",
            label="Nombre(s)",
            value="Nombre incorrecto",
            source="nombre",
        )
    ]
    report = verify_fill(filled_pdf, form_fields, manipulado)
    assert report.ok is False
    assert report.checks_failed >= 1
    assert any("Text12" in error for error in report.errors)


def test_verify_empty_mapping(filled_pdf, form_fields) -> None:
    report = verify_fill(filled_pdf, form_fields, [])
    assert report.ok is True
    assert report.rendered_pages == 2
