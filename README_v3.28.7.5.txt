EDNNA v3.28.7.5 — Auditoria de Conclusão / Autorreparo

- Audita ações GETNET marcadas RESPOSTA_RECEBIDA contra o histórico real do Redmine.
- Se a nota EDNNA de retorno não existir, converte somente a sincronização para RESPOSTA_PENDENTE_REDMINE.
- Reutiliza resposta já persistida; não reenvia e-mail e não reinterpreta a mensagem.
- Em seguida, a fila normal de pendências tenta reparar o Redmine no mesmo ciclo.
- Se o Redmine estiver indisponível, não altera o estado confirmado localmente por hipótese.
- Logs: confirmados_ids, reparo_pendente_ids, indisponiveis_ids.
