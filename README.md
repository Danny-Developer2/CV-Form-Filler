# CV-Form-Filler

[![Python >= 3.11](https://img.shields.io/badge/python-%3E%3D3.11-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**CV-Form-Filler** is a Python command-line tool that fills employment application
PDF forms from a CV. It parses the CV (PDF or DOCX), inspects the AcroForm fields
of the application form, maps the CV data onto the form fields with label
normalisation, text similarity and geometric position heuristics, and writes a
filled copy of the form without ever overwriting the original.

The tool handles personal data confidentially: data is processed locally and is
never written to logs.

## Features

- Parses a CV from **PDF** (pdfplumber) or **DOCX** (stdlib `zipfile`).
- Normalises the CV into a typed, immutable model: name, surnames, contact,
  birth date, address, city, nationality, CURP, RFC, NSS, work experience,
  education, languages, skills, software and checkbox concepts (sex, marital
  status, living arrangement, driving licence and how the vacancy was found).
- Inspects **AcroForm** fields with `pypdf`: name, type, rectangle and page.
- Finds the printed label of each field by **geometric proximity** (above, left
  or below), grouping contiguous words into multi-word labels. For checkboxes it
  also captures the full line above (`line_label`) and the option label to the
  right (`right_label`).
- Maps CV concepts to form fields using label normalisation (case, accents and
  punctuation), text similarity and table position/order.
- Fills **checkboxes** with the `/Yes` state when the option label next to the
  box matches the CV value (`Sexo` + `Masculino`, `Estado Civil` + `Soltero`,
  `Vive con` + `Solo`, `Tiene licencia` + `Si`, `Anuncio` for `¿Cómo supo?`).
- Fills text fields with a **uniform font size** (10 pt by default) and
  regenerates the appearance streams.
- Verifies the result with `pypdf` (`/V` values) and renders it with
  **pypdfium2** to confirm that every value was drawn in the correct field.
- Rich CLI with banner, progress bar, filled/missing field report and `--dry-run`
  mode.

## Requirements

- Python >= 3.11
- Dependencies: `pypdf`, `pdfplumber`, `pypdfium2`, `pydantic`, `typer`, `rich`,
  `Jinja2`.

## Installation

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

## Usage

```bash
cv-form-filler --cv CV.pdf --form FORMULARIO.pdf --output salida.pdf
```

or, from the project root:

```bash
python main.py --cv CV.pdf --form FORMULARIO.pdf --output salida.pdf
```

Useful options:

| Option | Description |
| --- | --- |
| `--font-size N` | Uniform font size for text fields (default `10`). |
| `--dry-run` | Only show the mapping; no PDF is written. |
| `--verbose` / `-v` | Detailed logging. |
| `--log-file PATH` | Also write the log to a file. |

Example:

```bash
python main.py --cv tests/fixtures/cv_juan_perez.pdf \
  --form tests/fixtures/formulario_empleo.pdf \
  --output reports/solicitud_rellenada.pdf \
  --font-size 10
```

## How it works

```
CV (PDF/DOCX) ──► cv_parser ──► CvData ─┐
                                       ├──► mapper ──► MappingResult ──► filler ──► PDF
Form (PDF) ────► form_inspector ───────┘                                            │
                                                                                    ▼
                                                                            verifier ──► OK/KO
```

1. **cv_parser**: extracts the text and normalises it into a `CvData` model.
2. **form_inspector**: reads the AcroForm fields and finds their labels by
   proximity, producing `FormField` objects with `label`, `row_label`,
   `column_label`, `line_label` and `right_label`.
3. **mapper**: matches CV concepts to fields with normalised similarity and
   positional table logic; fills checkboxes whose option label matches the CV
   value; fields without data are reported as missing.
4. **filler**: writes a copy of the form with `/V` values and regenerated
   appearances at a uniform font size.
5. **verifier**: reads back `/V` with `pypdf` and renders with `pypdfium2` to
   confirm the values are in the right fields.

## Privacy

The tool processes personal data locally. Logs contain only field names, counters
and technical paths; CV values are never logged. The output PDF is written next to
the path supplied by the user and the original form is never modified.

## Development

```bash
make install    # editable install with dev dependencies
make test       # pytest
make coverage   # pytest with coverage report
make lint       # ruff check
make format     # ruff format
make types      # mypy --strict
make check      # lint + format + types + tests
```

The test suite includes integration tests that run the tool against the fixtures
in `tests/fixtures/` (an anonymized CV generated with ReportLab and a real
employment application form). The CV fixture can be regenerated with:

```bash
python tests/fixtures/generate_cv_fixture.py
```

## Documentation

Full documentation is available in `docs/`:

| Document | Contents |
| --- | --- |
| [PROJECT_PROPOSAL.pdf](docs/PROJECT_PROPOSAL.pdf) | Problem, objectives, scope, architecture, technologies, plan and deliverables. |
| [TECHNICAL_DOCUMENTATION.pdf](docs/TECHNICAL_DOCUMENTATION.pdf) | Internal architecture, modules, models, mapping engine, flows and error handling. |
| [USER_MANUAL.pdf](docs/USER_MANUAL.pdf) | Requirements, installation, configuration, commands, real examples and troubleshooting. |
| [QA_TEST_REPORT.pdf](docs/QA_TEST_REPORT.pdf) | Test cases, real results (64/64, 92% coverage) and final status. |
| [PRIVACY_AND_SECURITY_NOTES.pdf](docs/PRIVACY_AND_SECURITY_NOTES.pdf) | Personal data handling, confidentiality, best practices and legal warnings. |

## License

MIT — see [LICENSE](LICENSE).

---

## Sección en español

**CV-Form-Filler** es una herramienta de línea de comandos que rellena
automáticamente formularios PDF de solicitud de empleo a partir de un CV.

### Uso rápido

```bash
python main.py --cv CV.pdf --form FORMULARIO.pdf --output salida.pdf
```

### Qué hace

1. Extrae y normaliza el CV (PDF o DOCX): nombre, apellidos, contacto, fecha de
   nacimiento, domicilio, ciudad, nacionalidad, CURP, RFC, NSS, experiencia,
   educación, idiomas, habilidades, software y conceptos de casillas (sexo,
   estado civil, vive con, licencia y cómo supo).
2. Inspecciona los campos AcroForm del formulario y localiza sus etiquetas por
   proximidad geométrica.
3. Mapea los datos del CV a los campos con heurísticas de normalización,
   similitud de texto y posición. Los campos sin datos quedan vacíos y se
   informan.
4. Rellena una copia del formulario con tamaño de fuente uniforme (10 pt por
   defecto) y marca las casillas cuyo valor coincide con la opción (`Sexo` +
   `Masculino`, `Estado Civil` + `Soltero`, `Vive con` + `Solo`, `Tiene
   licencia` + `Si`, `Anuncio` para `¿Cómo supo?`) con estado `/Yes`, sin
   sobrescribir el original.
5. Verifica el resultado con `pypdf` y renderiza el PDF con `pypdfium2`.

### Privacidad

Los datos personales se procesan localmente y no se registran en los logs.

### Desarrollo

```bash
make install   # instalación editable con dependencias de desarrollo
make test      # pruebas
make coverage  # pruebas con informe de cobertura
make lint      # ruff check
make types     # mypy --strict
make check     # lint + format + types + tests
```
