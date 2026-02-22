# Brainstorming Report — Analise-financeira-B3

Facilitador: Phbr
Data: 2026-02-15T17:41:00Z

Tema da sessão
- Definir objetivo e escopo do repositório: ferramenta de aprendizado para coleta e análise de dados da B3.

Objetivos principais
1. Confirmar o escopo educacional.
2. Priorizar implementações (coleta de preços, cálculo de retornos/risco, correlações, carteiras).
3. Gerar backlog e próximos passos com artefatos para implementação e aprendizado.

Técnicas utilizadas
- Mind Mapping (Estruturada)
- Morphological Analysis (Deep)
- Decision Tree Mapping (Estruturada)

Decisões-chave e recomendações
- Fontes de dados: Yahoo e outras fontes gratuitas como primeira prioridade; documentar fallback e limitações.
- Frequência: Diário (não há necessidade de intraday neste escopo inicial).
- Formato/armazenamento: Migrar para SQLite (tabela 'prices' e 'returns', indexar por ticker+date) para facilitar ingestão incremental, consultas e portabilidade.
- Visualização: Dashboard interativo (Streamlit + Plotly) como submódulo do módulo Visualização & Relatórios para explorar dados, gerar carteiras modelo e projetar volatilidade.

Priorização recomendada (próximos passos)
1. Implementar camada DB (db.write_prices / db.read_prices / db.append_prices) — Issue: #15
2. Implementar pipeline de coleta com pandas-datareader (.SA) e ingestão incremental — Issue: #2
3. Implementar cálculo de retornos e persistência em SQLite — Issue: #16
4. Adicionar testes de integridade e checks CI para o DB — Issue: #18
5. Prototipar Streamlit POC e adaptar utilitários de visualização para SQLite — Issues: #14, #17

Artefatos gerados
- Backlog atualizado: docs/planning-artifacts/backlog.md
- Documento de sessão: docs/brainstorming/brainstorming-session-20260215-145405.md
- Issues criadas: #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18

Próxima ação sugerida


Observações finais
- Este relatório resume a sessão de brainstorming e contém links/IDs das issues e artefatos gerados; quaisquer alterações de prioridade podem ser aplicadas diretamente no backlog ou nas issues do GitHub.
