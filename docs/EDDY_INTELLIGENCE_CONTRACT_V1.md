# EDDY Intelligence Contract v1

## Objetivo
Expor o EDDY como especialista EDI para a EDNNA sem permitir acesso direto ao banco ou espalhar conhecimento do orquestrador pelo domínio EDI.

## Fronteira
API/Contract -> Application Service -> EDI Domain -> integrações/banco/Redmine/players.

## Query v1
- edi.status.get: ligado ao snapshot operacional existente.
- edi.issue.inspect: reutiliza o gateway Redmine existente.
- edi.player.inspect: contrato disponível, resposta conservadora até existir visão agregada canônica.
- edi.rule.list: consulta pontual por rule_id; listagem consolidada ainda não inventada.

## Action
edi.operation.execute existe apenas em dry-run. Live retorna 403. O lookup por idempotency_key é somente leitura e nunca reexecuta.

## Segurança
Bearer token via EDDY_INTELLIGENCE_TOKEN. Nenhum segredo no repositório. Contrato exige X-EDNNA-Contract-Version: 1.

## Deploy
A aplicação atual é Streamlit. Esta API FastAPI deve ser publicada como processo/serviço separado ou via arquitetura Azure que exponha ambos. Não alterar o startup do Streamlit antes de definir essa topologia. Para desenvolvimento: uvicorn eddy_api.main:app.

## Próximos incrementos
1. persistência de action/idempotency antes de qualquer execução live;
2. catálogo canônico para edi.rule.list;
3. visão agregada baseada em evidências para edi.player.inspect;
4. autenticação service-to-service gerenciada quando a topologia Azure for definida.
