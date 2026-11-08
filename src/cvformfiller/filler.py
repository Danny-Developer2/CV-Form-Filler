"""Relleno del PDF del formulario con pypdf.

Se genera una copia del formulario con los valores ``/V`` y las apariencias
regeneradas a un tamaño de fuente uniforme. El PDF original nunca se sobrescribe.
"""

from __future__ import annotations

import time
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from cvformfiller.exceptions import FillError
from cvformfiller.models import FieldType, FillReport, FormField, MappedField
from cvformfiller.utils.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_FONT = "/Helv"
_TRUTHY = {"yes", "si", "sí", "true", "verdadero", "1", "x", "/yes", "marcado"}


def fill_form(
    form_path: Path,
    fields: list[FormField],
    mapping: list[MappedField],
    output_path: Path,
    font_size: float = 10.0,
    dry_run: bool = False,
    missing_fields: list[str] | None = None,
) -> FillReport:
    """Rellena el formulario y escribe una copia en ``output_path``."""
    inicio = time.perf_counter()
    if not form_path.exists():
        raise FillError(f"el formulario no existe: {form_path}")
    if output_path.resolve() == form_path.resolve():
        raise FillError("la salida no puede sobrescribir el formulario original")
    if font_size <= 0:
        raise FillError("el tamaño de fuente debe ser mayor que cero")

    faltantes = list(missing_fields or [])
    valores = _build_values(fields, mapping, font_size)
    if dry_run:
        return FillReport(
            output=str(output_path),
            total_fields=len(fields),
            fields_filled=len(valores),
            fields_missing=len(faltantes),
            missing_fields=faltantes,
            font_size=font_size,
            dry_run=True,
            duration_seconds=time.perf_counter() - inicio,
        )

    try:
        reader = PdfReader(form_path)
        writer = PdfWriter()
        writer.append(reader)
        paginas = _group_by_page(fields, valores)
        for pagina, campos in paginas.items():
            if 0 <= pagina < len(writer.pages):
                writer.update_page_form_field_values(
                    writer.pages[pagina], campos, auto_regenerate=True
                )
        writer.set_need_appearances_writer(True)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as handle:
            writer.write(handle)
    except FillError:
        raise
    except Exception as exc:
        raise FillError(f"no se pudo escribir el PDF de salida: {exc}") from exc

    logger.debug("PDF rellenado escrito en %s", output_path)
    return FillReport(
        output=str(output_path),
        total_fields=len(fields),
        fields_filled=len(valores),
        fields_missing=len(faltantes),
        missing_fields=faltantes,
        font_size=font_size,
        dry_run=False,
        duration_seconds=time.perf_counter() - inicio,
    )


def _build_values(
    fields: list[FormField], mapping: list[MappedField], font_size: float
) -> dict[str, str | tuple[str, str, float]]:
    """Construye el diccionario de valores campo -> valor (texto o /Yes)."""
    tipos = {field.name: field.type for field in fields}
    valores: dict[str, str | tuple[str, str, float]] = {}
    for item in mapping:
        if not item.value:
            continue
        tipo = tipos.get(item.field, FieldType.TEXT)
        if tipo is FieldType.CHECKBOX:
            if item.value.lower() in _TRUTHY:
                valores[item.field] = "/Yes"
        elif tipo is FieldType.RADIO:
            valores[item.field] = item.value
        else:
            valores[item.field] = (item.value, _DEFAULT_FONT, font_size)
    return valores


def _group_by_page(
    fields: list[FormField], valores: dict[str, str | tuple[str, str, float]]
) -> dict[int, dict[str, str | tuple[str, str, float]]]:
    """Agrupa los valores por página para actualizar el formulario."""
    paginas: dict[int, dict[str, str | tuple[str, str, float]]] = {}
    paginas_por_campo = {field.name: field.page for field in fields}
    for nombre, valor in valores.items():
        pagina = paginas_por_campo.get(nombre, 0)
        paginas.setdefault(pagina, {})[nombre] = valor
    return paginas


__all__ = ["fill_form"]
