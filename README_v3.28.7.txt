EDNNA v3.28.7 — Memória Operacional e Reconciliação de Retornos

Objetivos
1. Reduzir a pressão sobre o Redmine durante a reconstrução de contexto histórico.
2. Recuperar automaticamente cancelamentos GETNET cujo e-mail foi enviado, mas que ficaram fora de acoes_operacionais/monitoramento.
3. Permitir que respostas já existentes na Inbox, como o retorno do #48567 MAIS CAMPUS, voltem ao fluxo normal da EDNNA e atualizem o Redmine.

Alterações
- contexto_relacionamentos.py
  * cache de chamados abertos: 120 minutos
  * cache de histórico concluído: 7 dias
  * mantém fallback stale e circuit breaker já existentes
- orquestrador_cancelamentos.py
  * nova listagem global de etapas GETNET enviadas/aguardando retorno
- email_sender.py
  * nova busca de mensagem enviada pelo #ID do chamado na pasta Sent Items
- monitor_respostas.py
  * reconciliação antes de cada ciclo normal
  * se uma etapa GETNET está aguardando e não existe acompanhamento local, localiza o envio e reconstrói a ação
  * em seguida o mesmo ciclo localiza a resposta, interpreta GETNET e registra no Redmine
  * confirmação GETNET encerra somente a etapa GETNET; demais players mantêm o chamado com a EDNNA
- app.py
  * identificação da versão atualizada

Validação esperada para #48567
No primeiro ciclo após o deploy, caso a etapa GETNET esteja AGUARDANDO_RESPOSTA no orquestrador, espera-se log semelhante a:
[EDNNA] Monitor e-mail | reconciliação | chamado=48567 | acompanhamento reconstruído
[EDNNA] Monitor e-mail | reconciliação | chamado=48567 | resposta já localizada
[EDNNA] Monitor e-mail | resposta recebida | chamado=48567 | regra=CANCELAMENTO-GETNET-001 | de=...

O Redmine deve receber somente o conteúdo novo da resposta da GETNET, manter Estado=Em andamento e manter a EDNNA como responsável enquanto houver outras etapas externas pendentes.
