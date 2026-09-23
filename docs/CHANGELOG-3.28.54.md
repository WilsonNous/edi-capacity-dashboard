# EDNNA v3.28.54

- Follow-up Graph migrado de `createReplyAll` + draft para `replyAll` direto (Mail.Send), eliminando dependência de Mail.ReadWrite.
- Todo follow-up enviado passa a gerar journal no Redmine e manter o status de espera; falhas entram na outbox sem reenviar e-mail.
- Pós-envio automático passa a usar outbox transacional do Redmine; e-mail aceito pelo Graph nunca é repetido por falha de journal/status.
- Regras executáveis que já possuem envio confirmado pelo Graph podem ser promovidas automaticamente (`EDNNA_AUTO_TRUST_PREVIOUS_SEND=true`).
- Inclusões homologadas/autorizadas cuja mesma regra já teve envio confirmado podem operar automaticamente (`EDNNA_INCLUSOES_AUTO=true`).
- Executor automático passou a rodar também no worker de background, sem depender de abrir/recarregar a interface.
- CC operacional padronizado em BPO + EDI + Consultores.
- Limites de segurança: `EDNNA_AUTO_MAX_PER_RUN` e `EDNNA_INCLUSOES_AUTO_MAX_PER_CYCLE`.
