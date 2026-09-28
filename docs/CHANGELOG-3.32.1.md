# EDNNA v3.32.1 — Autonomia operacional

- Worker de background passa a ser iniciado pela Home e por qualquer tela operacional, não apenas pelo Painel EDI.
- Sincronização de journals/histórico passa a ser executada automaticamente pelo worker antes da avaliação de inclusões automáticas.
- `AGUARDANDO_VERIFICACAO_HISTORICO` deixa de ser interação humana e passa para **Estou cuidando**.
- Pendências Redmine com menos de 3 tentativas ficam em reconciliação automática; após 3 falhas aparecem como exceção, sem risco de reenvio.
- **Preciso de você** fica restrito a decisões/ações humanas reais: dados, destinatário, homologação, autorização e atuação assistida.
- **Estou cuidando** mostra também sincronizações de histórico e reconciliações técnicas em andamento.
- Acompanhamentos exibem prazo vencido e deixam explícito que o follow-up será executado pelo worker.
- Reconciliação manual foi removida da Central de Operação como obrigação do operador.
