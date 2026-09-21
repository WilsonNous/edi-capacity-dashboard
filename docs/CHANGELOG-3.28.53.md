# EDNNA v3.28.53

- Evidência pós-envio: HTTP 202 + tentativa de confirmação em Sent Items.
- Log explícito `SENT_ITEMS_CONFIRMED`, `SENT_ITEMS_PENDING` ou `SENT_ITEMS_CHECK_ERROR`.
- Home deixa de oferecer novo envio quando há evidência de envio.
- Exibe evidência Graph e data registrada.
- Botão **Reconciliar Redmine agora** atua somente no Redmine e nunca reenvia e-mail.
- Exibe o último erro da fila Redmine para diagnóstico operacional.
- Mantém as regras TICKET/TRIOCARD e a extração contextual da v3.28.52.
