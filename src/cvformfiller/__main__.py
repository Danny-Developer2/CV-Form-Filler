"""Punto de entrada para ``python -m cvformfiller``."""

from cvformfiller.cli import app


def main() -> None:
    """Ejecuta la interfaz de línea de comandos."""
    app()


if __name__ == "__main__":
    main()
