"""Genera ejemplos JSON del CV normalizado y de los campos del formulario.

Uso:
    python examples/generar_ejemplos.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cvformfiller.cv_parser import parse_cv  # noqa: E402
from cvformfiller.form_inspector import inspect_form  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
EXAMPLES = ROOT / "examples"


def main() -> None:
    """Escribe los ejemplos JSON."""
    EXAMPLES.mkdir(exist_ok=True)
    cv = parse_cv(FIXTURES / "cv_juan_perez.pdf")
    campos = inspect_form(FIXTURES / "formulario_empleo.pdf")

    cv_json = EXAMPLES / "cv-ejemplo.json"
    cv_json.write_text(
        json.dumps(cv.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    campos_json = EXAMPLES / "campos-ejemplo.json"
    campos_json.write_text(
        json.dumps(
            [campo.model_dump(mode="json") for campo in campos],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"CV normalizado: {cv_json}")
    print(f"Campos del formulario: {campos_json}")


if __name__ == "__main__":
    main()
