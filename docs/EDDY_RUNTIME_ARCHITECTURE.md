# EDDY Runtime Architecture

## Pilares
Toda evolução deve preservar: **segurança, performance, escalabilidade e flexibilidade**.

## Fase atual
Um único Azure App Service mantém o armazenamento persistente em `/home/data`.

- Gateway público: porta 8000.
- Streamlit: loopback 8501.
- Intelligence API: loopback 8001.
- Somente o Streamlit inicia o runtime operacional/worker.
- Intelligence API permanece QUERY/read-only; ACTION live continua bloqueada.
- `ednna.db` e `painel.db` continuam no armazenamento persistente atual.

## Roteamento
- `/api/intelligence/*` -> FastAPI.
- demais caminhos -> Streamlit.
- `/healthz` -> gateway, validando Streamlit e Intelligence API.\n- conexões WebSocket do Streamlit são encaminhadas ao processo interno em `:8501`.

## Falha segura
O script de startup supervisiona os três processos. Se um processo crítico morrer, o processo principal encerra para permitir que o App Service recicle a aplicação.

## Evolução
Quando a persistência sair de SQLite local para um banco compartilhável, UI, API e worker poderão ser separados fisicamente sem alterar o contrato EDNNA <-> EDDY.

## WebSocket e saúde\nO gateway suporta o canal WebSocket usado pelo Streamlit e preserva cookies/headers de autenticação relevantes. O health check retorna 503 se Streamlit ou Intelligence API não responderem. A API pode responder 401/422 no probe sem credencial; isso comprova que o processo está vivo sem armazenar segredo no gateway.\n\n## Produção
Não alterar o Startup Command do Azure antes de validar esta topologia em ambiente controlado. O comando atual de produção permanece a referência até aprovação explícita.
