# Checklist de Fechamento de História

Use este checklist sempre que uma história (story) for concluída. O objetivo é garantir que todos os artefatos necessários foram atualizados e que o item pode ser considerado `completed` no tracking.

- [ ] Código implementado e coberto por testes unitários.
- [ ] Testes de integração (quando aplicável) foram adicionados e passam.
- [ ] Atualizar `docs/implementation-artifacts/<story-key>.md` com notas de desenvolvimento (Dev Notes, desafios, decisões).
- [ ] Se houver migração de banco, adicionar arquivo SQL em `migrations/` e certificar que `apply_migrations` aplica sem erro.
- [ ] Atualizar `sprint-status.yaml` para refletir o status `completed`.
- [ ] Registrar qualquer saída de dados ou artefato gerado (`snapshots/`, `reports/`, etc.).
- [ ] Validar artefatos gerados (ex.: cálculos de checksum, arquivos CSV/JSON) manualmente ou via testes automatizados.
- [ ] Atualizar documentação relevante (`docs/playbooks/*`, `README.md`, etc.) com novo comando ou mudança de processo.
- [ ] Adicionar notas no pull request descrevendo como a história foi validada e qualquer dependência para epics futuros.
- [ ] Marcar o owner da história como responsável por monitorar ações de acompanhamento (se houver) e atualizar o campo `owner` no arquivo de história.

> **Dica**: inclua este checklist na descrição do PR usando `docs/playbooks/story-close-checklist.md` como referência ou copiando o conteúdo diretamente.
