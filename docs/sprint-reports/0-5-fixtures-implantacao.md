---
story: 0.5
title: Implantação — Fixtures de teste e CSV de amostra
author: Phbr
date: 2026-02-18
files:
  - tests/fixtures/sample_ticker.csv
  - tests/fixtures/sample_ticker_multi.csv
  - tests/fixtures/README.md
  - tests/conftest.py
  - tests/test_sample_fixture.py
  - tests/test_fixture_multi.py
  - tests/test_sample_db_multi_integration.py
summary: |
  Implementação de fixtures e dados de amostra para suportar testes determinísticos.
  Inclui CSV de exemplo, documentação das fixtures, fixture `sample_db` que popula um
  SQLite em memória e testes de exemplo que validam a integração básica.

---

# Relatório de implantação — Story 0.5

## Objetivo

Adicionar fixtures e um CSV de amostra para permitir que os testes unitários e de
integração rodem de maneira determinística e rápida (in‑repo, sem dependências externas).

## O que foi implementado

- `tests/fixtures/sample_ticker.csv`: CSV de amostra com 5 linhas para `PETR4.SA`.
- `tests/fixtures/README.md`: documentação da fixture e exemplo de uso do fixture `sample_db`.
- `tests/conftest.py`: fixture `sample_db` que cria um banco SQLite in‑memory, cria a
  tabela `prices` e popula com as linhas do CSV.
- `tests/test_sample_fixture.py`: dois testes de exemplo que consomem `sample_db`:
  - valida contagem de linhas (5)
  - valida valor de `close` para uma data conhecida
 - `tests/fixtures/sample_ticker_multi.csv`: CSV adicional com múltiplos tickers (ex.: `PETR4.SA`, `VALE3.SA`) e uma linha com `ticker` vazio para testar casos de borda.
 - `tests/test_fixture_multi.py`: teste que valida parsing e casos de borda do CSV multi-ticker.
 - `tests/test_sample_db_multi_integration.py`: teste de integração que popula um SQLite in-memory com o CSV multi-ticker e executa consultas de validação.

## Mapeamento para critérios de aceitação

 - AC1: testes que dependem do fixture — SATISFEITO. Adicionamos testes de exemplo e de integração que
   usam `sample_db` e foram executados com sucesso (local): `poetry run pytest -q` → 8 passed, 10 warnings.
- AC2: CSV pequeno e documentado — SATISFEITO. `tests/fixtures/sample_ticker.csv` possui
  5 linhas e `tests/fixtures/README.md` documenta sua finalidade e uso (inclui snippet).
- AC3: `tests/conftest.py` expõe fixture que carrega o CSV em SQLite in‑memory — SATISFEITO.

## Como reproduzir localmente

1. Instale dependências:

```bash
poetry install
```

2. Rode a suíte de testes:

```bash
poetry run pytest -q
```

3. Teste manual do fixture (exemplo rápido): execute o snippet presente em
   [tests/fixtures/README.md](tests/fixtures/README.md).

Evidência local (exemplo de saída):

```text
$ poetry run pytest -q
........
8 passed, 10 warnings in 0.82s
```

## Decisões e justificativas

- Usei apenas stdlib (`csv`, `sqlite3`) na fixture para minimizar dependências de
  tempo de execução nos testes e garantir portabilidade em CI.
- Mantive o CSV intencionalmente pequeno (5 linhas) para garantir testes rápidos.
- Adicionei um teste de exemplo para cobrir AC1; a equipe pode estender com testes
  de integração adicionais que simulem casos de borda.
 - Ajustes na fixture `sample_db`: agora declarada com `@pytest.fixture(scope="function")` e usando `yield` com `db.close()` no teardown para garantir que a conexão seja fechada após cada teste. Isso evita vazamento de conexões e efeitos colaterais quando múltiplos cursores são usados.
 - Adicionado `tests/fixtures/sample_ticker_multi.csv` para validar múltiplos tickers e casos de borda (linha com `ticker` vazio). Foram incluídos testes unitários e um teste de integração para garantir comportamento consistente ao inserir no SQLite.

## Checklist de entrega (FR28)

- [x] Arquivos de fixtures adicionados ao repositório (incluindo `sample_ticker_multi.csv`).
- [x] Documentação da fixture atualizada em `tests/fixtures/README.md`.
- [x] Fixture `sample_db` implementada/atualizada em `tests/conftest.py` (agora `scope="function"` com teardown seguro).
- [x] Testes de exemplo e integração adicionados e executados com sucesso localmente (`8 passed, 10 warnings`).
- [x] Relatório de implantação criado/atualizado (`docs/sprint-reports/0-5-fixtures-implantacao.md`).

## Próximos passos sugeridos

- Opcional: criar testes de integração que utilizem adaptadores (p.ex. conversão
  para pandas) se o código do projeto exigir DataFrame para consumo.
- Opcional: adicionar uma entrada rápida no `README.md` do projeto apontando para
  os fixtures e como reproduzir os testes localmente.

---

Arquivo gerado automaticamente para cumprir FR28 — documentação de implantação da story 0.5.
