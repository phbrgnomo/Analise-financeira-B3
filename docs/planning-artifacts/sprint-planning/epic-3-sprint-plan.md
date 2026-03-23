## Priorização

**Prioridade Alta (implantar primeiro)**
- Story 3.1 Quickstart CLI — peça central para demos/CI smoke; depende dos mínimos das Epics 0/1/2. Priorizar integração com fixtures `--no-network` para CI.
- Story 3.4 Health/metrics CLI — útil para operações e para CI monitoramento.
- Story 3.5 Examples / reproducible scripts — facilita verificação local/CI; pode acompanhar 3.1.
**Prioridade Média-Alta**
- Story 3.2 Notebooks parametrizáveis — alto valor para pesquisadores; depende de dados/data.db pronto.
**Prioridade Média**
- Story 3.3 Streamlit POC — valioso para demos, mas é POC; pode ser agendado após core quickstart e notebooks (menor risco se postergado).
**Prioridade Média-Baixa**
- Story 3.6 Documentação README + paths — necessário para onboarding imediato (empodera novos contribuintes).

Racional: Quickstart CLI (3.1) é o ponto de integração que demonstra que Epics 0/1/2 funcionam juntos — habilita validação do produto com stakeholders; docs e CI smoke dão confiança e reduzem risco.
