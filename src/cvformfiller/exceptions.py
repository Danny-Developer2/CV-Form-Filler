"""Jerarquía de excepciones centralizada de CV-Form-Filler."""

from __future__ import annotations


class CvFormFillerError(Exception):
    """Excepción base de CV-Form-Filler."""


class CvParseError(CvFormFillerError):
    """El CV no se pudo leer o no tiene un formato admitido."""


class FormInspectionError(CvFormFillerError):
    """El formulario PDF no tiene campos AcroForm o no se pudo inspeccionar."""


class MappingError(CvFormFillerError):
    """No se pudo mapear el CV sobre los campos del formulario."""


class FillError(CvFormFillerError):
    """No se pudo escribir el PDF de salida."""


class VerificationError(CvFormFillerError):
    """La verificación del PDF rellenado no superó las comprobaciones."""


__all__ = [
    "CvFormFillerError",
    "CvParseError",
    "FormInspectionError",
    "MappingError",
    "FillError",
    "VerificationError",
]
