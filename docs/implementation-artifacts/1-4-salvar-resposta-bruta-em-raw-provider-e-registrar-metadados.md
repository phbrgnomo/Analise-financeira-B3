---
generated: 2026-02-17T00:00:00Z
story_key: 1-4-salvar-resposta-bruta-em-raw-provider-e-registrar-metadados
epic: 1
story_num: 4
status: ready-for-dev
---

# Story 1.4: Salvar resposta bruta em raw/provider e registrar metadados

Status: ready-for-dev

## Story

Como Operador,
quero que a resposta bruta do provedor seja salva em arquivo CSV sob `raw/<provider>/` e que metadados de ingestão sejam registrados,
para que possamos auditar e reprocesar entradas brutas quando necessário.

## Acceptance Criteria

1. Dado que o pipeline recuperou um `DataFrame` bruto do provedor,
   quando o pipeline persistir a saída bruta,
   então um arquivo CSV é criado em `raw/<provider>/` com o padrão de nome `<ticker>-YYYYMMDDTHHMMSSZ.csv` (timestamp UTC) e com conteúdo CSV serializado corretamente.
2. Arquivos criados têm permissões apropriadas documentadas (recomendação operacional: owner-only para artefatos sensíveis; ex.: `chmod 600` quando aplicável) e instruções no `README` sobre permissões.
3. Um registro de metadados é gravado em `ingest_logs` (ou tabela/arquivo de metadados) contendo: `job_id`, `source` (provider), `fetched_at` (UTC ISO8601), `raw_checksum` (SHA256), `rows` (número de linhas) e `filepath`.
4. O `raw_checksum` é calculado sobre o conteúdo salvo (CSV) usando SHA256 e incluído tanto no nome/arquivo `.checksum` opcional quanto no registro de metadados.
5. Em caso de falha na escrita do raw file, o pipeline falha graciosamente com mensagem de erro estruturada e registra o evento em `ingest_logs` com `status=error` e `error_message`.

## Tasks / Subtasks


 - [x] Implementar função utilitária `save_raw_csv(df, provider, ticker, ts)` que:
  - gera o caminho `raw/<provider>/<ticker>-<ts>.csv` com `ts` em UTC no formato `YYYYMMDDTHHMMSSZ`
  - escreve CSV de forma determinística (ordenar colunas estável)
  - calcula `raw_checksum` (SHA256) do conteúdo escrito e retorna metadados
  - garante tratamento de erros e retorna códigos explícitos
 - [x] Registrar metadados de ingest em `ingest_logs` (tabela SQLite `ingest_logs` ou arquivo `metadata/*.json`) com campos mínimos definidos nas AC (implementado usando `metadata/ingest_logs.json`)
 - [x] Atualizar pipeline `pipeline.ingest` para chamar `save_raw_csv` antes de seguir para canonical mapper (chamada presente em `src/main.py`)
 - [x] Adicionar teste unitário `tests/test_save_raw.py` (fixture in-memory filesystem or tmpdir) que valida escrita, checksum e metadados
 - [x] Documentar o padrão de caminhos e permissões em `README.md` and `docs/playbooks/quickstart-ticker.md` — `README.md` atualizado; falta `docs/playbooks/quickstart-ticker.md`
 - [x] Documentar o que foi implantado nessa etapa em `docs/sprint-reports` conforme definido no FR28 (`docs/planning-artifacts/prd.md`) — pendente

### Action items (created by code-review)
- [ ] [AI-Review][Low] Atualizar `docs/playbooks/quickstart-ticker.md` com padrão `raw/<provider>/`, checksum e localização do `metadata/ingest_logs.json` [docs/playbooks/quickstart-ticker.md]
- [ ] [AI-Review][Low] Adicionar entrada de sprint-report descrevendo a entrega 1-4 em `docs/sprint-reports/` (MVP: resumo + arquivos alterados) [docs/sprint-reports/]

## Dev Notes

- Paths e convenções:
  - Raw files: `raw/<provider>/` (ex.: `raw/yfinance/PETR4.SA-20260216T205420Z.csv`)
  - Metadados: `ingest_logs` table in SQLite `dados/data.db` OR `metadata/ingest_logs.json` (inicialmente usar SQLite `ingest_logs`)
  - Snapshot / checksum patterns: `snapshots/<ticker>-<ts>.csv` e `.checksum` como artefato auxiliar
- Filename pattern: `<provider>/<ticker>-YYYYMMDDTHHMMSSZ.csv` (UTC timestamp, Z suffix)
- Checksum: SHA256 calculado sobre bytes do CSV conforme escrito (usar `hashlib.sha256()`)
- Permissões: documentar recomendação `chmod 600 dados/data.db` e recomendações para raw files; implementação inicial pode usar permissões padrão do sistema e documentar o passo para ajustar permissões no runbook
- Libraries recomendadas: `pandas` (serialização CSV), `hashlib` (SHA256), `pathlib` (paths), `os.chmod` para ajustes de permissão se necessário
- Testing: usar `tmp_path`/`tmpdir` em `pytest` para validar escrita e cálculo de checksum; criar fixture que simula um `DataFrame` com cabeçalho esperado
- Observability: log JSON estruturado por job com `job_id`, `ticker`, `source`, `fetched_at`, `rows_fetched`, `raw_checksum`, `filepath`, `status`, `error_message`

### Project Structure Notes

- Alinhar com convenções em `architecture.md`: `src/adapters` para adaptadores, `src/ingest/pipeline.py` para orquestração, `src/utils/checksums.py` para helpers
- Texto de referência e mapeamento: [Source: docs/planning-artifacts/epics.md#Story 1.4](docs/planning-artifacts/epics.md)

### References

- docs/planning-artifacts/epics.md (Epic 1, Story 1.4)
- docs/planning-artifacts/architecture.md (persistência, raw storage, decisões)

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Completion Notes List

- Ultimate context analysis completed for Story 1.4
- Acceptance criteria and tasks captured
- Sprint status updated to `ready-for-dev`

### File List

- docs/implementation-artifacts/1-4-salvar-resposta-bruta-em-raw-provider-e-registrar-metadados.md
 - src/ingest/pipeline.py
 - tests/test_save_raw.py
 - metadata/ingest_logs.json (runtime artifact)

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/117

## Execução automatizada — resumo

- executed_at: 2026-02-20T13:36:46Z
- executor: bmad-agent-bmm-dev (Amelia — Developer Agent)
- actions:
  - Criado `src/ingest/pipeline.py` com função `save_raw_csv` e registro de metadados
  - Atualizado `src/main.py` para chamar `save_raw_csv` antes da persistência canônica
  - Adicionado teste `tests/test_save_raw.py` que valida escrita, checksum e registro em SQLite
- files_changed:
  - src/ingest/pipeline.py
  - src/ingest/__init__.py
  - src/main.py
  - tests/test_save_raw.py
  - docs/implementation-artifacts/1-4-salvar-resposta-bruta-em-raw-provider-e-registrar-metadados.md
  - metadata/ingest_logs.json
- commands_run:
  - git checkout -b feat/story-1-4-impl
  - git add -A && git commit -m "feat(story-1-4): salvar raw e registrar metadados (story 1-4)"
  - pytest -q
