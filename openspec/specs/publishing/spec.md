# publishing Specification

## Purpose
Definir cómo se publica un episodio procesado en varias redes y varias cuentas por red, cómo se registra lo publicado y qué garantías ofrece (idempotencia, simulación, logs y custodia de credenciales).

## Requirements

### Requirement: Destinos como red más cuenta
El sistema SHALL modelar cada lugar de publicación como un destino `red/cuenta`. Un episodio SHALL poder publicarse en N destinos y cada red SHALL admitir N cuentas. Las redes soportadas son `youtube`, `bluesky`, `mastodon`, `instagram`, `x` y `tiktok`, y el destino especial `site` (audio, blog y RSS), que es único por directorio.

#### Scenario: Dos cuentas de la misma red
- **WHEN** hay configuradas `bluesky/programa` y `bluesky/personal`
- **THEN** ambas aparecen como destinos distintos y se pueden publicar por separado o a la vez

### Requirement: Cuentas definidas en el .env
El sistema SHALL leer las cuentas de cada red de `<RED>_ACCOUNTS` (lista separada por comas) y, por cada cuenta, de variables `<RED>_<CUENTA>_<CAMPO>` (nombres en mayúsculas). Los campos obligatorios SHALL ser: `bluesky` → `HANDLE`, `APP_PASSWORD`; `mastodon` → `URL`, `TOKEN`; `instagram` → `USER_ID` y `TOKEN` o un token ya guardado; `youtube` → ninguno (usa `CLIENT_SECRET`, ruta opcional que por defecto es `~/.config/spiral/client_secret.json`); `x` y `tiktok` → ninguno (son manuales). El destino `site` SHALL usar `IA_ACCESS_KEY` e `IA_SECRET_KEY` (o la configuración de `ia`) y los metadatos de `PODCAST_*` y `SITE_URL`. Un destino está **configurado** solo si tiene todos sus campos obligatorios.

#### Scenario: Cuenta completa
- **WHEN** `BLUESKY_ACCOUNTS=programa` y existen `BLUESKY_PROGRAMA_HANDLE` y `BLUESKY_PROGRAMA_APP_PASSWORD`
- **THEN** `bluesky/programa` figura como configurado

#### Scenario: Cuenta incompleta
- **WHEN** falta `BLUESKY_PROGRAMA_APP_PASSWORD`
- **THEN** `bluesky/programa` figura como no configurado y el motivo nombra esa variable

#### Scenario: Cuenta añadida solo en local
- **WHEN** el `.env` global define `MASTODON_ACCOUNTS=a` y el local define `MASTODON_ACCOUNTS=a,b` con las variables de `b`
- **THEN** se ofrecen `mastodon/a` y `mastodon/b`

### Requirement: Selección múltiple de destinos configurados
El sistema SHALL ofrecer, tras elegir un episodio procesado, todos los destinos conocidos y SHALL permitir marcar varios, pero MUST NOT permitir marcar los no configurados, que SHALL mostrarse indicando lo que les falta. Un episodio pendiente MUST NOT poder publicarse.

#### Scenario: Destino no configurado
- **WHEN** `youtube/canal` no tiene credenciales
- **THEN** aparece deshabilitado con el motivo y no se puede marcar

#### Scenario: Episodio pendiente
- **WHEN** el usuario intenta publicar un episodio pendiente
- **THEN** el sistema indica que debe procesarse primero

### Requirement: Estado de publicación por destino
El sistema SHALL registrar en `published/<nombre>/` el estado de cada destino (hecho, fecha, identificador o URL devuelta) y SHALL usarlo para no repetir una publicación ya hecha. Un fallo en un destino MUST NOT impedir intentar los demás ni borrar lo ya registrado, y el resultado final SHALL indicar qué destinos fueron bien y cuáles fallaron.

#### Scenario: Repetir una publicación
- **WHEN** `bluesky/programa` ya figura como publicado y el usuario lo selecciona de nuevo
- **THEN** el sistema lo omite e indica que ya estaba publicado

#### Scenario: Publicación parcial
- **WHEN** se seleccionan `youtube/canal` y `bluesky/programa` y el primero falla
- **THEN** `bluesky/programa` se publica y se registra, `youtube/canal` queda sin registrar y el sistema termina con código de salida distinto de cero

### Requirement: Simulación
El sistema SHALL ofrecer un modo de simulación que muestre el contenido que se enviaría a cada destino sin contactar con ninguna red y sin modificar el estado de publicación.

#### Scenario: Simular
- **WHEN** el usuario publica en modo simulación en `bluesky/programa`
- **THEN** se muestra el texto y no se realiza ninguna petición ni se modifica `published/`

### Requirement: Registro de publicaciones
El sistema SHALL añadir a `published/<nombre>/publish.log` cada intento, con fecha, destino y resultado. Los registros MUST NOT contener contraseñas, tokens ni claves.

#### Scenario: El log no filtra secretos
- **WHEN** se publica en un destino con token
- **THEN** `publish.log` no contiene el valor del token

### Requirement: Custodia de tokens
Los tokens generados por el sistema (OAuth de YouTube, token renovado de Instagram) SHALL guardarse en `~/.config/spiral/tokens/<red>-<cuenta>.json` con permisos de solo lectura y escritura para el usuario. El sistema MUST NOT escribirlos en el directorio de trabajo, en `published/` ni en los logs.

#### Scenario: Primer login de YouTube
- **WHEN** el usuario autoriza `youtube/canal`
- **THEN** el token queda en `~/.config/spiral/tokens/youtube-canal.json` con permisos 600

### Requirement: Destinos manuales
Para `x` y `tiktok` el sistema SHALL preparar el contenido (enlaces de publicación para X, carpeta de clips para TikTok) y SHALL preguntar al usuario si ya lo ha publicado; solo si confirma, SHALL registrar el destino como publicado de forma manual.

#### Scenario: Confirmación manual
- **WHEN** el usuario confirma que publicó en `x/programa`
- **THEN** `published/<nombre>/` lo registra como publicado manualmente

### Requirement: Sitio de audio, blog y RSS
El destino `site` SHALL subir el mp3 a Archive.org, generar la entrada de blog y regenerar `feed.xml` en `site/` dentro del directorio de trabajo, y SHALL, si `site/` es un repositorio git y el usuario lo confirma, hacer commit y push. Los destinos que enlazan al post del blog o necesitan una URL pública para los clips MUST NOT intentarse en la misma ejecución si `site` fue seleccionado y falló.

#### Scenario: Falla el sitio
- **WHEN** se seleccionan `site` y `bluesky/programa` y `site` falla
- **THEN** no se intenta `bluesky/programa` y se explica el motivo

#### Scenario: site/ no es un repositorio
- **WHEN** `site/` no es un repositorio git
- **THEN** el sistema genera los ficheros, no hace push e indica cómo publicarlos

### Requirement: Volver a publicar
`spiral publish --force` SHALL volver a ejecutar los destinos que ya constan como publicados. En el menú, si entre los destinos elegidos hay alguno ya publicado, el sistema SHALL preguntar (por defecto no) si volver a publicar, avisando de que en las redes se repiten los posts y vídeos; sin confirmación SHALL omitirlos. Con `--yes` sin `--force` los ya publicados SHALL omitirse sin preguntar.

#### Scenario: Forzar con la bandera
- **WHEN** `site` consta como publicado y se ejecuta `spiral publish a --to site --force`
- **THEN** `site` se ejecuta de nuevo y su estado queda como publicado

#### Scenario: Sin forzar
- **WHEN** `site` consta como publicado y se ejecuta `spiral publish a --to site --yes`
- **THEN** `site` se omite

### Requirement: Retirar publicaciones
`spiral unpublish <nombre>... --from <destino>[,...] [--dry-run] [--yes]` SHALL retirar los episodios de los destinos indicados. Bluesky y Mastodon SHALL borrar el post; `site` SHALL quitar la entrada, el post del blog y el elemento del feed, y subir el cambio si se confirma; el mp3 de Archive.org SHALL NOT borrarse. Los destinos sin borrado automático (YouTube, Instagram, X, TikTok) SHALL indicar que se borre a mano y solo pasar a no publicados si el usuario lo confirma. Un destino pasa a no publicado únicamente si el borrado tuvo éxito, y SHALL poder volver a publicarse. Sin `--yes` ni `--dry-run`, el sistema SHALL pedir confirmación antes de borrar (por defecto no); `--dry-run` MUST NOT modificar nada.

#### Scenario: Retirar del sitio
- **WHEN** `site` consta como publicado y se ejecuta `spiral unpublish a --from site --yes`
- **THEN** el feed deja de incluir el episodio, su entrada y su post desaparecen y `site` queda como no publicado

#### Scenario: Destino manual sin confirmar
- **WHEN** se retira de `x/programa` y el usuario no confirma que lo ha borrado
- **THEN** `x/programa` sigue constando como publicado

### Requirement: Escaparate del sitio
Tras publicar o retirar con éxito en algún destino, el sistema SHALL actualizar `site/`: cada post de episodio SHALL mostrar una insignia con el logo de cada red externa en la que consta publicado (enlazada cuando el enlace público se pueda deducir) y SHALL generarse una página `/publicaciones.html` con todos los episodios y sus insignias. Si `PODCAST_IMAGE` está definido, SHALL usarse como logo del sitio. Los estilos SHALL generarse en `_sass/spiral.scss` y `assets/main.scss` SHALL crearse solo si no existe. Un fallo al actualizar el escaparate MUST NOT cambiar el resultado de la publicación, y el cambio SHALL subirse a GitHub solo si se confirma.

#### Scenario: Publicar en una red
- **WHEN** un episodio ya está en `site` y se publica en `bluesky/programa`
- **THEN** su post y `/publicaciones.html` muestran la insignia de Bluesky enlazada al post

#### Scenario: Retirar de una red
- **WHEN** se retira el episodio de `bluesky/programa`
- **THEN** la insignia de Bluesky desaparece de su post y de `/publicaciones.html`
