# episode-lifecycle Specification

## Purpose
Definir las etapas por las que pasa cada episodio (pendiente, procesado, publicado), cómo se deducen de las carpetas del directorio de trabajo y qué hacen los comandos de listado, procesado e informe.

## Requirements

### Requirement: El estado de un episodio se deduce de las carpetas
El sistema SHALL determinar el estado de cada episodio únicamente a partir del sistema de ficheros del directorio de trabajo: es **pendiente** si existe `<nombre>.mov` en el directorio y no hay carpeta de procesado completa; **procesado** si existe `processed/<nombre>/` con su marca de finalización; **publicado en un destino** si `published/<nombre>/` registra ese destino como hecho. El sistema MUST NOT depender de una base de datos ni de ficheros fuera del directorio de trabajo para saberlo.

#### Scenario: Un .mov nuevo es pendiente
- **WHEN** hay `a.mov` en el directorio y no existe `processed/a/`
- **THEN** `a` figura como pendiente

#### Scenario: Un episodio procesado sigue apareciendo aunque su .mov ya no esté en el directorio
- **WHEN** `processed/a/` está completa y `a.mov` ya no está en el directorio raíz
- **THEN** `a` figura como procesado

#### Scenario: Carpeta de procesado incompleta
- **WHEN** `processed/a/` existe pero no tiene la marca de finalización
- **THEN** `a` NO figura como procesado

### Requirement: Listado completo con estado y destinos
El sistema SHALL mostrar, con `spiral list`, todos los episodios conocidos (pendientes, procesados y publicados), cada uno con su estado y, si lo tiene, los destinos donde ya está publicado.

#### Scenario: Lista mixta
- **WHEN** hay un pendiente, un procesado sin publicar y un procesado publicado en `bluesky/programa`
- **THEN** la lista muestra los tres, distingue su estado y el último muestra `bluesky/programa`

### Requirement: Procesado de un episodio
El sistema SHALL procesar un episodio pendiente generando en `processed/<nombre>/`: el vídeo final (intro + programa + outro, solo las piezas existentes) con el audio normalizado, el audio mp3, la transcripción (`.txt`, `.srt`, `.json`), el resumen y contenido estructurado (`contenido.json`) y los clips verticales. Al terminar con éxito, el sistema SHALL mover el `.mov` original a `processed/<nombre>/` y escribir la marca de finalización. El sistema MUST NOT retirar el original del directorio raíz mientras el procesado no haya terminado con éxito.

#### Scenario: Procesado correcto
- **WHEN** el usuario procesa `a` pendiente
- **THEN** existe `processed/a/` con todos los ficheros de salida y el original `a.mov`, y `a.mov` ya no está en el directorio raíz

#### Scenario: Fallo durante el procesado
- **WHEN** falla un paso (por ejemplo el resumen)
- **THEN** `a.mov` sigue en el directorio raíz, `a` sigue sin figurar como procesado y el sistema indica el paso fallido

#### Scenario: Sin intro ni outro
- **WHEN** no existen `intro.mov` ni `outro.mov` en ningún sitio
- **THEN** el vídeo final contiene solo el programa

### Requirement: Selección de un episodio por búsqueda
El sistema SHALL permitir elegir el episodio a procesar entre todos los ficheros del directorio, buscando por texto en el nombre o en el título.

#### Scenario: Filtrar por texto
- **WHEN** el usuario escribe `antenas` en el selector
- **THEN** solo se ofrecen los episodios cuyo nombre o título contiene `antenas`

### Requirement: No sobrescribir resultados existentes
El sistema MUST NOT sobrescribir `processed/<nombre>/` si ya existe. Si el directorio raíz contiene `<nombre>.mov` y ya existe `processed/<nombre>/`, el sistema SHALL detenerse y explicar el conflicto.

#### Scenario: Conflicto de nombre
- **WHEN** existen `a.mov` en el directorio raíz y `processed/a/`
- **THEN** el sistema no procesa `a`, no modifica nada y explica cómo resolverlo

### Requirement: Reprocesado de un episodio procesado
El sistema SHALL permitir reprocesar un episodio ya procesado a partir del original guardado en `processed/<nombre>/`, pidiendo confirmación porque se pierden las ediciones manuales de `contenido.json`. El reprocesado MUST conservar el estado de publicación en `published/<nombre>/`.

#### Scenario: Reprocesar confirmado
- **WHEN** el usuario confirma reprocesar `a`
- **THEN** los ficheros generados se regeneran desde `processed/a/a.mov` y `published/a/` no cambia

#### Scenario: Reprocesar rechazado
- **WHEN** el usuario no confirma
- **THEN** no se modifica ningún fichero

### Requirement: Sin archivado
El sistema MUST NOT ofrecer ningún comando ni opción de archivado ni leer una variable `ARCHIVE_DIR`. El estado de un episodio SHALL expresarse solo mediante pendiente, procesado y publicado.

#### Scenario: No existe el comando archive
- **WHEN** el usuario ejecuta `spiral --help`
- **THEN** la ayuda no incluye `archive`

### Requirement: Informe HTML
El sistema SHALL generar con `spiral view` un informe HTML con todos los episodios (pendientes, procesados y publicados), su estado y, por cada destino configurado, si el episodio está publicado o no, y SHALL abrirlo en el navegador. Los episodios publicados SHALL distinguirse visualmente de los demás con un icono y el estado MUST NOT transmitirse solo por el color. El informe MUST escapar el contenido procedente de los títulos.

#### Scenario: Informe con estados
- **WHEN** hay un pendiente, un procesado y un publicado, y el usuario ejecuta `spiral view`
- **THEN** el informe contiene una fila por episodio y una columna por destino configurado, y el publicado lleva el icono de publicado

#### Scenario: Título con HTML
- **WHEN** un título contiene `<script>`
- **THEN** el informe lo muestra como texto y no lo interpreta
