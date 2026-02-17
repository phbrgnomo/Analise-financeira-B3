#!/usr/bin/env bash
set -euo pipefail

# Sincroniza arquivos de stories em docs/implementation-artifacts
# com issues no GitHub usando o `gh` CLI.

REPO="phbrgnomo/Analise-financeira-B3"
DIR="docs/implementation-artifacts"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI não encontrado. Autentique e instale gh antes de executar." >&2
  exit 1
fi

echo "Iniciando sincronização de issues para $DIR -> $REPO"

for f in "$DIR"/*.md; do
  [ -e "$f" ] || continue
  echo "\nProcessando: $f"

  # extrai título: primeira linha com #, ou filename sem extensão
  title=$(grep -m1 '^#' "$f" || true)
  if [ -n "$title" ]; then
    # remove leading # e espaços
    title=${title#\#}
    title=$(echo "$title" | sed 's/^\s*//;s/\s*$//')
  else
    title=$(basename "$f" .md)
  fi

  echo "Título: $title"

  # procurar issue existente com título exato (compatível com gh sem --json)
  issue_number=""
  list_out=$(gh issue list --repo "$REPO" --search "$title" --limit 200 --state all 2>/dev/null || true)
  if [ -n "$list_out" ]; then
    while IFS= read -r line; do
      # linhas tipicamente: "#19  Title..." ou "19\tTitle"
      num=$(echo "$line" | sed -E 's/^#?([0-9]+).*/\1/')
      title_text=$(echo "$line" | sed -E 's/^#?[0-9]+[[:space:]]+//')
      if [ "$title_text" = "$title" ]; then
        issue_number=$num
        break
      fi
    done <<< "$list_out"
  fi

  if [ -z "$issue_number" ]; then
    echo "Issue não encontrada — criando..."
    # cria issue com body vindo do arquivo
    gh issue create --repo "$REPO" --title "$title" --body-file "$f"
    # recuperar número buscando novamente
    list_out2=$(gh issue list --repo "$REPO" --search "$title" --limit 200 --state all 2>/dev/null || true)
    if [ -n "$list_out2" ]; then
      issue_number=$(echo "$list_out2" | sed -n '1p' | sed -E 's/^#?([0-9]+).*/\1/')
    fi
    issue_url="https://github.com/$REPO/issues/$issue_number"
    echo "Criada: $issue_url (#$issue_number)"
  else
    echo "Issue encontrada: #$issue_number — atualizando corpo..."
    gh issue edit "$issue_number" --repo "$REPO" --body-file "$f"
    issue_url="https://github.com/$REPO/issues/$issue_number"
    echo "Atualizada: $issue_url (#$issue_number)"
  fi

  # inserir ou atualizar linha Issue: <url> no final do arquivo
  if grep -qE '^Issue:\s*https?://' "$f"; then
    # substituir primeira ocorrência
    sed -i "0,/^Issue:\s*https?:\/\//s|^Issue:.*|Issue: $issue_url|" "$f"
    echo "Link da issue atualizado no arquivo."
  else
    printf "\nIssue: %s\n" "$issue_url" >> "$f"
    echo "Link da issue adicionado ao final do arquivo."
  fi
done

echo "Sincronização concluída."
