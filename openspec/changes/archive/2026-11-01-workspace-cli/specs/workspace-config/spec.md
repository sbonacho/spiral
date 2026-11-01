## Purpose

Define cómo `spiral` descubre el directorio sobre el que trabaja y cómo combina la configuración global y la local, para que cada directorio de grabaciones sea un programa independiente.

## ADDED Requirements

### Requirement: El directorio de trabajo es el directorio actual
El sistema SHALL tratar el directorio desde el que se ejecuta `spiral` como su directorio de trabajo y SHALL buscar ahí los `.mov` de entrada. El sistema MUST NOT requerir ni aceptar una variable de configuración que apunte a otro directorio de grabaciones, y MUST NOT buscar `.mov` en subdirectorios.

#### Scenario: Se listan los .mov del directorio actual
- **WHEN** el usuario ejecuta `spiral list` en un directorio con `a.mov` y `b.mov`
- **THEN** el sistema muestra `a` y `b`

#### Scenario: No se recorren subdirectorios
- **WHEN** existe `sub/c.mov` y el usuario ejecuta `spiral list` en el directorio padre
- **THEN** `c` no aparece como episodio pendiente

### Requirement: Configuración en capas
El sistema SHALL cargar la configuración, variable a variable, con esta precedencia de mayor a menor: variables de entorno del proceso, `.env` del directorio de trabajo, `~/.config/spiral/.env`. Un valor vacío SHALL tratarse como no definido y MUST NOT sobrescribir un valor de una capa inferior.

#### Scenario: Lo local sobrescribe a lo global
- **WHEN** `~/.config/spiral/.env` define `LLM_PROVIDER=claude` y el `.env` local define `LLM_PROVIDER=ollama`
- **THEN** el valor efectivo es `ollama`

#### Scenario: Una variable solo global se conserva
- **WHEN** `IA_ACCESS_KEY` solo existe en el `.env` global
- **THEN** el valor efectivo es el del `.env` global

#### Scenario: Un valor vacío no pisa al global
- **WHEN** el `.env` local contiene `BLUESKY_PROGRAMA_HANDLE=` y el global define un valor
- **THEN** el valor efectivo es el del global

#### Scenario: El entorno del proceso manda
- **WHEN** `LLM_PROVIDER=gemini` está exportado en la shell y el `.env` local define `ollama`
- **THEN** el valor efectivo es `gemini`

### Requirement: Ausencia de configuración
El sistema SHALL poder listar y procesar episodios sin ningún fichero `.env`. La falta de configuración de una red SHALL afectar únicamente a la publicación en esa red.

#### Scenario: Sin .env se puede listar
- **WHEN** no existe ningún `.env` y el usuario ejecuta `spiral list`
- **THEN** el sistema lista los episodios sin error

### Requirement: Carpetas de resultados configurables dentro del directorio
El sistema SHALL guardar los episodios procesados en la carpeta indicada por `PROCESSED_DIR` (por defecto `processed`) y el estado de publicación en la indicada por `PUBLISHED_DIR` (por defecto `published`), ambas relativas al directorio de trabajo. El sistema MUST rechazar rutas absolutas o que salgan del directorio de trabajo mediante `..`.

#### Scenario: Valores por defecto
- **WHEN** no se define `PROCESSED_DIR`
- **THEN** los episodios procesados se guardan en `processed/` del directorio actual

#### Scenario: Nombre personalizado
- **WHEN** `PROCESSED_DIR=listos`
- **THEN** los episodios procesados se guardan en `listos/`

#### Scenario: Ruta que sale del directorio
- **WHEN** `PROCESSED_DIR=../fuera` o `PROCESSED_DIR=/tmp/x`
- **THEN** el sistema termina con un error que nombra la variable y no crea ninguna carpeta

### Requirement: Metadatos del podcast en la configuración
El sistema SHALL tomar los metadatos del programa de las variables `PODCAST_TITLE`, `PODCAST_DESCRIPTION`, `PODCAST_AUTHOR`, `PODCAST_EMAIL`, `PODCAST_LANGUAGE` (por defecto `es`), `PODCAST_CATEGORY`, `PODCAST_IMAGE` (opcional) y `SITE_URL`. La publicación en el sitio MUST NOT ejecutarse mientras falte alguna obligatoria, y el error SHALL nombrar las que faltan.

#### Scenario: Falta una variable obligatoria
- **WHEN** falta `SITE_URL` y el usuario intenta publicar en el sitio
- **THEN** el sistema se detiene antes de subir nada e indica que falta `SITE_URL`

### Requirement: Intro y outro opcionales con respaldo global
El sistema SHALL buscar `intro.mov` y `outro.mov` primero en el directorio de trabajo y, si no existen, en `~/.config/spiral/`. El fichero local MUST prevalecer sobre el global. Si una pieza no existe en ningún sitio, el sistema SHALL omitirla sin error. `intro.mov` y `outro.mov` MUST NOT tratarse como episodios.

#### Scenario: Solo hay intro global
- **WHEN** existe `~/.config/spiral/intro.mov` y no hay ficheros locales de intro ni outro
- **THEN** el episodio procesado lleva la intro global y no lleva outro

#### Scenario: La intro local gana
- **WHEN** existen `intro.mov` local y global
- **THEN** se usa la local

#### Scenario: Intro y outro no son episodios
- **WHEN** el directorio contiene `intro.mov`, `outro.mov` y `a.mov`
- **THEN** `spiral list` muestra solo `a`
