---
title: "Story 5.3: documentar-mappings-provider-canonico-em-adapter-mappings.md"
status: ready-for-dev
story_id: "5.3"
story_key: "5-3-documentar-mappings-provider-canonico-em-adapter-mappings-md"
---

# Story 5.3: documentar-mappings-provider-canonico-em-adapter-mappings.md

Status: ready-for-dev

## Story

Como desenvolvedor de integração de dados,
quero documentar os mappings do provider canônico para o adapter `mappings.md`,
para que outros desenvolvedores entendam claramente o mapeamento de campos, conversões de tipos e onde alterar/estender o adaptador sem introduzir regressões.

## Acceptance Criteria

1. Documento `docs/implementation-artifacts/5-3-documentar-mappings-provider-canonico-em-adapter-mappings-md.md` criado com linguagem clara em PT-BR.
2. Inclui tabela de mapeamento campo-a-campo entre fonte (raw provider) e schema canônico (colunas esperadas em `dados/` CSVs e `src.retorno`), com exemplos de valores.
3. Explica conversões de unidades/tipos (ex.: ajuste de preços, tratamento de NA, formatação de datas) e periodicidade esperada (diário, ajustes de fechamento).
4. Lista locais de código a serem modificados (ex.: `src/dados_b3.py`, `src/retorno.py`, `src/main.py`) e arquivos de dados afetados (`dados/*.csv`).
5. Contém notas de testes: exemplos de CSVs de entrada, comandos para validação local e casos de borda (missing, múltiplos tickers, split/bonificação).
6. Referências apontando para `docs/schema.md`, `README.md` e quaisquer PRD/epics relevantes.

## Tasks / Subtasks

- [ ] Analisar schema canônico em `docs/schema.md` e `src/retorno.py` (AC: #1,#2)
  - [ ] Listar todos os campos canônicos e seus tipos
- [ ] Mapear cada campo do provider (Yahoo / pandas-datareader) para campo canônico (AC: #2)
  - [ ] Documentar transformações necessárias (ajuste de preço, divisão, timezone, formato de data)
- [ ] Escrever exemplos de entrada (raw CSV snippet) e saída (Canonical CSV snippet) (AC: #3)
- [ ] Indicar pontos no código onde as mudanças são feitas (AC: #4)
- [ ] Adicionar instruções de teste local e validação (AC: #5)
- [ ] Revisão por pair programming / code review (AC: #6)

## Dev Notes

- Padrões e restrições arquiteturais relevantes:
  - Respeitar o formato de dados persistidos em `dados/` (coluna `Return` já existente para séries de retorno).
  - Reutilizar funções de transformação em `src.retorno` sempre que possível (evitar duplicação de lógica).
  - Manter compatibilidade com pipelines existentes que esperam `Adj Close` ou retornos diários.

- Componentes do projeto a tocar:
  - `src/dados_b3.py` — integração / coleta via Yahoo (`.SA` suffix handling).
  - `src/retorno.py` — funções de cálculo/conversão de retorno e risco.
  - `dados/` — exemplos de CSVs e fixtures para testes.
  - `docs/schema.md` — referência de esquema canônico.

### Project Structure Notes

- Nomeclatura: manter `TICKER.SA` para símbolos B3; arquivos em `dados/` devem ser `TICKER.csv` com colunas esperadas.
- Detectadas variações: alguns CSVs de exemplo usam `Adj Close`, outros usam `Close` — documentar preferência e fallback.

### References

- Source: [docs/schema.md](docs/schema.md#esquema-canonico)
- Source: [src/dados_b3.py](src/dados_b3.py#L1)
- Source: [src/retorno.py](src/retorno.py#L1)
- Project README: [README.md](README.md)

## Dev Agent Record

### Agent Model Used
GPT-5 mini (modo de execução: YOLO — análises e decisões automatizadas)

### Debug Log References

Nenhum log de execução adicional foi gravado neste passo além do arquivo de story gerado.

### Completion Notes List

- Análise inicial completada em modo YOLO; o documento contém mapeamento, exemplos e tarefas para implementação.

### File List

- docs/implementation-artifacts/5-3-documentar-mappings-provider-canonico-em-adapter-mappings-md.md
