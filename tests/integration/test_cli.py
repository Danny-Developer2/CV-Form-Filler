"""Pruebas de integración de la CLI."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader
from typer.testing import CliRunner

from cvformfiller.cli import app

runner = CliRunner()
CV = Path(__file__).resolve().parents[1] / "fixtures" / "cv_juan_perez.pdf"
FORM = Path(__file__).resolve().parents[1] / "fixtures" / "formulario_empleo.pdf"


def test_cli_fill(tmp_path: Path) -> None:
    salida = tmp_path / "salida.pdf"
    result = runner.invoke(
        app,
        ["--cv", str(CV), "--form", str(FORM), "--output", str(salida), "--font-size", "10"],
    )
    assert result.exit_code == 0, result.output
    assert salida.exists()
    campos = PdfReader(salida).get_fields() or {}
    assert str(campos["Text12"].get("/V")) == "Juan"
    assert str(campos["Text10"].get("/V")) == "Perez"
    assert str(campos["Text19"].get("/V")) == "+52 81 0000 0000"
    assert str(campos["Check Box20"].get("/V")) == "/Yes"
    assert str(campos["Check Box25"].get("/V")) == "/Yes"
    assert str(campos["Check Box35"].get("/V")) == "/Yes"
    assert str(campos["Check Box45"].get("/V")) == "/Yes"
    assert str(campos["Check Box181"].get("/V")) == "/Yes"
    assert campos["Check Box21"].get("/V") is None
    assert campos["Check Box44"].get("/V") is None


def test_cli_dry_run(tmp_path: Path) -> None:
    salida = tmp_path / "salida.pdf"
    result = runner.invoke(
        app,
        ["--cv", str(CV), "--form", str(FORM), "--output", str(salida), "--dry-run"],
    )
    assert result.exit_code == 0, result.output
    assert not salida.exists()
    assert "dry-run" in result.output


def test_cli_missing_options() -> None:
    result = runner.invoke(app, ["--cv", str(CV)])
    assert result.exit_code == 2


def test_cli_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "1.0.0" in result.output


def test_cli_bad_cv(tmp_path: Path) -> None:
    salida = tmp_path / "salida.pdf"
    result = runner.invoke(
        app,
        ["--cv", str(tmp_path / "no.pdf"), "--form", str(FORM), "--output", str(salida)],
    )
    assert result.exit_code == 1
