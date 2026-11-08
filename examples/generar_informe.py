"""Genera un informe JSON y un PDF de ejemplo a partir de los fixtures.

Uso:
    python examples/generar_informe.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cvformfiller.cv_parser import parse_cv  # noqa: E402
from cvformfiller.filler import fill_form  # noqa: E402
from cvformfiller.form_inspector import inspect_form  # noqa: E402
from cvformfiller.mapper import map_cv_to_form  # noqa: E402
from cvformfiller.verifier import verify_fill  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
REPORTS = ROOT / "reports"


def main() -> None:
    """Ejecuta el pipeline y escribe el informe de ejemplo."""
    REPORTS.mkdir(exist_ok=True)
    cv = parse_cv(FIXTURES / "cv_juan_perez.pdf")
    campos = inspect_form(FIXTURES / "formulario_empleo.pdf")
    mapping = map_cv_to_form(cv, campos)
    salida = REPORTS / "solicitud_rellenada.pdf"
    fill_form(FIXTURES / "formulario_empleo.pdf", campos, mapping.fields, salida)
    verificacion = verify_fill(salida, campos, mapping.fields)

    informe = {
        "candidato": cv.nombre,
        "campos_formulario": len(campos),
        "campos_rellenados": mapping.filled_count,
        "campos_faltantes": mapping.missing,
        "mapeo": [
            {
                "campo": item.field,
                "etiqueta": item.label,
                "valor": item.value,
                "origen": item.source,
            }
            for item in mapping.fields
        ],
        "verificacion": {
            "ok": verificacion.ok,
            "comprobaciones_pasadas": verificacion.checks_passed,
            "comprobaciones_fallidas": verificacion.checks_failed,
            "paginas_renderizadas": verificacion.rendered_pages,
        },
        "salida": str(salida.relative_to(ROOT)),
    }
    destino = REPORTS / "informe-ejemplo.json"
    destino.write_text(json.dumps(informe, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Informe escrito en {destino}")
    print(f"PDF rellenado en {salida}")


if __name__ == "__main__":
    main()
