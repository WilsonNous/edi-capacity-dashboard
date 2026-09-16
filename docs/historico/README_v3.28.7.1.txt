EDNNA v3.28.7.1 — Reconciliação de Órfãos

Objetivo
- Recuperar acompanhamentos de cancelamento GETNET que foram enviados antes da criação do orquestrador ou que ficaram sem ação local elegível.

Mudanças
- O monitor não depende mais apenas de cancelamento_etapas para descobrir o que deve reconciliar.
- Usa o snapshot persistido da EDNNA para localizar chamados de cancelamento GETNET atribuídos à EDNNA.
- Compara candidatos com a fila local de acompanhamento.
- Para órfãos, procura o e-mail real em Sent Items pelo #ID do chamado.
- Se o envio existe, recria a etapa GETNET como AGUARDANDO_RESPOSTA e reconstrói a ação operacional.
- Procura resposta posterior na Inbox; o ciclo normal processa a resposta e atualiza o Redmine.
- Inclui logs explícitos do funil de reconciliação.

Caso de homologação
- #48567 MAIS CAMPUS: o assunto enviado e a resposta GETNET contêm #48567. A resposta de confirmação deve ser detectada, registrada no Redmine e concluir somente a etapa GETNET. O chamado permanece com EDNNA / Em andamento enquanto houver outros players externos pendentes.
