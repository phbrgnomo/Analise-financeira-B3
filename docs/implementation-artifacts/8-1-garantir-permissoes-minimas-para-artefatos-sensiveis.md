## Story 8.1: garantir-permissoes-minimas-para-artefatos-sensiveis

Status: ready-for-dev

## Story

As a Administrador/DevOps,
I want garantir permissões mínimas para artefatos sensíveis (DB, raw, snapshots, .env),
so that dados sensíveis e segredos não fiquem expostos em checkouts locais ou em repositório.

## Acceptance Criteria

1. Ao criar ou atualizar `dados/data.db` o arquivo deve ter permissões owner-only (ex.: chmod 600) por padrão.
2. Arquivos sensíveis gerados pelo pipeline (ex.: `raw/<provider>/*.csv` contendo dados brutos sensíveis) devem ter permissões restritas documentadas e recomendação de `chmod 600` ou diretório com `0700` dependendo do caso.
3. O projeto fornece um comando/documentação para aplicar permissões padrão pós-criação (`scripts/apply-perms.sh` ou instruções CLI).
4. CI inclui uma verificação (script simples) que falha se arquivos sensíveis no repositório tiverem permissões públicas (por exemplo, permissões de world-readable).
5. `.env.example` permanece sem segredos e README descreve como armazenar segredos localmente e recomendações (python-dotenv, gitignore, not commit).
6. Tests: existe um teste/checagem (pode ser unitário ou script) que inspeciona `dados/data.db` criado durante testes locais para garantir `stat().st_mode` corresponde a 0o600.
7. Documento de aceitação lista arquivos/paths considerados sensíveis e a política de permissão aplicada.

## Tasks / Subtasks

- [ ] Task 1 (AC: 1,2) - Implementar permissão default ao criar `dados/data.db`
  - [ ] Subtask 1.1 - Atualizar código de criação de DB (ex.: modulo `src` que cria `dados/`) para aplicar `os.chmod(path, 0o600)` após criação
  - [ ] Subtask 1.2 - Adicionar configuração/flag `DATA_DIR_PERMS` ou usar `umask` controlado por `.env`
- [ ] Task 2 (AC: 3,4) - Documentar e fornecer script para aplicar permissões
  - [ ] Subtask 2.1 - Adicionar `scripts/apply-perms.sh` com instruções seguras
  - [ ] Subtask 2.2 - Atualizar `README.md` e `docs/planning-artifacts/epics.md` seção de segurança
- [ ] Task 3 (AC: 4,6) - CI check e testes
  - [ ] Subtask 3.1 - Adicionar `ci/check-perms.sh` que valida não-exposição de arquivos sensíveis
  - [ ] Subtask 3.2 - Adicionar teste em `tests/` que cria um DB temporário e verifica modo de arquivo
- [ ] Task 4 (AC: 5) - Segredos e `.env`
  - [ ] Subtask 4.1 - Garantir `.env.example` não contenha segredos e README mostre fluxo recomendado (copy `.env.example` -> `.env`)
  - [ ] Subtask 4.2 - Documentar uso de `python-dotenv` e recomendações de armazenamento seguro (OS keyring, env vars)

## Dev Notes

- Arquivos e paths relevantes:
  - `dados/data.db` (SQLite) — deve ser criado com permissões owner-only `0o600`.
  - `raw/<provider>/` — recomenda-se `0700` diretório e arquivos `0600` quando contém dados sensíveis.
  - `snapshots/` — snapshots que contêm dados exportados podem ser marcados como sensíveis; documentar política específica (por padrão `0640` ou `0600`).
  - `tests/fixtures` — fixtures não devem conter segredos; manter amostras públicas.

- Implementação técnica recomendada:
  - Após criação de arquivos (DB, raw, snapshots), chamar `os.chmod(path, 0o600)` ou `pathlib.Path(path).chmod(0o600)`.
  - Usar `tempfile.NamedTemporaryFile(delete=False)` em pipelines antes de mover para destino final com permissões ajustadas.
  - Ao criar diretórios, usar `os.makedirs(path, exist_ok=True, mode=0o700)` e validar permissões após criação.
  - Adicionar utilitário `src/utils/secure_fs.py` com helpers `secure_write_file`, `secure_mkdir`, `apply_default_perms` para reutilização.

### Security checks and CI

- CI job `ci/check-perms.sh` pode executar `find` para detectar arquivos com máscara de permissão insegura e falhar:
  - `find . -type f \( -path './dados/*' -o -path './raw/*' \) -perm /o=r -print` → se houver saída, falhar.
- Incluir Snyk/CVE scanning (conforme regras do projeto) e secret scanning pre-commit hooks (ex.: `pre-commit` + `detect-secrets`) como recomendação/next step.

### Testing

- Test cria DB temporário em `tmp/` (ou tmpdir fixture) e verifica `os.stat(db_path).st_mode & 0o777 == 0o600`.
- Test de integração opcional cria raw file e verifica `0600` ou diretório `0700` conforme política.

## Project Structure Notes

- Alinhar utilitários de permissão em `src.utils` para evitar duplicação.
- Não hardcodear caminhos; obter `DATA_DIR` de config/env e documentar padrão `./dados`.

## References

- Source: [epics](docs/planning-artifacts/epics.md#nonfunctional-requirements) — NFR-Sec1 e FR32
- Source: [architecture](docs/planning-artifacts/architecture.md) (relevant sections may apply)
- Guidance: docs/planning-artifacts/prd.md

## Dev Agent Record

### Agent Model Used
internal-analysis-agent

### Completion Notes List

- Story scaffolded and acceptance criteria/tasks defined.

### File List

- docs/implementation-artifacts/8-1-garantir-permissoes-minimas-para-artefatos-sensiveis.md
