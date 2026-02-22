#!/bin/sh
# Instala o hook presente em scripts/git-hooks/pre-commit para .git/hooks/pre-commit

set -e

HOOK_SRC="$(pwd)/scripts/git-hooks/pre-commit"
HOOK_DST="$(pwd)/.git/hooks/pre-commit"

if [ ! -d .git ]; then
  echo "Parece que este diretório não é um repositório git (.git não encontrado)." >&2
  exit 1
fi

if [ ! -f "$HOOK_SRC" ]; then
  echo "Arquivo de hook não encontrado em $HOOK_SRC" >&2
  exit 1
fi

mkdir -p "$(dirname "$HOOK_DST")"
cp "$HOOK_SRC" "$HOOK_DST"
chmod +x "$HOOK_DST"

echo "Hook instalado em .git/hooks/pre-commit"
echo "Ele vai rodar 'pre-commit' e re-stagear automaticamente alterações geradas pelos hooks."
