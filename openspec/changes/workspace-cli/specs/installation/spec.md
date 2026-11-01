## Purpose

Definir cómo se instala, actualiza y documenta `spiral` para que cualquier usuario de un Mac pueda tenerlo funcionando con una sola línea.

## ADDED Requirements

### Requirement: Instalación con una línea
El README SHALL abrir con un único comando que instala `spiral` en un Mac. Ese comando SHALL instalar `uv` si no está presente, instalar `spiral` como herramienta global de Python desde el repositorio de GitHub y dejar el comando `spiral` disponible en el PATH. El instalador MUST NOT requerir `sudo`.

#### Scenario: Instalación en un Mac limpio
- **WHEN** el usuario ejecuta la línea del README en un Mac con Apple Silicon sin `uv`
- **THEN** `uv` y `spiral` quedan instalados y, en una terminal nueva, `spiral --version` funciona

### Requirement: Plataforma soportada
El instalador SHALL verificar que el sistema es macOS con Apple Silicon y, en otro caso, MUST terminar sin instalar nada y explicar el motivo.

#### Scenario: Mac Intel
- **WHEN** se ejecuta el instalador en un Mac Intel
- **THEN** termina con un mensaje que indica que no está soportado y no modifica el sistema

### Requirement: PATH del shell
Si el directorio de binarios de las herramientas de `uv` no está en el PATH, el instalador SHALL añadirlo al fichero de arranque del shell actual (zsh o bash) y MUST NOT duplicar la línea al repetirse.

#### Scenario: Repetir el instalador
- **WHEN** el instalador se ejecuta dos veces
- **THEN** el fichero de arranque contiene la configuración del PATH una sola vez

### Requirement: Configuración global inicial
El instalador SHALL crear `~/.config/spiral/.env` a partir de una plantilla comentada si no existe y MUST NOT sobrescribirlo si ya existe.

#### Scenario: Reinstalación
- **WHEN** ya existe `~/.config/spiral/.env` con claves del usuario
- **THEN** el instalador no lo modifica

### Requirement: Actualización
Volver a ejecutar la línea de instalación SHALL actualizar `spiral` a la última versión del repositorio sin perder la configuración del usuario.

#### Scenario: Actualizar
- **WHEN** hay una versión nueva en GitHub y el usuario repite la línea
- **THEN** `spiral --version` muestra la versión nueva y `~/.config/spiral/` no cambia

### Requirement: Comprobación de requisitos externos
El instalador SHALL informar de los requisitos externos que falten (como `ffmpeg`) con la orden para instalarlos, sin instalarlos por su cuenta.

#### Scenario: Falta ffmpeg
- **WHEN** `ffmpeg` no está instalado
- **THEN** el instalador lo indica y muestra `brew install ffmpeg`

### Requirement: Documentación pública
El repositorio SHALL incluir `README.md` en inglés, cuya primera sección tras el título es el comando de instalación de una línea, y `README.es.md` en español, enlazados entre sí. El README SHALL documentar la configuración en capas, el ciclo de vida de los episodios, el alta de cada red y los límites conocidos. El repositorio SHALL incluir un `LICENSE` MIT y MUST NOT contener credenciales, datos personales ni el contenido de un `.env`.

#### Scenario: Primera pantalla del README
- **WHEN** un visitante abre el README del repositorio
- **THEN** ve, antes de cualquier otra sección, el comando de instalación de una línea

#### Scenario: Sin secretos en el repositorio
- **WHEN** se revisa el repositorio a publicar
- **THEN** no hay ficheros `.env` ni tokens, y `.gitignore` los excluye
