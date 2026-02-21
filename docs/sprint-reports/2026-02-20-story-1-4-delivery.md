---
title: Sprint report — Story 1.4 delivery (Salvar raw + Metadados)
date: 2026-02-20
story: 1-4
---

Resumo

Esta entrega implementa a persistência das respostas brutas dos provedores em CSV (`raw/<provider>/`) com checksum SHA256 e registro de metadados de ingestão em `metadata/ingest_logs.json`.

O que foi implementado

- Função `save_raw_csv` em `src/ingest/pipeline.py`:
  - grava CSV atômico sem índice (`index=False`)
  - calcula e grava checksum SHA256 em `*.checksum`
  - persiste metadados em `metadata/ingest_logs.json` de forma atômica
  - opção `set_permissions=True` para aplicar `chmod 600` em sistemas POSIX
- Testes adicionados/atualizados:
  - `tests/test_save_raw.py` — valida escrita, checksum e gravação de metadados
  - `tests/test_save_raw_permissions.py` — teste POSIX para `set_permissions` (pulável no Windows)
- Documentação:
  - `README.md` atualizado com notas operacionais sobre raw files e metadados
  - `docs/playbooks/quickstart-ticker.md` atualizado com paths e verificações para raw + metadados
- Resultado dos testes:
  - `pytest` local: 45 passed

Arquivos alterados/criados

- src/ingest/pipeline.py (modificado)
- tests/test_save_raw.py (modificado)
- tests/test_save_raw_permissions.py (novo)
- README.md (modificado)
- docs/playbooks/quickstart-ticker.md (modificado)
- docs/implementation-artifacts/1-4-salvar-resposta-bruta-em-raw-provider-e-registrar-metadados.md (atualizado)
- metadata/ingest_logs.json (criável em runtime)

Observações e próximos passos

- A persistência de metadados em JSON foi escolhida como solução inicial; sugere-se migrar para SQLite/Postgres caso seja necessário transacionamento e concorrência.
- Pendências:
  - Incluir resumo formal no `docs/sprint-reports/` (este arquivo serve como entrega)
  - Validar política de retenção/backup para `metadata/ingest_logs.json` em ambientes de produção

Decisões e justificativas

- Persistência de metadados em JSON (`metadata/ingest_logs.json`): escolha inicial para simplicidade e portabilidade. Justificativa: evita introduzir migrações e dependências de DB no MVP, facilita inspeção manual e é suficiente para uso single-user local; migrar para SQLite/Postgres quando houver necessidade de concorrência/transações.
- Escrita atômica de CSV e JSON: reduz risco de arquivos corrompidos por falhas durante gravação. Justificativa: operações atômicas garantem que consumidores não leiam arquivos incompletos e facilitam rollbacks manuais se necessário.
- `index=False` ao gravar CSV: evita coluna de índice inesperada que pode complicar reprocessamento. Justificativa: mantém o CSV compatível com ferramentas externas e evita duplicação de dados (índice como coluna).
- Checksum SHA256 e arquivo `*.checksum`: separa a verificação de integridade do conteúdo. Justificativa: checksum é usado para auditoria/reprocessamento e para detectar corrupção entre escrita e ingestão posterior.
- `set_permissions` opt-in (chmod 600): não forçamos mudanças de permissão por padrão para evitar surpresas em ambientes Windows/CI. Justificativa: permite operação segura em POSIX quando o usuário optar por aplicar políticas de segurança, sem prejudicar ambientes que não suportam `chmod`.
- Testes: uso de `tmp_path` e teste POSIX condicional para permissões. Justificativa: isola efeitos no filesystem, mantém testes portáveis entre CI (Windows) e ambientes POSIX locais.


Como validar localmente

1. Rodar testes:

```bash
poetry run pytest -q
```

2. Executar quickstart para um ticker e verificar raw + metadata:

```bash
poetry run main
ls raw/yfinance/
cat metadata/ingest_logs.json | jq '.[-1]'
```
