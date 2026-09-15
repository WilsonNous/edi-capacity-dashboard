EDNNA v3.28.7.2 — Reconciliação por E-mail + Fila Resiliente Redmine
Data: 15/09/2026

OBJETIVO
- Recuperar atuações GETNET a partir de Sent Items mesmo quando o snapshot Redmine estiver antigo/indisponível.
- Evitar que chamados já processados, como #30846, sejam processados novamente.
- Recuperar o legado #48567 MAIS CAMPUS pelo #ID presente no assunto do e-mail.
- Persistir a resposta da adquirente no SQLite antes de tentar atualizar o Redmine.
- Repetir a sincronização com o Redmine em ciclos posteriores sem reler/processar a mesma resposta.

ALTERAÇÕES
1. email_sender.py
   - listar_envios_cancelamento_getnet(): descobre envios GETNET/cancelamento em Sent Items e extrai #chamado.
   - Busca local, sem filtros complexos do Graph/InefficientFilter.

2. acompanhamento_acoes.py
   - confirmar_envio_real() aceita enviado_em_real para preservar a data real do envio reconstruído.
   - novo estado RESPOSTA_PENDENTE_REDMINE.
   - persistência e fila de respostas aguardando sincronização Redmine.

3. monitor_respostas.py
   - candidatos = orquestrador + snapshot + Sent Items.
   - idempotência por estado local.
   - resposta é salva antes do PUT/nota Redmine.
   - se Redmine falhar, a resposta permanece em fila e é sincronizada posteriormente.

LOGS ESPERADOS PARA #48567
[EDNNA] Reconciliação | enviados_descobertos=N | candidatos=N | ...
[EDNNA] Reconciliação | avaliando chamado=48567
[EDNNA] Reconciliação | enviado localizado | chamado=48567
[EDNNA] Reconciliação | acompanhamento reconstruído | chamado=48567
[EDNNA] Reconciliação | resposta localizada | chamado=48567
[EDNNA] Monitor e-mail | resposta recebida | chamado=48567 | regra=CANCELAMENTO-GETNET-001

SE REDMINE ESTIVER FORA
[EDNNA] Monitor e-mail | resposta preservada | chamado=48567 | Redmine pendente: ...
Em ciclo posterior:
[EDNNA] Redmine pendente | sincronizado | chamado=48567

DEPLOY
Substituir preservando os caminhos:
- ednna/monitor_respostas.py
- ednna/acompanhamento_acoes.py
- ednna/email_sender.py
- README_v3.28.7.2.txt
