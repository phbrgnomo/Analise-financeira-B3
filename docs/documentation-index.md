# Índice de documentação do projeto

Este documento contém a lista canônica de arquivos de documentação
usados pelo repositório _Analise-financeira-B3_. Ele serve como referência
para colaboradores verificarem rapidamente quais documentos existem e quais
podem precisar ser atualizados durante mudanças de código ou arquitetura.

## Estrutura principal

- `README.md` – Visão geral do projeto e instruções rápidas de início.
- `docs/` – Documentação detalhada:
  - `diagrama-dataflow.md` – Diagramas e explicações do fluxo de dados.
  - `metadata_contract.md` – Especificações do contrato de metadata.
  - `metadata_schema.json` – Esquema JSON para validação de metadata.
  - `project-context.md` – Contexto do projeto e regras para agentes de IA.
  - `quickstart-ci.md` – Guia para reproduzir a CI localmente.
  - `schema.md` – Documentação do esquema de dados.

## Seções especializadas

### docs/modules/
- `adapter-guidelines.md` – Diretrizes para criação de adapters.
- `adapter-mappings.md` – Mapeamentos de campos do provedor para o esquema.
- `adapter-pr-checklist.md` – Checklist de PRs que modificam adapters.
- `retornos-conventions.md` – Convenções para cálculos de retornos financeiros.
- `yfinance_adapter.md` – Documentação específica do adapter Yahoo Finance.

### docs/planning-artifacts/
- `architecture.md` – Visão geral da arquitetura do sistema.
- `prd.md` – Documento de requisitos do produto.

### docs/playbooks/
- `quickstart-cli.md` – Guia de uso da CLI.
- `quickstart-tickers.md` – Guia para reproduzir o pipeline de ingestão.
- `validate-snapshots.md` – Guia para identificar e validar snapshots.
- `testing-network-fixtures.md` – Guia para utilização de fixtures de rede.
- `ux.md` – Expectativas de UX para CLI, notebooks e interface Streamlit.

> **Nota:** Esta lista é mantida manualmente. Quando adicionar um novo arquivo
de documentação, inclua-o aqui e considere atualizar o checklist de revisão
do projeto conforme necessário.
