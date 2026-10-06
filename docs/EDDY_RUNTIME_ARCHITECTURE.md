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
- `/healthz` -> gateway.

## Falha segura
O script de startup supervisiona os três processos. Se um processo crítico morrer, o processo principal encerra para permitir que o App Service recicle a aplicação.

## Evolução
Quando a persistência sair de SQLite local para um banco compartilhável, UI, API e worker poderão ser separados fisicamente sem alterar o contrato EDNNA <-> EDDY.

## Produção
Não alterar o Startup Command do Azure antes de validar esta topologia em ambiente controlado. O comando atual de produção permanece a referência até aprovação explícita.
