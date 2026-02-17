---
title: "3-6 Documentar expected outputs e paths no README e notebooks"
story: 3-6-documentar-expected-outputs-e-paths-no-readme-e-notebooks
status: ready-for-dev
---

# Story 3.6: documentar-expected-outputs-e-paths-no-readme-e-notebooks

Status: ready-for-dev

## Story

Como mantenedor do projeto,
eu quero documentar explicitamente os outputs esperados, caminhos de arquivos e convenções no README e nos notebooks,
para que desenvolvedores e analistas reproduzam resultados de forma confiável e saibam onde os artefatos são gerados.

## Acceptance Criteria

1. O README principal contém uma seção "Expected outputs" listando todos os arquivos gerados (CSV/plots/notebooks) e seus caminhos relativos em `dados/` e `docs/`.
2. Notebooks de exemplo (em `docs/` ou `examples/`) têm células de introdução que apontam para os paths esperados e mostram como reproduzir os artefatos.
3. Todas as ferramentas/steps que escrevem arquivos (ex.: coleta de dados, transformação de retornos) têm seus destinos e formatos documentados (colunas esperadas, nomes de arquivo, ordenação temporal).
4. Há um pequeno exemplo passo-a-passo para reproduzir um run (com comandos `poetry run main` ou `python -m src.main`) que gera ao menos um CSV de saída esperado.
5. As convenções de nomeação de arquivos e separador de datas estão documentadas (ex.: sufixo `.SA` para ativos B3; formato YYYY-MM-DD).

## Tasks / Subtasks

- [ ] Atualizar `README.md` com seção "Expected outputs" e exemplos de comandos.
  - [ ] Listar cada CSV/artefato gerado, caminho relativo e esquema de coluna.
- [ ] Atualizar notebooks de exemplo em `docs/` e `examples/` com comentários sobre onde os outputs são gravados.
  - [ ] Adicionar célula de verificação que valida existência e colunas do CSV de exemplo.
- [ ] Revisar chamadas em `src/` que escrevem/esperam arquivos e anotar seus paths na documentação.
- [ ] Adicionar seção de "Reproducing results" com comandos mínimos e expectativas.

## Dev Notes

- Use as convenções já presentes no projeto: ativos B3 com sufixo `.SA`, datas em `YYYY-MM-DD` e `252` dias úteis para anualização.
- Saída canônica dos retornos: CSVs em `dados/{TICKER}.csv` com coluna `Return` para cada ativo.
- Evitar mudanças no código que alterem paths sem atualizar o README; preferir variáveis de ambiente ou constantes centrais se precisar mudar.

### Project Structure Notes

- Paths relevantes:
  - Dados brutos / persistidos: `dados/` (CSV por ativo com coluna `Return`)
  - Implementação e módulos: `src/` (ex.: `src/dados_b3.py`, `src/retorno.py`)
  - Artefatos de documentação e histórias: `docs/` e `docs/implementation-artifacts/`
- Detectadas diferenças: nenhum padrão divergente encontrado nos arquivos principais; manter convenções do `pyproject.toml` e scripts de exemplo.

### References

- Source: [docs/planning-artifacts](docs/planning-artifacts) — epics e PRD relacionados a organização de outputs
- Source: `src/main.py`, `src/dados_b3.py`, `src/retorno.py` — pontos onde arquivos são lidos/gravas

## Dev Agent Record

### Agent Model Used

GPT-5 mini

### Debug Log References

- Documento gerado automaticamente via workflow `create-story` (modo YOLO).

### Completion Notes List

- Análise de contexto aplicada: conventions de arquivos, locais de saída, e comandos de execução.

### File List

- docs/implementation-artifacts/3-6-documentar-expected-outputs-e-paths-no-readme-e-notebooks.md

Issue: https://github.com/phbrgnomo/Analise-financeira-B3/issues/134
