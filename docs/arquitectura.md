# Arquitectura de CV-Form-Filler

## Visión general

CV-Form-Filler es una herramienta de línea de comandos organizada en torno a una
pipeline de cinco etapas: **parseo del CV**, **inspección del formulario**,
**mapeo**, **rellenado** y **verificación**. Cada etapa es un módulo
independiente con una responsabilidad única y se comunica con las siguientes
mediante modelos de datos inmutables.

```
┌────────────┐   ┌────────────────┐   ┌──────────┐   ┌─────────┐   ┌────────────┐
│ cv_parser  │──►│ form_inspector │──►│  mapper  │──►│ filler  │──►│  verifier  │
└────────────┘   └────────────────┘   └──────────┘   └─────────┘   └────────────┘
      │                   │                 │              │              │
      ▼                   ▼                 ▼              ▼              ▼
   CvData            FormField[]      MappingResult   FillReport   VerificationReport
```

## Estructura del proyecto

```
08-CV-Form-Filler/
├── main.py                      # punto de entrada python main.py
├── pyproject.toml               # dependencias, ruff, mypy, pytest
├── Makefile                     # install, test, coverage, lint, format, types, check
├── src/cvformfiller/
│   ├── __init__.py              # versión y metadatos
│   ├── __main__.py              # python -m cvformfiller
│   ├── cli.py                   # CLI Typer + Rich
│   ├── models.py                # modelos Pydantic inmutables
│   ├── exceptions.py            # jerarquía de excepciones
│   ├── cv_parser.py             # CV PDF/DOCX → CvData
│   ├── form_inspector.py        # PDF → FormField[]
│   ├── mapper.py                # CvData + FormField[] → MappingResult
│   ├── filler.py                # MappingResult → PDF
│   ├── verifier.py              # PDF → VerificationReport
│   └── utils/logger.py          # logging sin datos personales
├── tests/
│   ├── conftest.py              # fixtures de sesión
│   ├── fixtures/                # CV anonimizado y formulario real de prueba
│   ├── unit/                    # pruebas unitarias por módulo
│   └── integration/             # pruebas de la CLI
├── docs/                        # idea.md, arquitectura.md
├── examples/                    # ejemplos de uso
└── reports/                     # salidas generadas
```

## Modelos de datos

Todos los modelos son inmutables (`ConfigDict(frozen=True)`) para garantizar que
los datos no se modifiquen una vez construidos.

| Modelo | Descripción |
| --- | --- |
| `FieldType` | `StrEnum`: `TEXT`, `CHECKBOX`, `RADIO`, `UNKNOWN`. |
| `Contacto` | Teléfono, correo y presencia web. |
| `Experience` | Puesto, empresa, periodo y descripción. |
| `Education` | Título, institución, periodo y grado. |
| `CvData` | CV normalizado: datos personales (incluye sexo, estado civil, vive con, licencia y cómo supo), experiencia, educación, idiomas, habilidades y software. |
| `FormField` | Campo del formulario: nombre, tipo, rectángulo, página, etiqueta, fila, columna, línea completa, etiqueta de opción a la derecha y confianza. |
| `MappedField` | Campo con el valor asignado y su origen. |
| `MappingResult` | Lista de campos mapeados, campos faltantes y totales. |
| `FillReport` | Informe del rellenado: totales, faltantes, fuente y verificación. |
| `VerificationReport` | Resultado de la verificación: OK/KO, comprobaciones y errores. |

## Módulos

### cv_parser.py

- `parse_cv(path)` elige el extractor según la extensión.
- PDF: `pdfplumber` extrae el texto con coordenadas.
- DOCX: se lee `word/document.xml` con `zipfile` y `xml.etree` (sin dependencias
  adicionales).
- El texto se agrupa por secciones (`PERFIL`, `EXPERIENCIA`, `EDUCACIÓN`,
  `IDIOMAS`, `HABILIDADES`) y se normaliza en `CvData`.
- Heurísticas: nombre/apellidos (últimas dos palabras como apellidos), teléfono
  (descartando rangos de años), ciudad/estado, CURP/RFC/NSS/fecha de nacimiento
  por patrones, experiencia por líneas con `|` y año, educación por nivel.

### form_inspector.py

- Lee el diccionario `/AcroForm` con `pypdf` y recorre `/Fields`.
- Para cada campo registra nombre, tipo (`/FT`, `/Ff` para radio), rectángulo y
  página.
- Extrae las palabras del PDF con `pdfplumber` y busca la etiqueta más cercana:
  - **encima** o **debajo**: palabras con solape horizontal y distancia vertical
    mínima, agrupadas por línea y contigüidad.
  - **a la izquierda**: etiquetas de varias líneas (por ejemplo
    "Nombre de la Compañía") agrupadas por proximidad vertical.
- Además calcula:
  - `line_label`: la línea completa más cercana por encima o debajo, sin exigir
    solape horizontal (la etiqueta conceptual de una casilla puede ocupar varias
    palabras y quedar parcialmente fuera del rectángulo).
  - `right_label`: la etiqueta de opción situada a la derecha del campo
    (`Masculino`, `Soltero`, `Si`, ...), agrupando las palabras contiguas con
    solape vertical.
- Devuelve `FormField` con `label`, `row_label`, `column_label`, `line_label` y
  `right_label`.

### mapper.py

- Normaliza etiquetas (minúsculas, sin acentos, sin puntuación).
- Calcula similitud con los alias de cada concepto del CV.
- Asigna conceptos simples de forma voraz por similitud y posición (los campos
  más altos de la página ganan los empates).
- Tablas repetidas:
  - **Experiencia**: campos de empresa, puesto y periodo (`de`/`a`) ordenados por
    posición X.
  - **Escolaridad**: filas por nivel (primaria, secundaria, preparatoria,
    profesional, comercial) y columnas por etiqueta o posición.
  - **Estudios actuales**: escuela y carrera del estudio más reciente.
- **Casillas de verificación**: por cada regla (`sexo`, `estado_civil`,
  `vive_con`, `licencia`, `como_supo`) localiza las casillas cuya etiqueta
  conceptual coincide con el concepto y comprueba la etiqueta de la opción
  situada a la derecha del campo. Cuando el valor del CV coincide con la opción
  (`Sexo` + `Masculino`, `Estado Civil` + `Soltero`, `Vive con` + `Solo`,
  `Tiene licencia` + `Si`, `Anuncio` para `¿Cómo supo?`), marca la casilla con el
  estado `/Yes`. Solo se marca la primera casilla que coincide; las demás quedan
  sin marcar.
- Los campos sin datos se registran en `missing`.

### filler.py

- Lee el formulario con `pypdf` y lo clona en un `PdfWriter`.
- Actualiza los valores `/V` y regenera las apariciones con
  `update_page_form_field_values`, usando una tupla `(valor, "/Helv", font_size)`
  para forzar el tamaño uniforme.
- Las casillas usan el estado `/Yes`.
- Escribe una copia; nunca sobrescribe el original.

### verifier.py

- Lee el PDF de salida con `pypdf` y comprueba que cada `/V` coincide con el valor
  mapeado (texto) o con `/Yes` (casillas).
- Renderiza el PDF con `pypdfium2` (`init_forms()` para que las apariciones se
  dibujen) y comprueba que la región de cada campo rellenado contiene píxeles
  oscuros, es decir, que el valor se dibujó en el lugar correcto.

### cli.py

- Un `Typer` con un `callback` principal para que las opciones funcionen
  directamente (`python main.py --cv ... --form ... --output ...`).
- Banner `Rich`, aviso de privacidad, barra de progreso y tabla de campos
  rellenados/faltantes.
- Modo `--dry-run` que solo muestra el mapeo.
- Código de salida: `0` éxito, `1` error, `2` opciones incompletas, `130`
  interrupción.

## Flujo de datos

1. `parse_cv` → `CvData`.
2. `inspect_form` → `list[FormField]`.
3. `map_cv_to_form` → `MappingResult`.
4. `fill_form` → `FillReport` y PDF de salida.
5. `verify_fill` → `VerificationReport`.

## Pruebas

- **Unitarias**: modelos, parser, inspector, mapper, filler y verifier.
- **Integración**: la CLI completa contra los fixtures.
- Fixtures: el CV de prueba es un CV anonimizado generado con ReportLab
  (`tests/fixtures/generate_cv_fixture.py`) y el formulario es una solicitud de
  empleo real con campos AcroForm.
- Cobertura ≥ 80 % (actual: ~93 %).

## Seguridad y privacidad

- No se registraron datos personales en los logs: solo nombres de campo,
  contadores y rutas técnicas.
- El formulario original nunca se modifica.
- No hay llamadas de red.
- Las excepciones no exponen valores del CV.
