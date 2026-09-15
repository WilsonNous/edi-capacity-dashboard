EDNNA v3.28.7.3 — Reconciliação Idempotente + Diagnóstico

Objetivo
- Fechar o ciclo de retorno de cancelamentos GETNET, especialmente #48567 MAIS CAMPUS.

Ajustes
1. RESPOSTA_RECEBIDA e RESPOSTA_PENDENTE_REDMINE não são mais contados como órfãos.
2. Registros presos em ENVIANDO são recuperados quando o envio real existe em Sent Items.
3. Sent Items é tratado como evidência de envio e fonte de reconstrução.
4. Logs detalhados mostram cada estágio: Sent Items, reconstrução, busca Inbox e resposta.
5. Busca direta de resposta por #chamado amplia a janela da Inbox para 500 mensagens.
6. Mantida fila resiliente de sincronização Redmine da v3.28.7.2.

Arquivos
- ednna/monitor_respostas.py
- ednna/email_sender.py
- ednna/acompanhamento_acoes.py

Validação
- py_compile executado com sucesso.

Log esperado para #48567
[EDNNA] Reconciliação | avaliando chamado=48567 | estado_sqlite=...
[EDNNA] Reconciliação | Sent Items HIT | chamado=48567 | ...
[EDNNA] Reconciliação | enviado localizado | chamado=48567
[EDNNA] Reconciliação | ENVIANDO recuperado ... (se estava preso em ENVIANDO)
[EDNNA] Reconciliação | buscando Inbox | chamado=48567 | ...
[EDNNA] Reconciliação | resposta localizada | chamado=48567 | ...
