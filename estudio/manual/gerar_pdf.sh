#!/bin/bash
# Rebuilds ../web/manual.pdf from manual.html (needs node + playwright: npm i playwright && npx playwright install chromium).
cd "$(dirname "$0")" || exit 1
node gerar_pdf.js "$PWD" "$PWD/../web/manual.pdf" && ls -la ../web/manual.pdf
