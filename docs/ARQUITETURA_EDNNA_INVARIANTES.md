# EDNNA — invariantes operacionais permanentes

## Redmine

1. Toda transição de status deve passar por pre-flight de workflow.
2. `start_date` e `due_date` nunca podem ser enviados vazios.
3. Se `start_date` já existir no chamado, deve ser preservado. Se estiver vazio, usar a data da primeira atuação real da EDNNA.
4. Se `due_date` já existir, preservar quando aplicável. Se estiver vazio, usar o prazo operacional da regra; na ausência, 2 dias úteis.
5. Falha de Redmine após envio de e-mail nunca autoriza reenvio do e-mail. A pendência é exclusivamente de reconciliação Redmine.

## Evidência de e-mail

1. HTTP 202 do Microsoft Graph é evidência de aceitação do envio.
2. Sent Items é a fonte de verdade para reconstrução histórica de mensagens já enviadas.
3. Ao reparar chamados antigos, recuperar e-mail inicial e follow-ups reais, em ordem cronológica, sem reconstruir o texto a partir de template.
4. Cada mensagem recuperada recebe marcador idempotente `[EDNNA-EVIDENCIA:<internetMessageId>]` no journal do Redmine.
5. O reconciliador nunca dispara e-mail.

## Follow-up

1. Follow-up usa `replyAll` e preserva a thread.
2. Follow-up só altera o contador após o Graph aceitar a mensagem.
3. O journal do follow-up e o status do chamado são efeitos pós-envio reconciliáveis.

## Interface

1. Número de chamado permanece clicável.
2. Cliente, tipo/origem e usuário devem ser exibidos por nome; IDs são apenas fallback técnico e não apresentação final.
3. Cards e botões seguem proporções consistentes em todas as telas da EDNNA.
