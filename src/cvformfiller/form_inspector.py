"""Inspección de formularios PDF con campos AcroForm.

Para cada campo se registra su nombre, tipo, rectángulo y página, y se busca la
etiqueta impresa más cercana por proximidad geométrica (encima, a la izquierda o
debajo), agrupando palabras contiguas en la misma línea.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pdfplumber
from pypdf import PdfReader
from pypdf.generic import DictionaryObject

from cvformfiller.exceptions import FormInspectionError
from cvformfiller.models import FieldType, FormField
from cvformfiller.utils.logger import get_logger

logger = get_logger(__name__)

_FT_MAP = {
    "/Tx": FieldType.TEXT,
    "/Ch": FieldType.TEXT,
    "/Btn": FieldType.CHECKBOX,
    "/Sig": FieldType.UNKNOWN,
}

_RADIO_BIT = 1 << 15  # Ff: Radio

_WORD_GAP = 25.0
_LINE_TOLERANCE = 2.5


def inspect_form(path: Path) -> list[FormField]:
    """Inspecciona los campos AcroForm de un PDF y devuelve su metadatos."""
    if not path.exists():
        raise FormInspectionError(f"el formulario no existe: {path}")
    try:
        reader = PdfReader(path)
    except Exception as exc:
        raise FormInspectionError(f"no se pudo leer el formulario: {exc}") from exc

    root = reader.trailer["/Root"]
    if not isinstance(root, DictionaryObject):
        raise FormInspectionError("el PDF no tiene un diccionario raíz válido")
    acro_form = root.get("/AcroForm")
    if acro_form is None:
        raise FormInspectionError("el PDF no tiene diccionario /AcroForm")
    acro_form = acro_form.get_object()
    field_refs = acro_form.get("/Fields")
    if not field_refs:
        raise FormInspectionError("el PDF no tiene campos AcroForm")

    try:
        with pdfplumber.open(path) as pdf:
            pages_words = [page.extract_words() for page in pdf.pages]
            page_heights = [float(page.height) for page in pdf.pages]
    except Exception as exc:
        raise FormInspectionError(f"no se pudo extraer el texto del formulario: {exc}") from exc

    campos: list[FormField] = []
    for ref in field_refs:
        field = ref.get_object()
        nombre = str(field.get("/T", "")).strip()
        if not nombre:
            continue
        rect_raw = field.get("/Rect")
        if rect_raw is None:
            continue
        try:
            rect = tuple(float(value) for value in rect_raw)
        except (TypeError, ValueError) as exc:
            raise FormInspectionError(f"rectángulo no válido en el campo {nombre!r}") from exc
        if len(rect) != 4:
            continue
        pagina = _find_page(field, reader)
        tipo = _field_type(field)
        palabras = pages_words[pagina] if pagina < len(pages_words) else []
        alto = page_heights[pagina] if pagina < len(page_heights) else 792.0
        etiqueta, fila, columna, confianza = _nearest_labels(rect, alto, palabras)
        linea = _nearest_line_label(rect, alto, palabras)
        derecha = _right_label(rect, alto, palabras)
        campos.append(
            FormField(
                name=nombre,
                type=tipo,
                rect=rect,
                page=pagina,
                label=etiqueta,
                row_label=fila,
                column_label=columna,
                line_label=linea,
                right_label=derecha,
                confidence=round(confianza, 3),
            )
        )

    if not campos:
        raise FormInspectionError("el formulario no tiene campos con nombre y rectángulo")
    logger.debug("inspeccionados %d campos del formulario", len(campos))
    return campos


def _find_page(field: Any, reader: PdfReader) -> int:
    """Localiza la página a la que pertenece el widget del campo."""
    ref = getattr(field, "indirect_reference", None)
    if ref is None:
        return 0
    for index, page in enumerate(reader.pages):
        for annot in page.get("/Annots", []):
            if annot == ref:
                return index
            parent = annot.get_object().get("/Parent")
            if parent is not None and parent == ref:
                return index
    return 0


def _field_type(field: Any) -> FieldType:
    """Deduce el tipo de campo a partir de /FT y /Ff."""
    ft = str(field.get("/FT", ""))
    if ft == "/Btn":
        ff = field.get("/Ff", 0)
        try:
            if int(ff) & _RADIO_BIT:
                return FieldType.RADIO
        except (TypeError, ValueError):
            pass
        return FieldType.CHECKBOX
    return _FT_MAP.get(ft, FieldType.UNKNOWN)


def _nearest_labels(
    rect: tuple[float, float, float, float],
    page_height: float,
    words: list[dict[str, float]],
) -> tuple[str, str, str, float]:
    """Busca la etiqueta, fila y columna más cercanas al rectángulo del campo."""
    x0, y0, x1, y1 = rect
    top = page_height - max(y0, y1)
    bottom = page_height - min(y0, y1)
    field_height = max(bottom - top, 1.0)

    above: list[tuple[float, dict[str, float]]] = []
    below: list[tuple[float, dict[str, float]]] = []
    left: list[tuple[float, dict[str, float]]] = []

    for word in words:
        wx0, wx1 = float(word["x0"]), float(word["x1"])
        wt, wb = float(word["top"]), float(word["bottom"])
        if wx1 <= x0 + 1.5:
            vertical = max(0.0, min(wb, bottom) - max(wt, top))
            if vertical >= 0.25 * field_height:
                left.append((x0 - wx1, word))
            continue
        overlap = max(0.0, min(wx1, x1) - max(wx0, x0))
        if overlap <= 0.5:
            continue
        if wb <= top + 1.5:
            above.append((top - wb, word))
        elif wt >= bottom - 1.5:
            below.append((wt - bottom, word))

    best_above = _best_segment(above, x0)
    best_below = _best_segment(below, x0)
    best_left = _best_left_block(left, x0, top, bottom)

    gap = best_above[0] if best_above else float("inf")
    if best_left and (not best_above or best_left[0] < gap):
        gap = best_left[0]
    if best_below and best_below[0] < gap:
        gap = best_below[0]
    confidence = max(0.0, 1.0 - gap / 40.0) if gap != float("inf") else 0.0

    column_label = best_above[1] if best_above else (best_below[1] if best_below else "")
    row_label = best_left[1] if best_left else column_label
    label = column_label or row_label
    return label, row_label, column_label, confidence


def _nearest_line_label(
    rect: tuple[float, float, float, float],
    page_height: float,
    words: list[dict[str, float]],
) -> str:
    """Devuelve la línea de texto completa más cercana por encima o debajo.

    A diferencia de :func:`_nearest_labels`, no exige solapamiento horizontal con
    el campo: agrupa todas las palabras de la línea y devuelve el segmento
    contiguo más próximo. Primero elige la línea por distancia vertical (la
    etiqueta conceptual de una casilla está justo encima) y después el segmento
    más alineado con el centro del campo.
    """
    x0, y0, x1, y1 = rect
    top = page_height - max(y0, y1)
    bottom = page_height - min(y0, y1)
    centro_x = (x0 + x1) / 2.0

    lineas: dict[float, list[dict[str, float]]] = {}
    for word in words:
        wt, wb = float(word["top"]), float(word["bottom"])
        if wb > top + 1.5 and wt < bottom - 1.5:
            continue
        key = wt
        for existing in lineas:
            if abs(existing - wt) <= _LINE_TOLERANCE:
                key = existing
                break
        lineas.setdefault(key, []).append(word)
    if not lineas:
        return ""

    mejor_gap: float | None = None
    mejor_linea: list[dict[str, float]] = []
    for linea in lineas.values():
        wt = min(float(w["top"]) for w in linea)
        wb = max(float(w["bottom"]) for w in linea)
        gap = top - wb if wb <= top + 1.5 else wt - bottom
        if mejor_gap is None or gap < mejor_gap:
            mejor_gap = gap
            mejor_linea = linea

    mejor_texto = ""
    mejor_distancia: float | None = None
    for segmento in _segments_of_line(mejor_linea):
        sx0 = min(float(w["x0"]) for w in segmento)
        sx1 = max(float(w["x1"]) for w in segmento)
        distancia = 0.0 if sx0 <= centro_x <= sx1 else min(abs(sx0 - centro_x), abs(centro_x - sx1))
        if mejor_distancia is None or distancia < mejor_distancia:
            mejor_distancia = distancia
            mejor_texto = " ".join(
                str(w["text"]) for w in sorted(segmento, key=lambda w: float(w["x0"]))
            )
    return mejor_texto


def _segments_of_line(words: list[dict[str, float]]) -> list[list[dict[str, float]]]:
    """Agrupa las palabras de una línea en segmentos separados por huecos."""
    segmentos: list[list[dict[str, float]]] = []
    actual: list[dict[str, float]] = []
    for word in sorted(words, key=lambda w: float(w["x0"])):
        if actual and float(word["x0"]) - float(actual[-1]["x1"]) > _WORD_GAP:
            segmentos.append(actual)
            actual = []
        actual.append(word)
    if actual:
        segmentos.append(actual)
    return segmentos


def _right_label(
    rect: tuple[float, float, float, float],
    page_height: float,
    words: list[dict[str, float]],
) -> str:
    """Devuelve la etiqueta de opción situada a la derecha del campo.

    Las casillas de verificación suelen estar seguidas de la etiqueta de su
    opción (``Masculino``, ``Soltero``, ``Si``, ...) a la derecha del
    rectángulo. Se agrupan las palabras contiguas con solapamiento vertical y se
    devuelve el segmento más cercano al borde derecho del campo.
    """
    x0, y0, x1, y1 = rect
    top = page_height - max(y0, y1)
    bottom = page_height - min(y0, y1)
    field_height = max(bottom - top, 1.0)

    candidatos: list[tuple[float, dict[str, float]]] = []
    for word in words:
        wx0 = float(word["x0"])
        wt, wb = float(word["top"]), float(word["bottom"])
        if wx0 < x1 - 1.5:
            continue
        vertical = max(0.0, min(wb, bottom) - max(wt, top))
        if vertical >= 0.25 * field_height:
            candidatos.append((wx0 - x1, word))
    if not candidatos:
        return ""
    mejor = _best_segment(candidatos, x1)
    return mejor[1] if mejor else ""


def _best_segment(
    candidates: list[tuple[float, dict[str, float]]], field_x0: float
) -> tuple[float, str] | None:
    """Agrupa palabras contiguas y devuelve el segmento más cercano al campo."""
    if not candidates:
        return None
    lines: dict[float, list[tuple[float, dict[str, float]]]] = {}
    for gap, word in sorted(
        candidates, key=lambda item: (float(item[1]["top"]), float(item[1]["x0"]))
    ):
        top = float(word["top"])
        key = min(lines, key=lambda k: abs(k - top)) if lines else top
        if abs(key - top) > _LINE_TOLERANCE:
            key = top
        lines.setdefault(key, []).append((gap, word))

    best_score: float | None = None
    best_gap = 0.0
    best_text = ""
    for words_in_line in lines.values():
        ordered = sorted(words_in_line, key=lambda item: float(item[1]["x0"]))
        segments: list[list[tuple[float, dict[str, float]]]] = []
        current: list[tuple[float, dict[str, float]]] = []
        for item in ordered:
            if current and float(item[1]["x0"]) - float(current[-1][1]["x1"]) > _WORD_GAP:
                segments.append(current)
                current = []
            current.append(item)
        if current:
            segments.append(current)

        for segment in segments:
            seg_gap = min(gap for gap, _ in segment)
            seg_x0 = min(float(word["x0"]) for _, word in segment)
            distance = abs(seg_x0 - field_x0)
            score = seg_gap + 0.2 * distance
            if best_score is None or score < best_score:
                best_score = score
                best_gap = seg_gap
                best_text = " ".join(str(word["text"]) for _, word in segment)
    if best_score is None:
        return None
    return best_gap, best_text


def _best_left_block(
    candidates: list[tuple[float, dict[str, float]]],
    field_x0: float,
    field_top: float,
    field_bottom: float,
) -> tuple[float, str] | None:
    """Agrupa etiquetas de varias líneas situadas a la izquierda del campo."""
    if not candidates:
        return None
    words = sorted(
        (word for _, word in candidates),
        key=lambda w: (float(w["top"]), float(w["x0"])),
    )
    lineas: list[list[dict[str, float]]] = []
    for word in words:
        top = float(word["top"])
        if lineas and abs(float(lineas[-1][0]["top"]) - top) <= _LINE_TOLERANCE:
            lineas[-1].append(word)
        else:
            lineas.append([word])

    segmentos: list[list[dict[str, float]]] = []
    for linea in lineas:
        ordenadas = sorted(linea, key=lambda w: float(w["x0"]))
        actual: list[dict[str, float]] = []
        for word in ordenadas:
            if actual and float(word["x0"]) - float(actual[-1]["x1"]) > _WORD_GAP:
                segmentos.append(actual)
                actual = []
            actual.append(word)
        if actual:
            segmentos.append(actual)

    bloques: list[list[dict[str, float]]] = []
    for segmento in segmentos:
        colocado = False
        for bloque in bloques:
            bx0 = min(float(w["x0"]) for w in bloque)
            bx1 = max(float(w["x1"]) for w in bloque)
            sx0 = min(float(w["x0"]) for w in segmento)
            sx1 = max(float(w["x1"]) for w in segmento)
            overlap = max(0.0, min(sx1, bx1) - max(sx0, bx0))
            min_width = min(sx1 - sx0, bx1 - bx0)
            bloque_bottom = max(float(w["bottom"]) for w in bloque)
            segmento_top = min(float(w["top"]) for w in segmento)
            vertical_gap = max(0.0, segmento_top - bloque_bottom)
            if min_width > 0 and overlap / min_width >= 0.5 and vertical_gap <= 8.0:
                bloque.extend(segmento)
                colocado = True
                break
        if not colocado:
            bloques.append(list(segmento))

    best: tuple[float, str] | None = None
    for block in bloques:
        block_x1 = max(float(w["x1"]) for w in block)
        gap = field_x0 - block_x1
        if gap < 0:
            continue
        block_top = min(float(w["top"]) for w in block)
        block_bottom = max(float(w["bottom"]) for w in block)
        vertical_overlap = max(0.0, min(block_bottom, field_bottom) - max(block_top, field_top))
        text = " ".join(
            str(w["text"]) for w in sorted(block, key=lambda w: (float(w["top"]), float(w["x0"])))
        )
        score = gap - 0.5 * vertical_overlap
        if best is None or score < best[0]:
            best = (score, text)
    return best


__all__ = ["inspect_form"]
