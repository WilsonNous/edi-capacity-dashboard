# EDNNA 3.32.6

## Segurança operacional
- Corrige incompatibilidade da chamada `footer()` na Central Operação.
- Restringe estados terminais aos estados comprovados na operação Netunna: Rejeitada, Concluído, Cancelado e Fechado (com variações de gênero/acentuação).
- Remove inferência terminal por `closed_on` e os estados `Resolvido/Resolvida`, que não tinham semântica comprovada neste contexto.
- Adiciona barreira fail-safe no nível do `email_sender`: todo envio Graph e todo `replyAll` exige `chamado_id` e executa pre-flight fresco no Redmine imediatamente antes do efeito externo.
- Falha/indisponibilidade do pre-flight bloqueia o envio.
- Decisões de pre-flight passam a ser registradas em `auditoria_preflight` no SQLite.
- Chamados terminais têm acompanhamentos pendentes inativados sem apagar histórico.

## Follow-up / observabilidade
- Corrige contagem do worker: `followups_enviados` só aumenta quando o envio realmente retorna `ok=True`.
- Passa a distinguir follow-ups bloqueados e falhos no resumo do ciclo, evitando registrar como enviado um follow-up barrado pelo pre-flight.

## Compatibilidade
- Todos os chamadores conhecidos de `enviar_email_graph` e `responder_todos_email_graph` foram atualizados para informar o chamado correspondente.
- Fluxo Greencard existente foi preservado.
