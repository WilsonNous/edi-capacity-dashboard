EDNNA v3.28.5 — Orquestrador de Cancelamentos por Player

Objetivo
- Tratar cancelamentos totais como um conjunto de etapas independentes por player/adquirente.
- Manter a EDNNA responsável enquanto houver etapas externas pendentes.
- Devolver ao responsável humano original somente quando todas as etapas externas conhecidas estiverem concluídas.

Principais mudanças
1. Nova tabela SQLite cancelamento_etapas em ednna.db, uma linha por chamado + player.
2. O planejador sincroniza as etapas com o catálogo operacional. Uma nova regra de cancelamento homologada passa a ser reconhecida na próxima reconstrução do plano, sem regra fixa de sequência no orquestrador.
3. GETNET é a primeira etapa executável real. Após envio, a etapa fica AGUARDANDO_RESPOSTA.
4. Retorno GETNET com confirmação de desativação/cancelamento marca somente GETNET como CANCELAMENTO_CONFIRMADO.
5. Em cancelamento com outros players pendentes, o chamado continua atribuído à EDNNA e em Em andamento.
6. Se todas as etapas externas estiverem concluídas, o chamado volta ao responsável humano original preservado e permanece Em andamento para ações internas/físicas.
7. A Central de Cancelamentos mostra o progresso por player.

Segurança
- PROCEDIMENTO_NAO_HOMOLOGADO nunca é tratado como concluído.
- Não há fechamento automático do chamado.
- Novas adquirentes só se tornam executáveis quando houver regra homologada no catálogo e preparação operacional correspondente.
- O handoff usa somente o responsável original previamente preservado pela EDNNA.

Arquivos alterados
- app.py
- ednna/acompanhamento_acoes.py
- ednna/monitor_respostas.py
- ednna/planejador_cancelamentos.py
- ednna/redmine_writer.py
- ui/ednna_workspace.py

Arquivo novo
- ednna/orquestrador_cancelamentos.py
