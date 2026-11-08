"""Configuración común de las pruebas de CV-Form-Filler."""

from __future__ import annotations

from pathlib import Path

import pytest

from cvformfiller.cv_parser import parse_cv
from cvformfiller.form_inspector import inspect_form
from cvformfiller.mapper import map_cv_to_form
from cvformfiller.models import (
    CvData,
    FieldType,
    FormField,
    MappedField,
    MappingResult,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CV_FIXTURE = FIXTURES / "cv_juan_perez.pdf"
FORM_FIXTURE = FIXTURES / "formulario_empleo.pdf"


@pytest.fixture(scope="session")
def cv_data() -> CvData:
    """CV de prueba anonimizado parseado una sola vez para toda la sesión."""
    return parse_cv(CV_FIXTURE)


@pytest.fixture(scope="session")
def form_fields() -> list[FormField]:
    """Formulario de prueba inspeccionado una sola vez por sesión."""
    return inspect_form(FORM_FIXTURE)


@pytest.fixture(scope="session")
def checkbox_fields(form_fields: list[FormField]) -> list[FormField]:
    """Casillas del formulario de prueba."""
    return [field for field in form_fields if field.type is FieldType.CHECKBOX]


@pytest.fixture(scope="session")
def mapping(cv_data: CvData, form_fields: list[FormField]) -> MappingResult:
    """Mapeo del CV de prueba sobre el formulario de prueba."""
    return map_cv_to_form(cv_data, form_fields)


@pytest.fixture(scope="session")
def mapped_checkboxes(mapping: MappingResult) -> list[MappedField]:
    """Casillas marcadas por el mapeo del CV de prueba."""
    return [item for item in mapping.fields if item.field.startswith("Check Box")]
