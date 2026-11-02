# interactive-cli Specification

## Purpose
Definir la experiencia de uso del comando `spiral`: selectores con flechas y espacio, panel de estado de las redes, y un modo no interactivo equivalente para automatizar y probar.

## Requirements

### Requirement: Panel inicial de redes y acciones
Al ejecutarse sin argumentos, el sistema SHALL mostrar el estado de cada destino configurable (configurado o no, y qué le falta) y SHALL ofrecer las acciones `list`, `process`, `publish`, `unpublish` y `view`. El estado MUST NOT transmitirse solo mediante el color: SHALL usar también símbolos o texto.

#### Scenario: Panel con redes sin configurar
- **WHEN** el usuario ejecuta `spiral` y `youtube/canal` no tiene credenciales
- **THEN** el panel muestra `youtube/canal` como no configurado con el motivo

### Requirement: Navegación con flechas
Los menús de una sola opción SHALL poder recorrerse con las flechas arriba/abajo y confirmarse con Enter.

#### Scenario: Elegir una acción
- **WHEN** el usuario baja con la flecha hasta `process` y pulsa Enter
- **THEN** se inicia `process`

### Requirement: Selector de episodios con búsqueda
El selector de episodios SHALL mostrar todos los ficheros con su estado y SHALL filtrar la lista a medida que el usuario escribe.

#### Scenario: Filtrado al escribir
- **WHEN** el usuario escribe parte de un nombre
- **THEN** la lista se reduce a las coincidencias y se elige con flechas y Enter

### Requirement: Selección múltiple con espacio
Los selectores de episodios (`process`, `publish`) y de destinos SHALL permitir marcar y desmarcar varias opciones con la barra espaciadora y confirmar con Enter. Las opciones no disponibles SHALL mostrarse deshabilitadas, con el motivo, y no ser marcables.

Los selectores SHALL ofrecer una tecla para marcar o desmarcar todas las opciones disponibles (Ctrl-A en el de episodios, que además filtra al escribir; `a` en el de destinos).

#### Scenario: Marcar todos los episodios
- **WHEN** el usuario pulsa Ctrl-A en el selector de episodios y Enter
- **THEN** quedan marcados todos los episodios elegibles y ninguno de los no elegibles

#### Scenario: Marcar varios destinos
- **WHEN** el usuario pulsa espacio sobre `bluesky/programa` y `mastodon/programa` y Enter
- **THEN** se publica solo en esos dos destinos

### Requirement: Varios episodios en una acción
`process` y `publish` SHALL aceptar varios episodios. `process` SHALL continuar con los demás si uno falla, mostrar cuántos se procesaron y terminar con código 1 si alguno falló; `--redo` y su confirmación SHALL aplicarse a todos los ya procesados. `publish` SHALL comprobar antes de publicar que todos están procesados, pedir destinos y modo una sola vez, y publicar cada episodio con su propio resultado; las confirmaciones manuales (x, tiktok) SHALL pedirse por cada episodio.

#### Scenario: Un fallo no detiene el resto
- **WHEN** se procesan a, b y c y b falla
- **THEN** a y c se procesan, se informa del fallo de b y el código de salida es 1

#### Scenario: Un episodio sin procesar bloquea todo
- **WHEN** se publica a y b y b no está procesado
- **THEN** no se publica ninguno y se explica cómo procesar b

### Requirement: Cancelación segura
Pulsar Ctrl-C durante una selección SHALL cancelar la acción sin modificar ficheros y volver al menú, o terminar con código 130 si se ejecutó una acción directa.

#### Scenario: Cancelar un selector
- **WHEN** el usuario pulsa Ctrl-C en el selector de destinos
- **THEN** no se publica nada y no se modifica ningún fichero

### Requirement: Uso no interactivo
Cada acción SHALL poder ejecutarse con argumentos explícitos: `spiral process <nombre>...`, `spiral publish <nombre>... --to <red/cuenta>[,...] [--dry-run] [--yes]`, `spiral list` y `spiral view`. Si la entrada no es un terminal y faltan argumentos, el sistema MUST terminar con un error de uso y código 2 sin esperar entrada. `spiral --version` SHALL mostrar la versión.

#### Scenario: Publicar sin terminal
- **WHEN** se ejecuta `spiral publish a --to bluesky/programa --yes` sin terminal
- **THEN** se publica en ese destino sin hacer preguntas

#### Scenario: Faltan argumentos sin terminal
- **WHEN** se ejecuta `spiral publish` sin terminal
- **THEN** termina con código 2 y un mensaje de uso

### Requirement: Progreso visible
Las operaciones largas (transcripción, codificación, subidas) SHALL mostrar un indicador de progreso o actividad.

#### Scenario: Subida de un vídeo
- **WHEN** se sube un vídeo a YouTube
- **THEN** la salida muestra el avance de la subida

### Requirement: Idioma de la interfaz
El sistema SHALL mostrar los mensajes, la ayuda, las preguntas, las etiquetas, los errores y el informe HTML en el idioma indicado por `PODCAST_LANGUAGE` cuando sea español (`es`) o inglés (`en`), ignorando la región (por ejemplo `en-US`), y en inglés para cualquier otro idioma. Si `PODCAST_LANGUAGE` no está definida, el sistema SHALL usar español. El idioma de la interfaz MUST NOT depender de ninguna otra variable de configuración.

#### Scenario: Sin PODCAST_LANGUAGE
- **WHEN** `PODCAST_LANGUAGE` no está definida y el usuario ejecuta `spiral --help`
- **THEN** la ayuda se muestra en español

#### Scenario: Programa en inglés
- **WHEN** `PODCAST_LANGUAGE=en` y el usuario ejecuta `spiral list`
- **THEN** los encabezados, estados y mensajes se muestran en inglés

#### Scenario: Idioma sin traducción
- **WHEN** `PODCAST_LANGUAGE=fr`
- **THEN** la interfaz se muestra en inglés

#### Scenario: Variante regional
- **WHEN** `PODCAST_LANGUAGE=es-MX`
- **THEN** la interfaz se muestra en español

#### Scenario: Informe en el idioma elegido
- **WHEN** `PODCAST_LANGUAGE=en` y el usuario ejecuta `spiral view`
- **THEN** el informe HTML está en inglés y su etiqueta `lang` es `en`
