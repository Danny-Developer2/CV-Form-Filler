"""Genera el fixture anonimizado del CV con ReportLab.

El CV de prueba contiene exclusivamente datos ficticios (nombre, contacto,
empresas, instituciones y habilidades inventados) para que el repositorio pueda
publicarse sin exponer datos personales reales.

Uso:
    python tests/fixtures/generate_cv_fixture.py
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

DESTINO = Path(__file__).resolve().parent / "cv_juan_perez.pdf"

LINEAS = [
    "JUAN PEREZ LOPEZ | Curriculum Vitae",
    "Juan Perez Lopez",
    "Desarrollador de Software",
    "Ciudad Ficticia, N.L. | +52 81 0000 0000 | juan.perez@example.com | @juanperez",
    "DATOS PERSONALES",
    "Sexo: Masculino",
    "Estado Civil: Soltero",
    "Vive con: Solo",
    "Tiene licencia de manejo: Si",
    "¿Cómo supo de esta vacante?: Anuncio",
    "PERFIL",
    "Desarrollador de software con experiencia en backend, frontend y bases de datos.",
    "HABILIDADES",
    "Backend: Python, Java, SQL",
    "Frontend: HTML, CSS, JavaScript",
    "Bases de datos: MySQL, PostgreSQL",
    "Herramientas: Git, Docker, Linux",
    "EXPERIENCIA",
    "Desarrollador Backend | Empresa ABC | 2024 - 2026",
    "Automatización de procesos con Python",
    "Desarrollador Frontend | Empresa DEF | 2022 - 2023",
    "Desarrollo de aplicaciones web con JavaScript",
    "Desarrollador Junior | Empresa GHI | 2021 - 2022",
    "Soporte y mantenimiento de sistemas",
    "EDUCACIÓN",
    "Ingeniería Ficticia | Universidad Ficticia | 2018 - 2022",
    "Curso de Python | Instituto Ficticio | 2023 - 2024",
    "CERTIFICACIONES",
    "Scrum Fundamentals | Certificación Ficticia | 2023",
    "IDIOMAS",
    "Español: Nativo | Inglés: Intermedio",
    "PROYECTOS DESTACADOS",
    "github.com/juanperez | Proyecto Uno, Proyecto Dos",
    "Aplicaciones web con Python y JavaScript",
]


def main() -> None:
    """Escribe el PDF del CV anonimizado."""
    lienzo = canvas.Canvas(str(DESTINO), pagesize=letter)
    _, alto = letter
    y = alto - 50.0
    for linea in LINEAS:
        lienzo.drawString(50.0, y, linea)
        y -= 16.0
    lienzo.showPage()
    lienzo.save()
    print(f"CV anonimizado escrito en {DESTINO}")


if __name__ == "__main__":
    main()
