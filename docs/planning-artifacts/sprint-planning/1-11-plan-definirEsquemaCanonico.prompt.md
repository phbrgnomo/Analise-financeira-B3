Plan: Definir Esquema Canônico e Exemplos

Resumo

Criar o esquema canônico (`docs/schema.yaml` + `docs/schema.md`), validar o exemplo CSV existente, adicionar um mapper canônico em `src/adapters` e um teste de validação `tests/test_schema.py` usando `pandera`. Atualizar `pyproject.toml` (dependências de desenvolvimento) e o CI (`.github/workflows/ci.yml`) para executar a validação. Resultado: snapshot CSVs terão contrato explícito e CI garante conformidade.

Passos de Implementação

1. Schema file
- Criar `docs/schema.yaml` com `schema_version: 1` e definições das colunas recomendadas:
  - `ticker` (string, não-nulo)
  - `date` (string, formato YYYY-MM-DD, não-nulo)
  - `open` (float, nullable)
  - `high` (float, nullable)
  - `low` (float, nullable)
  - `close` (float, nullable)
  - `adj_close` (float, nullable)
  - `volume` (integer, nullable)
  - `source` (string, não-nulo)
  - `fetched_at` (datetime UTC ISO8601, não-nulo)
  - `raw_checksum` (string, SHA256 hex, não-nulo)
- Incluir notas semânticas e flags `nullable`/`description` por campo.

2. Docs
- Criar `docs/schema.md` explicando significado de cada campo, formatos aceitos (`date`, `fetched_at`), política de versionamento (`schema_version`) e orientação de migração (minor vs breaking).
- Referenciar `dados/examples/ticker_example.csv` e explicar como produtores devem popular campos de metadata.

3. Exemplo CSV
- Rever `dados/examples/ticker_example.csv` (atualmente presente) e garantir que contenha header compatível e linhas representativas, incluindo `fetched_at` e `raw_checksum` de exemplo.

4. Mapper canônico
- Adicionar `src/adapters/canonical_mapper.py` com função `map_to_canonical(df, source_meta)` que:
  - Normaliza nomes/formatos de colunas do provedor para os nomes canônicos.
  - Garante formatos (`date` como `YYYY-MM-DD`, `fetched_at` em UTC ISO8601).
  - Calcula `raw_checksum` (SHA256 do payload/CSV) quando ausente.
  - Preenche `source` a partir de `source_meta`.
- Testes unitários simples para o mapper (ex.: transformar DataFrame de exemplo).

5. Teste de schema
- Adicionar `tests/test_schema.py` que:
  - Carrega `docs/schema.yaml`.
  - Lê `dados/examples/ticker_example.csv` com `pandas`.
  - Cria `pandera.DataFrameSchema` baseado no YAML e valida o DataFrame.
  - Falha se o CSV não estiver conforme.

6. Dependência (`pandera`)
- Adicionar `pandera` como dependência de desenvolvimento no `pyproject.toml`.
- Comandos sugeridos (poetry):
```
poetry add -D pandera
poetry install
```

7. CI
- Atualizar `.github/workflows/ci.yml` para garantir que o job `test` instala dependências dev (incluindo `pandera`) e executa `pytest tests/test_schema.py` (ou `pytest -k schema`) como etapa antes de publicar snapshots.

8. Integração com `main`/ingestão
- Atualizar `src/main.py` (ou ponto de geração de snapshots) para usar opcionalmente `src/adapters/canonical_mapper.map_to_canonical()` antes de salvar CSV, garantindo que snapshots persistidos já estejam no formato canônico.
- Tornar isso opt-in via flag/variável de ambiente se necessário.

9. Atualizar documentação de implementação
- Atualizar `docs/implementation-artifacts/1-11-definir-esquema-can%C3%B4nico-de-dados-e-documenta%C3%A7%C3%A3o-do-modelo-schema-examples.md` com links para os novos arquivos e status.

10. Testes finais e verificação
- Rodar `poetry run pytest` e garantir que `tests/test_schema.py` passe.
- Validar a pipeline CI na PR.

Verificação / Comandos de Validação

- Rodar teste isolado:
```
poetry run pytest tests/test_schema.py -q
```
- Rodar toda a suíte:
```
poetry run pytest -q
```
- Executar o entrypoint (opcional):
```
poetry run main
# ou
python -m src.main
```

Decisões

- Validador escolhido: `pandera` como dependência de desenvolvimento (escolha aprovada). Motivo: expressividade e fácil integração com `pandas`.
- Schema storage: YAML (`docs/schema.yaml`) com `schema_version` para rastreio de migrações.
- Mapper: implementar um adapter canônico em `src/adapters` para centralizar mapeamentos provider→canônico.

Riscos & Mitigações

- Risco: adicionar `pandera` altera CI. Mitigação: instalar via `poetry` e rodar apenas o teste de schema como etapa leve antes de etapas pesadas.
- Risco: mudanças no formato de snapshots podem quebrar consumidores. Mitigação: documentar política de versão/migração em `docs/schema.md` e usar `schema_version` nos snapshots.
