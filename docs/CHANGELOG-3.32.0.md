# EDNNA 3.32.0

## Central de Operação
- `Operação de hoje` passa a ser a central de interação humana com quatro áreas: **Preciso de você**, **Estou cuidando**, **Fiz / acompanhei** e **Não consegui continuar**.
- Regras automáticas prontas deixam de ser apresentadas como tarefa manual.
- Follow-ups automáticos continuam sob responsabilidade do worker; somente follow-ups assistidos oferecem botão.
- Acompanhamentos persistidos exibem chamado, cliente, origem, última atuação, prazo e próxima ação.
- Reconciliações Redmine aparecem como exceção técnica e nunca provocam reenvio de e-mail.

## Descoberta e SENFF
- Snapshot operacional agora preserva `Descrição`, `Origem` e `Alterado` do Redmine.
- O campo estruturado **Origem** passa a ter precedência quando identifica univocamente o player.
- Botão **Atualizar fila agora** força sincronização real do snapshot `status=open` antes do recálculo.
- Novo diagnóstico **Rastrear um chamado** informa se o chamado está no snapshot e se foi descoberto pelo motor.
- Caso de referência #49286 validado em teste sintético como `SENFF` / inclusão.

## Resiliência
- Navegação comum continua local-first; somente atualização explícita força consulta ao Redmine.
- Falha no refresh mantém a última fotografia válida.
