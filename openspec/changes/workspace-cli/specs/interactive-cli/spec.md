## Purpose

Definir la experiencia de uso del comando `spiral`: selectores con flechas y espacio, panel de estado de las redes, y un modo no interactivo equivalente para automatizar y probar.

## ADDED Requirements

### Requirement: Panel inicial de redes y acciones
Al ejecutarse sin argumentos, el sistema SHALL mostrar el estado de cada destino configurable (configurado o no, y qué le falta) y SHALL ofrecer las acciones `list`, `process`, `publish` y `view`. El estado MUST NOT transmitirse solo mediante el color: SHALL usar también símbolos o texto.

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
El selector de destinos SHALL permitir marcar y desmarcar varias opciones con la barra espaciadora y confirmar con Enter. Las opciones no disponibles SHALL mostrarse deshabilitadas, con el motivo, y no ser marcables.

#### Scenario: Marcar varios destinos
- **WHEN** el usuario pulsa espacio sobre `bluesky/programa` y `mastodon/programa` y Enter
- **THEN** se publica solo en esos dos destinos

### Requirement: Cancelación segura
Pulsar Ctrl-C durante una selección SHALL cancelar la acción sin modificar ficheros y volver al menú, o terminar con código 130 si se ejecutó una acción directa.

#### Scenario: Cancelar un selector
- **WHEN** el usuario pulsa Ctrl-C en el selector de destinos
- **THEN** no se publica nada y no se modifica ningún fichero

### Requirement: Uso no interactivo
Cada acción SHALL poder ejecutarse con argumentos explícitos: `spiral process <nombre>`, `spiral publish <nombre> --to <red/cuenta>[,...] [--dry-run] [--yes]`, `spiral list` y `spiral view`. Si la entrada no es un terminal y faltan argumentos, el sistema MUST terminar con un error de uso y código 2 sin esperar entrada. `spiral --version` SHALL mostrar la versión.

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
