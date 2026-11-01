#!/usr/bin/env bash
# Instala el comando `spiral`: añade un alias al rc de tu shell y prepara .env.
#   ./install.sh              instalar (se puede repetir)
#   ./install.sh --uninstall  quitar el alias
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BEGIN="# >>> spiral >>>"
END="# <<< spiral <<<"

case "$(basename "${SHELL:-}")" in
  zsh)  RC="$HOME/.zshrc" ;;
  bash) RC="$HOME/.bash_profile"; [ -f "$HOME/.bashrc" ] && [ ! -f "$RC" ] && RC="$HOME/.bashrc" ;;
  *)    echo "Shell no soportado (${SHELL:-desconocido}): añade a mano  alias spiral='$DIR/spiral'" >&2; exit 1 ;;
esac

remove_block() {
  [ -f "$RC" ] && sed -i.bak "/^$BEGIN\$/,/^$END\$/d" "$RC" && rm -f "$RC.bak"
  return 0
}

if [ "${1:-}" = "--uninstall" ]; then
  remove_block
  echo "Alias quitado de $RC. (El proyecto y tu .env siguen en $DIR.)"
  exit 0
fi

chmod +x "$DIR/spiral" "$DIR/engine.py"

remove_block
{
  echo "$BEGIN"
  echo "alias spiral='$DIR/spiral'"
  echo "$END"
} >> "$RC"

if [ ! -f "$DIR/.env" ]; then
  cp "$DIR/.env.example" "$DIR/.env"
  chmod 600 "$DIR/.env"
  echo "Creado $DIR/.env: edítalo (SOURCE_DIR, ARCHIVE_DIR y las claves)."
fi

echo
echo "Comprobando requisitos:"
missing=0
for cmd in python3 ffmpeg ffprobe uv claude git; do
  if command -v "$cmd" >/dev/null 2>&1; then echo "  ✔ $cmd"; else echo "  ✘ $cmd (falta)"; missing=1; fi
done
[ "$missing" = 1 ] && echo "  Instala lo que falta antes de procesar (README, sección 2)."

echo
echo "Instalado: alias 'spiral' en $RC"
echo "Abre una terminal nueva, o ejecuta:  source $RC"
