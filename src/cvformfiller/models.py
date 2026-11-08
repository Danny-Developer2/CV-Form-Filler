"""Modelos de datos de CV-Form-Filler.

Todos los modelos son inmutables (``ConfigDict(frozen=True)``) para garantizar
que el CV parseado y el mapeo no se modifiquen una vez construidos.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class FieldType(StrEnum):
    """Tipo de campo AcroForm."""

    TEXT = "text"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    UNKNOWN = "unknown"


class Contacto(BaseModel):
    """Datos de contacto extraídos del CV."""

    model_config = ConfigDict(frozen=True)

    telefono: str = ""
    email: str = ""
    web: str = ""


class Experience(BaseModel):
    """Entrada de experiencia laboral."""

    model_config = ConfigDict(frozen=True)

    puesto: str = ""
    empresa: str = ""
    periodo: str = ""
    descripcion: str = ""


class Education(BaseModel):
    """Entrada de formación académica."""

    model_config = ConfigDict(frozen=True)

    titulo: str = ""
    institucion: str = ""
    periodo: str = ""
    grado: str = ""


class CvData(BaseModel):
    """CV normalizado extraído de un PDF o DOCX."""

    model_config = ConfigDict(frozen=True)

    nombre: str = ""
    apellidos: str = ""
    contacto: Contacto = Field(default_factory=Contacto)
    fecha_nacimiento: str = ""
    domicilio: str = ""
    ciudad: str = ""
    estado: str = ""
    nacionalidad: str = ""
    curp: str = ""
    rfc: str = ""
    nss: str = ""
    sexo: str = ""
    estado_civil: str = ""
    vive_con: str = ""
    licencia: str = ""
    como_supo: str = ""
    experiencia: list[Experience] = Field(default_factory=list)
    educacion: list[Education] = Field(default_factory=list)
    idiomas: list[str] = Field(default_factory=list)
    habilidades: list[str] = Field(default_factory=list)
    software: list[str] = Field(default_factory=list)

    @property
    def has_contact(self) -> bool:
        """Indica si el CV incluye algún dato de contacto."""
        return bool(self.contacto.telefono or self.contacto.email or self.contacto.web)


class FormField(BaseModel):
    """Campo del formulario inspeccionado con su etiqueta por proximidad."""

    model_config = ConfigDict(frozen=True)

    name: str
    type: FieldType
    rect: tuple[float, float, float, float]
    page: int
    label: str = ""
    row_label: str = ""
    column_label: str = ""
    line_label: str = ""
    right_label: str = ""
    confidence: float = 0.0


class MappedField(BaseModel):
    """Campo del formulario con el valor que se le asignará."""

    model_config = ConfigDict(frozen=True)

    field: str
    label: str
    value: str
    source: str
    confidence: float = 0.0


class MappingResult(BaseModel):
    """Resultado del mapeo del CV sobre los campos del formulario."""

    model_config = ConfigDict(frozen=True)

    fields: list[MappedField] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    total_fields: int = 0
    filled_count: int = 0

    @property
    def fill_ratio(self) -> float:
        """Fracción de campos con datos (0.0 a 1.0)."""
        if self.total_fields == 0:
            return 0.0
        return self.filled_count / self.total_fields


class FillReport(BaseModel):
    """Informe del proceso de rellenado y verificación."""

    model_config = ConfigDict(frozen=True)

    output: str
    total_fields: int = 0
    fields_filled: int = 0
    fields_missing: int = 0
    missing_fields: list[str] = Field(default_factory=list)
    font_size: float = 10.0
    dry_run: bool = False
    checks_passed: int = 0
    checks_failed: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0


class VerificationReport(BaseModel):
    """Resultado de la verificación del PDF rellenado."""

    model_config = ConfigDict(frozen=True)

    ok: bool = True
    checks_passed: int = 0
    checks_failed: int = 0
    rendered_pages: int = 0
    errors: list[str] = Field(default_factory=list)


__all__ = [
    "FieldType",
    "Contacto",
    "Experience",
    "Education",
    "CvData",
    "FormField",
    "MappedField",
    "MappingResult",
    "FillReport",
    "VerificationReport",
]
