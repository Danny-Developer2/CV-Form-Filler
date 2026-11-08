"""Verificación del PDF rellenado.

Comprueba con pypdf que los valores ``/V`` quedaron en los campos correctos y
renderiza el documento con pypdfium2 para confirmar que cada valor se dibujó en
la región de su campo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
from pypdf import PdfReader

from cvformfiller.exceptions import VerificationError
from cvformfiller.models import FieldType, FormField, MappedField, VerificationReport
from cvformfiller.utils.logger import get_logger

logger = get_logger(__name__)

_RENDER_SCALE = 2.0
_DARK_THRESHOLD = 128
_MIN_DARK_RATIO = 0.002


def verify_fill(
    output_path: Path,
    fields: list[FormField],
    mapping: list[MappedField],
) -> VerificationReport:
    """Verifica que el PDF de salida contiene los valores en los campos correctos."""
    if not output_path.exists():
        raise VerificationError(f"el PDF de salida no existe: {output_path}")

    errores: list[str] = []
    passed = 0
    failed = 0

    try:
        reader = PdfReader(output_path)
    except Exception as exc:
        raise VerificationError(f"no se pudo leer el PDF de salida: {exc}") from exc

    pdf_fields = reader.get_fields() or {}
    tipos = {field.name: field.type for field in fields}

    for item in mapping:
        if not item.value:
            continue
        campo = pdf_fields.get(item.field)
        if campo is None:
            errores.append(f"el campo {item.field!r} no existe en el PDF de salida")
            failed += 1
            continue
        valor = campo.get("/V")
        valor_str = str(valor) if valor is not None else ""
        if tipos.get(item.field) is FieldType.CHECKBOX:
            if valor_str == "/Yes":
                passed += 1
            else:
                errores.append(
                    f"el checkbox {item.field!r} quedó en {valor_str!r} en lugar de /Yes"
                )
                failed += 1
        elif valor_str == item.value:
            passed += 1
        else:
            errores.append(
                f"el campo {item.field!r} contiene {valor_str!r} en lugar de {item.value!r}"
            )
            failed += 1

    rendered_pages, render_errores = _verify_render(output_path, fields, mapping)
    errores.extend(render_errores)
    failed += len(render_errores)
    if rendered_pages == len(reader.pages):
        passed += 1
    else:
        errores.append(
            f"el PDF de salida tiene {rendered_pages} páginas y el original {len(reader.pages)}"
        )
        failed += 1

    logger.debug("verificación: %d_OK, %d errores", passed, failed)
    return VerificationReport(
        ok=failed == 0,
        checks_passed=passed,
        checks_failed=failed,
        rendered_pages=rendered_pages,
        errors=errores,
    )


def _verify_render(
    output_path: Path,
    fields: list[FormField],
    mapping: list[MappedField],
) -> tuple[int, list[str]]:
    """Renderiza con pypdfium2 y comprueba que cada valor se dibujó en su campo."""
    errores: list[str] = []
    try:
        document = pdfium.PdfDocument(output_path)
        document.init_forms()
    except Exception as exc:
        errores.append(f"no se pudo renderizar el PDF con pypdfium2: {exc}")
        return 0, errores

    paginas: dict[int, Any] = {}
    alturas: dict[int, float] = {}
    rects: dict[str, tuple[int, float, float, float, float]] = {}
    for field in fields:
        rects[field.name] = (
            field.page,
            float(field.rect[0]),
            float(field.rect[1]),
            float(field.rect[2]),
            float(field.rect[3]),
        )

    for item in mapping:
        if not item.value or item.field not in rects:
            continue
        pagina, x0, y0, x1, y1 = rects[item.field]
        if pagina >= len(document):
            continue
        if pagina not in paginas:
            page = document[pagina]
            alturas[pagina] = float(page.get_size()[1])
            paginas[pagina] = page.render(scale=_RENDER_SCALE).to_pil().convert("L")
        imagen = paginas[pagina]
        page_height = alturas[pagina]
        ix0 = int(x0 * _RENDER_SCALE)
        ix1 = int(x1 * _RENDER_SCALE)
        iy0 = int((page_height - max(y0, y1)) * _RENDER_SCALE)
        iy1 = int((page_height - min(y0, y1)) * _RENDER_SCALE)
        ix0, ix1 = sorted((ix0, ix1))
        iy0, iy1 = sorted((iy0, iy1))
        ix0 += 2
        iy0 += 2
        ix1 = max(ix0 + 1, ix1 - 2)
        iy1 = max(iy0 + 1, iy1 - 2)
        region = imagen.crop((ix0, iy0, ix1, iy1))
        datos = region.tobytes()
        oscuros = sum(1 for byte in datos if byte < _DARK_THRESHOLD)
        ratio = oscuros / max(1, len(datos))
        if ratio < _MIN_DARK_RATIO:
            errores.append(
                f"el valor de {item.field!r} no se dibujó en la región del campo "
                f"(página {pagina + 1})"
            )

    return len(document), errores


__all__ = ["verify_fill"]
