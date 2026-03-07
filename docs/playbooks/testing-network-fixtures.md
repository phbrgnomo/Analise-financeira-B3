# Playbook: Fixtures e Mocks para Testes de Rede

Objetivo: reduzir flakiness dos testes que dependem de rede, fornecendo um modo `playback` determinístico
e um modo `record` para atualizar gravações quando necessário.

Resumo rápido
- Padrão de execução em CI: `NETWORK_MODE=playback` (sem rede)
- Para atualizar gravações locais: `NETWORK_MODE=record pytest tests/...`

Arquivos criados
- `tests/fixtures/network/conftest.py`: fixtures pytest com `mock_yfinance_data` (autouse opcional)
- `tests/fixtures/sample_ticker.csv`: dados de exemplo usados em playback (já presente no repositório)

Como usar
1. Rodar testes isolados (sem rede):

```bash
pytest
```

2. Atualizar gravações (usar com cuidado):

```bash
NETWORK_MODE=record pytest tests/adapters/test_adapters.py::TestYFinanceAdapter::test_fetch
```

Recomendações
- Execute `record` apenas em ambiente controlado (máquina de desenvolvedor ou job CI específico).
- Adicione job CI que rode periodicamente com `NETWORK_MODE=record` em branch protegido para validar mudanças de contrato.
- Priorize uso de fixtures em testes unitários; reserve `record` para testes de contrato/integration.

Critérios de aceitação
- Testes em CI passam consistentemente sem depender de rede (playback).
- Documentação clara de como atualizar gravações.
