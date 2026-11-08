# Idea planteada: CV-Form-Filler

## Problema

Millones de solicitudes de empleo siguen llegando en formato PDF con campos
AcroForm que el candidato debe rellenar a mano o con un editor genérico. El
proceso es repetitivo, lento y propenso a errores: copiar a mano el nombre, los
apellidos, el teléfono, el domicilio, la experiencia y la escolaridad de un CV a
un formulario puede llevar varios minutos por solicitud.

Además, los formularios reales no siguen un estándar: las etiquetas están
encima, debajo o al lado de los campos; hay tablas con columnas repetidas
(experiencia anterior, escolaridad); y los nombres de campo son genéricos
(`Text1`, `Check Box20`, …), por lo que el valor no describe el significado del
campo.

## Propuesta

Una herramienta de línea de comandos que, a partir de un CV (PDF o DOCX) y un
formulario de solicitud en PDF, genera una copia del formulario con los campos
rellenados automáticamente:

```bash
python main.py --cv CV.pdf --form FORMULARIO.pdf --output salida.pdf
```

La herramienta:

1. **Extrae y normaliza** el CV en un modelo de datos tipado e inmutable.
2. **Inspecciona** los campos AcroForm del formulario y localiza sus etiquetas
   por proximidad geométrica (incluida la etiqueta de opción a la derecha de las
   casillas).
3. **Mapea** los datos del CV a los campos con heurísticas de normalización,
   similitud de texto y posición/orden.
4. **Rellena** una copia del formulario con tamaño de fuente uniforme y marca las
   casillas cuya opción coincide con el valor del CV con estado `/Yes`.
5. **Verifica** el resultado leyendo los valores `/V` y renderizando el PDF.

## Alcance

### Incluido

- CV en PDF (con capa de texto) y DOCX.
- Formularios PDF con campos AcroForm de texto y casillas.
- Etiquetas localizadas por proximidad (encima, a la izquierda o debajo) y
  etiqueta de opción a la derecha de las casillas.
- Casillas rellenadas por coincidencia con la opción: sexo, estado civil,
  vive con, licencia y cómo supo.
- Tablas repetidas: experiencia laboral y escolaridad.
- Modo `--dry-run` para revisar el mapeo sin escribir el PDF.
- Tamaño de fuente uniforme configurable (`--font-size`).
- Informe de campos rellenados y campos faltantes.
- Verificación del PDF generado.
- Fixture de CV anonimizado generado con ReportLab para publicar el repositorio
  sin datos personales reales.

### Fuera de alcance

- Firmas digitales.
- Envío del formulario por correo o a plataformas de empleo.
- Extracción de datos de formularios escaneados sin capa de texto (OCR).
- Traducción del CV a otros idiomas.
- Modificación del formulario original: la herramienta siempre escribe una copia.

## Valor

- **Ahorro de tiempo**: el rellenado pasa de minutos a segundos.
- **Menos errores**: los datos se copian del CV sin transcripción manual.
- **Trazabilidad**: el informe muestra qué campos se rellenaron y cuáles quedaron
  vacíos por falta de datos.
- **Confidencialidad**: los datos personales se procesan en local y no se
  registran.

## Privacidad y tratamiento de datos

El CV contiene datos personales (nombre, contacto, dirección, CURP, RFC, NSS).
La herramienta:

- Procesa todo en local; no envía datos a servicios externos.
- No escribe valores del CV en los logs: solo nombres de campo y contadores.
- No sobrescribe el formulario original.
- Genera una copia que el usuario controla y puede eliminar.

## Métricas de éxito

- Cobertura de pruebas ≥ 80 %.
- `mypy --strict` sin errores.
- `ruff check` y `ruff format --check` sin errores.
- Verificación del PDF generado sin errores en el formulario de prueba.
- Campos rellenados correctamente en el CV de prueba: nombre, apellidos,
  teléfono, domicilio, experiencia y escolaridad.
- Campos sin datos en el CV (CURP, RFC, NSS, fecha de nacimiento, nacionalidad)
  quedan vacíos y aparecen en el informe de faltantes.
