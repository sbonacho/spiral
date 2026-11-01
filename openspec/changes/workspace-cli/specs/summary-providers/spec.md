## Purpose

Definir qué motores generan el resumen y el contenido derivado de cada episodio, y cómo se elige el idioma de la transcripción y del texto generado, para que la herramienta sirva a quien no tenga Claude Code.

## ADDED Requirements

### Requirement: Proveedor de resumen seleccionable
El sistema SHALL generar el resumen y el contenido estructurado con el proveedor indicado en `LLM_PROVIDER`: `claude` (CLI de Claude Code instalada, valor por defecto), `gemini` (requiere `GEMINI_API_KEY`) u `ollama` (requiere `OLLAMA_MODEL`, con `OLLAMA_URL` opcional y por defecto `http://localhost:11434`). Un valor desconocido SHALL producir un error que liste los valores admitidos.

#### Scenario: Ollama local
- **WHEN** `LLM_PROVIDER=ollama` y `OLLAMA_MODEL` está definido
- **THEN** el resumen se genera sin enviar la transcripción fuera de la máquina

#### Scenario: Proveedor sin configurar
- **WHEN** `LLM_PROVIDER=gemini` y falta `GEMINI_API_KEY`
- **THEN** el procesado se detiene antes de llamar al proveedor y nombra la variable que falta

#### Scenario: Valor desconocido
- **WHEN** `LLM_PROVIDER=otro`
- **THEN** el sistema lista `claude`, `gemini` y `ollama` como valores válidos

### Requirement: Contenido estructurado y validado
El resultado de cualquier proveedor SHALL ser el mismo objeto estructurado (título, resumen corto y largo, capítulos, etiquetas, hilo para X, entrada de blog y clips con tiempos). El sistema MUST validar su estructura antes de escribirlo y MUST NOT escribir `contenido.json` si la respuesta es inválida.

#### Scenario: Respuesta inválida
- **WHEN** el proveedor devuelve un JSON sin el campo `clips`
- **THEN** no se escribe `contenido.json` y el error indica el campo ausente

### Requirement: Conservar lo ya generado ante un fallo del proveedor
Si el proveedor de resumen falla o no está disponible, el sistema SHALL conservar la transcripción ya generada para que un reintento repita solo el resumen.

#### Scenario: Reintento tras fallo
- **WHEN** el resumen falla y el usuario vuelve a procesar el episodio
- **THEN** no se vuelve a transcribir

### Requirement: Idioma del programa
El sistema SHALL transcribir y generar el contenido en el idioma indicado por `PODCAST_LANGUAGE` (por defecto `es`).

#### Scenario: Programa en inglés
- **WHEN** `PODCAST_LANGUAGE=en`
- **THEN** la transcripción se hace en inglés y el contenido generado está en inglés

### Requirement: Transparencia sobre el destino de la transcripción
El sistema SHALL indicar el proveedor activo antes de enviarle la transcripción.

#### Scenario: Aviso del proveedor
- **WHEN** se inicia el resumen con `LLM_PROVIDER=gemini`
- **THEN** la salida indica que la transcripción se enviará a Gemini
