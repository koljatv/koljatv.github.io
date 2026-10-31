#!/bin/bash
# Prepara o Estúdio KÖLJA TV neste Mac (uma vez): o desenhista das vinhetas e o ícone na Mesa.
cd "$(dirname "$0")/.." || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
PY=$(for p in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do [ -x "$p" ] && echo "$p" && break; done)
SUP="$HOME/Library/Application Support/Estudio KOLJA TV"
echo "== Estúdio KÖLJA TV: instalação =="
command -v ffmpeg >/dev/null || echo "ATENÇÃO: falta o ffmpeg (o conversor de vídeo). Instale com: brew install ffmpeg"
if ! "$PY" estudio/midia_check.py >/dev/null 2>&1; then
  echo "Preparando o desenhista das vinhetas (precisa de internet só agora)..."
  mkdir -p "$SUP" && "$PY" -m venv "$SUP/venv" && "$SUP/venv/bin/pip" install -q pillow numpy && echo "ok"
fi
"$PY" estudio/criar_app.py && echo "Pronto: o ícone 'Estúdio KÖLJA TV' está na sua Mesa (Desktop)."
read -n 1 -s -r -p "Aperte qualquer tecla para fechar."
