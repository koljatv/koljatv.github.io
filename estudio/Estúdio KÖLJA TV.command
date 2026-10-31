#!/bin/bash
# Abre o Estúdio KÖLJA TV (dois cliques). A janela do Terminal pode ficar aberta ou ser fechada depois que o navegador abrir.
cd "$(dirname "$0")/.." || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
PY=$(for p in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do [ -x "$p" ] && echo "$p" && break; done)
mkdir -p "$HOME/Library/Logs"
nohup "$PY" estudio/estudio.py >> "$HOME/Library/Logs/Estudio KOLJA TV.log" 2>&1 &
sleep 1
echo "Estúdio KÖLJA TV aberto no navegador (http://127.0.0.1:8799). Pode fechar esta janela."
