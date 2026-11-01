#!/usr/bin/env bash
# Installs the `spiral` command on macOS (Apple Silicon). Safe to run again: it updates spiral
# and never overwrites your configuration.
#   curl -LsSf https://raw.githubusercontent.com/sbonacho/spiral/main/install.sh | bash
set -euo pipefail

SOURCE="${SPIRAL_INSTALL_SOURCE:-git+https://github.com/sbonacho/spiral}"
CONFIG_DIR="$HOME/.config/spiral"

if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
  echo "spiral only supports macOS on Apple Silicon for now (transcription uses MLX)." >&2
  echo "Nothing was installed." >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv (https://astral.sh/uv)..."
  curl -LsSf https://astral.sh/uv/install.sh | bash
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "Installing spiral..."
uv tool install --force "$SOURCE"
uv tool update-shell >/dev/null 2>&1 || true   # adds uv's tool bin dir to your shell profile if missing (idempotent)

# Older versions added an alias block to your shell profile; it would shadow the new command, so remove it.
for rc in "$HOME/.zshrc" "$HOME/.bash_profile" "$HOME/.bashrc"; do
  if [ -f "$rc" ] && grep -q '^# >>> spiral >>>$' "$rc" && grep -q '^# <<< spiral <<<$' "$rc"; then
    sed -i.bak '/^# >>> spiral >>>$/,/^# <<< spiral <<<$/d' "$rc" && rm -f "$rc.bak"
    echo "Removed the old spiral alias from $rc"
  fi
done

mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG_DIR/.env" ]; then
  cat > "$CONFIG_DIR/.env" <<'ENV'
# Global spiral settings. A .env in the directory where you run `spiral` overrides these, variable by variable.
# Empty values are ignored. Keep this file private: it can hold secrets.

# Summary provider: claude (default, needs the `claude` CLI), gemini or ollama
# LLM_PROVIDER=claude
# GEMINI_API_KEY=
# OLLAMA_MODEL=

# Archive.org keys (https://archive.org/account/s3.php) for the audio hosting
# IA_ACCESS_KEY=
# IA_SECRET_KEY=
ENV
  chmod 600 "$CONFIG_DIR/.env"
  echo "Created $CONFIG_DIR/.env"
fi

echo
missing=0
for tool in ffmpeg ffprobe; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Missing: $tool  ->  brew install ffmpeg"
    missing=1
  fi
done
[ "$missing" = 0 ] && echo "ffmpeg: ok"

echo
echo "Done. Open a new terminal and run:  spiral --version"
