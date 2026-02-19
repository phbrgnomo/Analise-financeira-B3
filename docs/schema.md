# Schema de Dados Canônico - Snapshots Financeiros

**Versão do Schema:** 1  
**Data da Última Atualização:** 2026-02-19  
**Responsável:** Data Engineering Team

---

## Visão Geral

Este documento descreve o esquema canônico para snapshots de dados financeiros armazenados em arquivos CSV no diretório `dados/`. O esquema define um contrato estável para consumidores downstream (notebooks, métricas, análises) e estabelece políticas de versionamento e migração.

## Localização dos Arquivos

- **Schema YAML:** `docs/schema.yaml` (definição técnica completa)
- **Schema MD:** `docs/schema.md` (este documento - explicação para humanos)
- **Exemplos:** `dados/examples/ticker_example.csv` (arquivo de exemplo validado)
- **Snapshots:** `dados/` (arquivos CSV de produção)

---

## Estrutura das Colunas

### Colunas Obrigatórias

#### `ticker` (string, NOT NULL)
- **Descrição:** Símbolo do ativo (ex: PETR4, VALE3, ITUB4)
- **Formato:** Alfanumérico maiúsculo, máximo 10 caracteres
- **Exemplo:** `"PETR4"`
- **Validação:** Deve estar em maiúsculas e ter no máximo 10 caracteres

#### `date` (date, NOT NULL)
- **Descrição:** Data da negociação no formato ISO 8601
- **Formato:** `YYYY-MM-DD`
- **Exemplo:** `"2024-01-15"`
- **Validação:** Deve ser uma data válida, não pode ser futura

#### `source` (string, NOT NULL)
- **Descrição:** Identificador da fonte de dados (ex: yfinance, b3-api)
- **Formato:** Alfanumérico minúsculo com hífens, máximo 50 caracteres
- **Exemplo:** `"yfinance"`
- **Validação:** Lowercase, apenas letras, números e hífens

#### `fetched_at` (datetime, NOT NULL)
- **Descrição:** Timestamp UTC de quando os dados foram obtidos do provedor
- **Formato:** ISO 8601 com timezone UTC: `YYYY-MM-DDTHH:MM:SSZ`
- **Exemplo:** `"2024-01-15T18:30:45Z"`
- **Validação:** Deve ser >= date (não pode buscar dados antes da data de negociação)

---

### Colunas de Dados de Mercado (Opcionais)

#### `open` (float, NULLABLE)
- **Descrição:** Preço de abertura do dia de negociação
- **Formato:** Número decimal, 2 casas recomendadas
- **Exemplo:** `28.50`
- **Validação:** Deve ser >= 0

#### `high` (float, NULLABLE)
- **Descrição:** Preço máximo alcançado durante o dia
- **Formato:** Número decimal, 2 casas recomendadas
- **Exemplo:** `29.75`
- **Validação:** Deve ser >= 0, >= open, >= close

#### `low` (float, NULLABLE)
- **Descrição:** Preço mínimo alcançado durante o dia
- **Formato:** Número decimal, 2 casas recomendadas
- **Exemplo:** `28.25`
- **Validação:** Deve ser >= 0, <= open, <= close

#### `close` (float, NULLABLE)
- **Descrição:** Preço de fechamento do dia
- **Formato:** Número decimal, 2 casas recomendadas
- **Exemplo:** `29.10`
- **Validação:** Deve ser >= 0

#### `adj_close` (float, NULLABLE)
- **Descrição:** Preço de fechamento ajustado (considera splits, dividendos, bonificações)
- **Formato:** Número decimal, 2 casas recomendadas
- **Exemplo:** `29.10`
- **Validação:** Deve ser >= 0
- **Nota:** Importante para análises históricas precisas

#### `volume` (integer, NULLABLE)
- **Descrição:** Volume de negociação (quantidade de ações negociadas)
- **Formato:** Número inteiro
- **Exemplo:** `15420000`
- **Validação:** Deve ser >= 0

---

### Colunas de Auditoria e Rastreabilidade

#### `raw_checksum` (string, NULLABLE)
- **Descrição:** Checksum SHA256 do payload bruto do provedor para auditabilidade
- **Formato:** String hexadecimal minúscula de 64 caracteres
- **Exemplo:** `"a3f2c5d8e9b1234567890abcdef01234567890abcdef01234567890abcdef0123"`
- **Validação:** Deve ser um hash SHA256 válido (64 caracteres hexadecimais)
- **Uso:** Permite verificar integridade dos dados originais e detectar alterações

---

### Colunas Calculadas (Legacy)

#### `Return` (float, NULLABLE)
- **Descrição:** Retorno diário calculado
- **Fórmula:** `(close - close_anterior) / close_anterior`
- **Exemplo:** `0.0234` (representando 2.34% de retorno)
- **Nota:** Coluna mantida para compatibilidade com `src/retorno.py` e consumers existentes
- **Validação:** Pode ser negativo (perdas) ou positivo (ganhos)

---

## Formato de Arquivo CSV

### Especificações Técnicas

- **Tipo:** CSV (Comma-Separated Values)
- **Encoding:** UTF-8
- **Delimitador:** `,` (vírgula)
- **Header:** Primeira linha contém nomes das colunas
- **Quoting:** Minimal (apenas quando necessário)
- **Separador Decimal:** `.` (ponto)
- **Formato de Data:** `YYYY-MM-DD`
- **Formato de Datetime:** ISO 8601 com UTC (`YYYY-MM-DDTHH:MM:SSZ`)
- **Representação de NULL:** String vazia `""`

### Convenção de Nomenclatura

Arquivos de snapshot devem seguir um dos padrões:
- `{ticker}_snapshot.csv` - snapshot completo do ativo
- `{ticker}_{date_range}.csv` - snapshot de período específico

**Exemplos:**
- `PETR4_snapshot.csv`
- `VALE3_2024-01.csv`
- `ITUB4_2023-Q1.csv`

---

## Versionamento e Política de Migração

### Versão Atual

**Schema Version:** 1  
**Data:** 2026-02-19

### Tipos de Mudanças

#### Mudanças Menores (NÃO incrementam schema_version)
Mudanças compatíveis que não quebram consumers existentes:
- ✅ Adicionar novas colunas opcionais (nullable=true)
- ✅ Adicionar novas constraints que não invalidam dados existentes
- ✅ Adicionar campos de metadata ou documentação
- ✅ Melhorar descrições ou exemplos

**Ação requerida:** Nenhuma para consumers existentes

#### Mudanças Breaking (DEVEM incrementar schema_version)
Mudanças incompatíveis que podem quebrar consumers:
- ❌ Remover colunas existentes
- ❌ Renomear colunas
- ❌ Alterar tipos de dados de colunas
- ❌ Tornar colunas nullable em non-nullable
- ❌ Adicionar colunas non-nullable sem valores padrão
- ❌ Alterar formato de valores (ex: mudar formato de data)

**Ação requerida:**
1. Incrementar `schema_version` em `docs/schema.yaml`
2. Documentar mudança em `versioning.migration_notes`
3. Atualizar todos os consumers conhecidos
4. Fornecer scripts de migração se necessário
5. Comunicar equipe sobre breaking change

### Histórico de Versões

#### Version 1 (2026-02-19)
- **Descrição:** Schema canônico inicial
- **Mudanças:**
  - Estabelecida estrutura base de colunas
  - Incluída coluna `Return` para compatibilidade com código existente
  - Definidas políticas de versionamento e migração
  - Criado exemplo de referência

---

## Regras de Validação

### Colunas Obrigatórias
Todo arquivo CSV válido DEVE conter:
- `ticker`
- `date`
- `source`
- `fetched_at`

### Regras de Negócio
1. **Consistência de Preços:**
   - `high >= low` (sempre)
   - `high >= open` e `high >= close` (quando presentes)
   - `low <= open` e `low <= close` (quando presentes)

2. **Consistência Temporal:**
   - `date` deve ser no passado ou hoje (sem datas futuras)
   - `fetched_at >= date` (não pode buscar dados antes da data de negociação)

3. **Consistência de Dados:**
   - Valores numéricos (preços, volume) devem ser >= 0
   - `raw_checksum` deve ser SHA256 válido quando presente

---

## Armazenamento e Checksums

### Estrutura de Diretórios

```
dados/
├── examples/
│   └── ticker_example.csv          # Exemplo de referência validado
├── PETR4_snapshot.csv              # Snapshot de produção
├── PETR4_snapshot.csv.checksum     # SHA256 checksum do snapshot
├── VALE3_snapshot.csv
├── VALE3_snapshot.csv.checksum
└── ...
```

### Checksums de Snapshots

Todos os snapshots em `dados/` DEVEM ter um arquivo `.checksum` associado:
- **Formato:** SHA256 hex do conteúdo do CSV
- **Naming:** `{snapshot_filename}.checksum`
- **Validação:** CI deve verificar checksums no pipeline

**Exemplo de geração:**
```bash
sha256sum dados/PETR4_snapshot.csv | cut -d' ' -f1 > dados/PETR4_snapshot.csv.checksum
```

---

## Exemplo de Uso

### Arquivo de Exemplo

Veja `dados/examples/ticker_example.csv` para um exemplo completo e validado.

### Leitura em Python (pandas)

```python
import pandas as pd

# Ler CSV com schema canônico
df = pd.read_csv('dados/PETR4_snapshot.csv', 
                 parse_dates=['date'],
                 dtype={
                     'ticker': str,
                     'source': str,
                     'open': float,
                     'high': float,
                     'low': float,
                     'close': float,
                     'adj_close': float,
                     'volume': 'Int64',  # nullable integer
                     'raw_checksum': str,
                     'Return': float
                 })

# Converter fetched_at para datetime UTC
df['fetched_at'] = pd.to_datetime(df['fetched_at'], utc=True)

# Validar colunas obrigatórias
required_cols = ['ticker', 'date', 'source', 'fetched_at']
assert all(col in df.columns for col in required_cols), "Missing required columns"

# Validar regras de negócio
assert (df['high'] >= df['low']).all(), "high must be >= low"
assert (df['date'] <= pd.Timestamp.now().date()).all(), "No future dates allowed"
```

### Validação com Pandera

```python
import pandera as pa
from pandera import Column, DataFrameSchema

# Schema de validação
schema = DataFrameSchema({
    'ticker': Column(str, nullable=False),
    'date': Column('datetime64[ns]', nullable=False),
    'open': Column(float, nullable=True, checks=pa.Check.ge(0)),
    'high': Column(float, nullable=True, checks=pa.Check.ge(0)),
    'low': Column(float, nullable=True, checks=pa.Check.ge(0)),
    'close': Column(float, nullable=True, checks=pa.Check.ge(0)),
    'adj_close': Column(float, nullable=True, checks=pa.Check.ge(0)),
    'volume': Column('Int64', nullable=True, checks=pa.Check.ge(0)),
    'source': Column(str, nullable=False),
    'fetched_at': Column('datetime64[ns, UTC]', nullable=False),
    'raw_checksum': Column(str, nullable=True),
    'Return': Column(float, nullable=True),
})

# Validar DataFrame
validated_df = schema.validate(df)
```

---

## Integração com Adapters

Os adapters (implementados conforme Story 1.1) devem mapear dados do provedor para este schema canônico:

### Responsabilidades do Adapter

1. **Normalização de Nomes:** Mapear nomes de colunas do provedor para nomes canônicos
2. **Conversão de Tipos:** Garantir tipos corretos (strings, floats, datetimes)
3. **Formato de Datas:** Converter para `YYYY-MM-DD` e ISO 8601 UTC
4. **Metadados:** Adicionar `source`, `fetched_at`, `raw_checksum`
5. **Validação:** Aplicar regras de negócio antes de persistir

### Exemplo de Mapeamento (yfinance)

```python
# Mapeamento yfinance -> schema canônico
column_mapping = {
    'Date': 'date',
    'Open': 'open',
    'High': 'high',
    'Low': 'low',
    'Close': 'close',
    'Adj Close': 'adj_close',
    'Volume': 'volume',
}

# Adicionar metadados
df['ticker'] = ticker_symbol
df['source'] = 'yfinance'
df['fetched_at'] = datetime.now(timezone.utc).isoformat()
df['raw_checksum'] = calculate_sha256(raw_response)
```

---

## Referências

- **Schema YAML:** `docs/schema.yaml` (definição técnica completa)
- **Exemplo CSV:** `dados/examples/ticker_example.csv`
- **Story Original:** `docs/implementation-artifacts/1-11-definir-esquema-canonico-de-dados-e-documentacao-do-modelo-schema-examples.md`
- **PRD:** `docs/planning-artifacts/prd.md` (recomendações de modelo de dados)
- **Project Context:** `docs/project-context.md` (regras de dados e persistência)

---

## Próximos Passos

1. **Implementação:** Adapters devem seguir este schema (ref: Story 1.1)
2. **Validação:** Testes automatizados devem validar conformidade com schema
3. **CI/CD:** Pipeline deve verificar checksums e validar snapshots
4. **Documentação:** Manter este documento sincronizado com `schema.yaml`
5. **Evolução:** Seguir política de versionamento para mudanças futuras

---

**Última Atualização:** 2026-02-19  
**Versão do Schema:** 1  
**Status:** Ativo
