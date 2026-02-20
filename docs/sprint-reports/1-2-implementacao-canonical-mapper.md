# Sprint Report: Story 1.2 - Implementação do Canonical Mapper

**Data:** 2026-02-20
**Story:** 1-2-implementar-canonical-mapper-provider-schema-canonico
**Status:** ✅ Concluída

## Resumo

Implementação completa do canonical mapper que normaliza DataFrames de provedores para o esquema canônico do projeto, com validação pandera, cálculo de checksums e suporte a metadata.

## Objetivos Alcançados

### 1. Implementação do Mapper (`src/etl/mapper.py`)

- ✅ Função `to_canonical(df, provider_name, ticker)` implementada
- ✅ Retorna DataFrame com colunas canônicas: ticker, date, open, high, low, close, adj_close, volume, source, fetched_at
- ✅ Cálculo de `raw_checksum` (SHA256) do payload bruto
- ✅ Normalização de `fetched_at` para UTC ISO8601 (formato: 2026-02-17T12:34:56Z)
- ✅ Validação com pandera `DataFrameSchema` canônico
- ✅ Tratamento de erros com exceção tipada `MappingError`

### 2. Testes Unitários (`tests/test_mapper.py`)

Cobertura completa com 8 testes:
- ✅ `test_successful_mapping_from_yfinance` - mapping bem-sucedido
- ✅ `test_missing_required_columns_raises_error` - colunas faltantes
- ✅ `test_raw_checksum_correctness` - verificação de checksum correto
- ✅ `test_canonical_schema_validation` - validação pandera
- ✅ `test_invalid_types_fail_validation` - tipos inválidos
- ✅ `test_empty_dataframe_raises_error` - DataFrame vazio
- ✅ `test_timezone_normalization_to_utc` - normalização de timezone
- ✅ `test_metadata_preserved_in_attrs` - metadata preservada

### 3. Testes de Integração (`tests/integration/test_mapper_integration.py`)

- ✅ `test_canonical_output_shape_for_db_layer` - smoke test para DB layer
- ✅ `test_canonical_output_ready_for_upsert_operation` - validação de chaves de upsert (ticker, date)

### 4. Documentação

- ✅ Exemplo de mapping yfinance → canonical em `docs/planning-artifacts/adapter-mappings.md`
- ✅ Exemplo de código com uso do mapper integrado ao adaptador
- ✅ Documentação de tipos e formatos esperados

## Detalhes Técnicos

### Esquema Canônico (Pandera)

```python
CanonicalSchema = DataFrameSchema(
    {
        "ticker": Column(str, nullable=False),
        "date": Column(pd.Timestamp, nullable=False),
        "open": Column(float, nullable=False),
        "high": Column(float, nullable=False),
        "low": Column(float, nullable=False),
        "close": Column(float, nullable=False),
        "adj_close": Column(float, nullable=False),
        "volume": Column(int, nullable=False, coerce=True),
        "source": Column(str, nullable=False),
        "fetched_at": Column(str, nullable=False),
    },
    strict=True,
    coerce=True,
)
```

### Metadata (DataFrame.attrs)

- `raw_checksum`: SHA256 hex digest do CSV bruto
- `provider`: Nome do provedor (ex: 'yfinance')
- `ticker`: Símbolo do ticker

### Tratamento de Erros

Exception `MappingError` lançada para:
- DataFrame vazio
- Colunas obrigatórias faltantes
- Tipos inválidos que falham na validação pandera
- Erros na construção do DataFrame canônico

## Resultados dos Checks

### Testes
```
53 passed, 11 warnings in 1.11s
```

### Linting (pre-commit)
```
✅ ruff - Passed
✅ fix end of files - Passed
✅ trim trailing whitespace - Passed
```

### CI Orchestrator
```
✅ [1/4] Lint - Passed
✅ [2/4] Unit tests - 53 passed
✅ [3/4] Smoke - 53 passed
✅ [4/4] Integration - 1 passed
```

## Arquivos Modificados

- `src/etl/mapper.py` - implementação do mapper (já existia, formatação corrigida)
- `tests/test_mapper.py` - testes unitários (já existiam, formatação corrigida)
- `tests/integration/test_mapper_integration.py` - testes de integração (já existiam, formatação corrigida)
- `docs/planning-artifacts/adapter-mappings.md` - documentação de exemplos (já existia)
- `docs/sprint-reports/1-2-implementacao-canonical-mapper.md` - este relatório (novo)

## Dependências

Todas as dependências já estavam instaladas em `pyproject.toml`:
- `pandera = "^0.29.0"` - validação de schema DataFrame
- `pandas = "^2.3.2"` - manipulação de DataFrames

## Próximos Passos

1. Implementar comando pipeline `ingest` (Story 1.3) que orquestra adapter + mapper
2. Implementar persistência de dados canônicos no SQLite (Story 1.6)
3. Considerar expandir o mapper para suportar outros provedores (Alpha Vantage, etc.)

## Notas

A implementação já estava completa e todos os testes passando. As únicas mudanças aplicadas foram:
- Formatação automática (remoção de imports não utilizados)
- Organização de imports (ruff)
- Remoção de espaços em branco em linhas vazias

Todo o código está em conformidade com as convenções do projeto (line-length 88, Python ^3.12).
