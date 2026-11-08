"""Interfaz de línea de comandos de CV-Form-Filler (Typer + Rich)."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table
from rich.text import Text

from cvformfiller import __version__
from cvformfiller.cv_parser import parse_cv
from cvformfiller.exceptions import CvFormFillerError
from cvformfiller.filler import fill_form
from cvformfiller.form_inspector import inspect_form
from cvformfiller.mapper import map_cv_to_form
from cvformfiller.models import CvData, FillReport, FormField, MappingResult
from cvformfiller.utils.logger import setup_logger
from cvformfiller.verifier import verify_fill

app = typer.Typer(
    name="cv-form-filler",
    help=(
        "CV-Form-Filler — rellena automáticamente formularios PDF de solicitud "
        "de empleo a partir de un CV."
    ),
    add_completion=False,
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)

AVISO_PRIVACIDAD = (
    "[yellow]AVISO:[/yellow] los datos personales del CV se procesan localmente y "
    "no se registran en los logs."
)

_PASOS = [
    "Leyendo el CV",
    "Inspeccionando el formulario",
    "Mapeando los campos",
    "Rellenando el PDF",
    "Verificando la salida",
]


@app.callback(invoke_without_command=True)
def run(
    ctx: typer.Context,
    cv: Path | None = typer.Option(None, "--cv", "-c", help="CV en PDF o DOCX."),
    form: Path | None = typer.Option(
        None, "--form", "-f", help="Formulario PDF con campos AcroForm."
    ),
    output: Path | None = typer.Option(None, "--output", "-o", help="PDF de salida."),
    font_size: float = typer.Option(
        10.0, "--font-size", help="Tamaño de fuente uniforme para los campos de texto (pt)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Solo muestra el mapeo sin escribir el PDF."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Registro detallado."),
    log_file: Path | None = typer.Option(None, "--log-file", help="Volcar el registro a fichero."),
) -> None:
    """Rellena un formulario de empleo a partir del CV proporcionado."""
    if ctx.invoked_subcommand is not None:
        return
    if cv is None or form is None or output is None:
        err_console.print("[red]Error:[/red] son obligatorios --cv, --form y --output.")
        raise typer.Exit(code=2)

    setup_logger("DEBUG" if verbose else "INFO", log_file)
    _print_banner()
    console.print(AVISO_PRIVACIDAD)

    try:
        cv_data, campos, mapping, report = _run(cv, form, output, font_size, dry_run)
    except CvFormFillerError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except KeyboardInterrupt:  # pragma: no cover - interrupción manual
        err_console.print("\n[yellow]Ejecución interrumpida por el usuario.[/yellow]")
        raise typer.Exit(code=130) from None

    _print_summary(cv_data.nombre, campos, mapping, report)
    if not dry_run:
        console.print(f"[green]PDF guardado en:[/green] {report.output}")
        if report.errors:
            for error in report.errors[:10]:
                err_console.print(f"[red]· {escape(error)}[/red]")


def _run(
    cv: Path,
    form: Path,
    output: Path,
    font_size: float,
    dry_run: bool,
) -> tuple[CvData, list[FormField], MappingResult, FillReport]:
    """Ejecuta el pipeline completo con barra de progreso."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Procesando", total=len(_PASOS))

        progress.update(task, description=_PASOS[0])
        cv_data = parse_cv(cv)
        progress.advance(task)

        progress.update(task, description=_PASOS[1])
        campos = inspect_form(form)
        progress.advance(task)

        progress.update(task, description=_PASOS[2])
        mapping = map_cv_to_form(cv_data, campos)
        progress.advance(task)

        progress.update(task, description=_PASOS[3])
        report = fill_form(
            form,
            campos,
            mapping.fields,
            output,
            font_size=font_size,
            dry_run=dry_run,
            missing_fields=mapping.missing,
        )
        progress.advance(task)

        progress.update(task, description=_PASOS[4])
        if not dry_run:
            verificacion = verify_fill(output, campos, mapping.fields)
            report = FillReport(
                output=report.output,
                total_fields=report.total_fields,
                fields_filled=report.fields_filled,
                fields_missing=report.fields_missing,
                missing_fields=report.missing_fields,
                font_size=report.font_size,
                dry_run=report.dry_run,
                checks_passed=verificacion.checks_passed,
                checks_failed=verificacion.checks_failed,
                errors=verificacion.errors,
                duration_seconds=report.duration_seconds,
            )
        progress.advance(task)

    return cv_data, campos, mapping, report


def _print_banner() -> None:
    """Muestra el banner de la herramienta."""
    banner = Panel.fit(
        "[bold cyan]CV-Form-Filler[/bold cyan] "
        f"v{__version__}\n"
        "[white]Relleno automático de formularios PDF de empleo[/white]\n"
        "[yellow]Procesa datos personales localmente y con confidencialidad.[/yellow]",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(banner)


def _print_summary(
    nombre: str,
    campos: list[FormField],
    mapping: MappingResult,
    report: FillReport,
) -> None:
    """Muestra el informe de campos rellenados y faltantes."""
    console.print(f"\n[bold]CV-Form-Filler[/bold] — candidato: {escape(nombre or '—')}")
    console.print(
        f"Campos del formulario: {len(campos)} · Rellenados: {report.fields_filled} · "
        f"Faltantes: {report.fields_missing} · Fuente: {report.font_size:g} pt"
    )

    if mapping.fields:
        tabla = Table(title="Campos rellenados")
        tabla.add_column("Campo", style="cyan")
        tabla.add_column("Etiqueta")
        tabla.add_column("Valor")
        tabla.add_column("Origen", style="dim")
        for item in mapping.fields:
            tabla.add_row(
                Text(item.field),
                Text(item.label or "—"),
                Text(item.value),
                Text(item.source),
            )
        console.print(tabla)

    if report.missing_fields:
        faltantes = report.missing_fields
        mostrados = ", ".join(escape(name) for name in faltantes[:15])
        if len(faltantes) > 15:
            mostrados += f" y {len(faltantes) - 15} más"
        console.print(
            f"\n[yellow]Campos sin datos en el CV ({len(faltantes)}):[/yellow] {mostrados}"
        )

    if report.dry_run:
        console.print("\n[blue]Modo dry-run: no se escribió ningún PDF.[/blue]")
    elif report.checks_failed:
        console.print(
            f"\n[red]Verificación fallida:[/red] {report.checks_failed} comprobaciones "
            f"no superadas."
        )
    else:
        console.print(
            f"\n[green]Verificación correcta:[/green] {report.checks_passed} comprobaciones "
            f"superadas."
        )


@app.command()
def version() -> None:
    """Muestra la versión de CV-Form-Filler."""
    console.print(f"CV-Form-Filler {__version__}")


def main() -> None:
    """Punto de entrada de la CLI."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
