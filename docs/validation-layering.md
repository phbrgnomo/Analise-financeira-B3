# Validação em Camadas — Estratégia e Responsabilidades

Este documento descreve a divisão de responsabilidades entre as duas camadas de
validação presentes no pipeline de ingestão do projeto e como as falhas são
registradas para auditoria.

1. Adapter-level (sanity checks)
  - Localização: `src/adapters/base.py` (método `_validate_dataframe`).
  - Responsabilidade: garantir sanidade dos dados retornados pelo provedor antes
    do mapeamento — verificar DataFrame não vazio, presença das colunas OHLCV
    esperadas e índice `DatetimeIndex`.
  - Comportamento em caso de falha: lança `ValidationError` imediatamente.
  - Auditoria: essas falhas agora são registradas (best-effort) em
    `metadata/ingest_logs.json` com `reason_code=ADAPTER_VALIDATION` para
    facilitar triagem.

2. Canonical-level (schema/semantics)
  - Localização: `src/validation.py` (`validate_dataframe`, `validate_and_handle`).
  - Responsabilidade: validação pós-mapeamento ao esquema canônico do projeto
    (tipos, constraints por-linha, checks como `high > low`, coerção/normalização
    e separação de linhas válidas e inválidas).
  - Comportamento em caso de falha: o validador produz `invalid_df` com
    `_validation_errors` por linha, persiste CSVs de inválidos em
    `raw/<provider>/invalid-<ticker>-<ts>.csv` e registra entradas detalhadas em
    `metadata/ingest_logs.json`. Se a porcentagem de inválidos exceder o
    threshold (`VALIDATION_INVALID_PERCENT_THRESHOLD` / `--validation-tolerance`),
    o ingest pode ser abortado lançando `ValidationError`.

Observações operacionais
- Os dois níveis têm propósitos distintos: o adaptador protege contra respostas
  de provedores que violam contratos básicos; o validador canônico trata da
  conformidade com o schema do produto e da coleta de evidências para auditoria.
- Recomenda-se usar `ingest_logs` como fonte única para triagem operacional —
  tanto erros do adaptador quanto inválidos canônicos são gravados no mesmo
  arquivo, com campos e códigos de razão consistentes.

Recomendações futuras
- Unificar as `reason_code` possíveis em um arquivo de referência (`docs/`) para
  facilitar mapeamento em dashboards/alertas.
- Adicionar um pequeno utilitário CLI para consultar `ingest_logs` e filtrar por
  `reason_code`, `ticker` e `created_at` (veja story 4.2).

Arquivo(s) relevantes
- `src/adapters/base.py` — checks do adaptador e (novo) logging de falhas
- `src/validation.py` — validação canônica, persistência de inválidos e logging
- `metadata/ingest_logs.json` — registro de ingestões e eventos de validação
