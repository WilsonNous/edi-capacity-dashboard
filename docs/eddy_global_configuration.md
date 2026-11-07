# EDDY | Configuracao global (migracao VR01)

As configuracoes operacionais passam a ser compartilhadas entre regras.
A camada `ednna.eddy_global_config` reconhece os nomes globais abaixo.

| Legada VR01 | Global |
| --- | --- |
| EDDY_VR01_EXTERNAL_ENABLED | EDDY_EXTERNAL_ENABLED |
| EDDY_VR01_INTERVAL_SECONDS | EDDY_INTERVAL_SECONDS |
| EDDY_VR01_TRANSPORT_MYSQL_READY | EDDY_TRANSPORT_MYSQL_READY |
| EDDY_VR01_RECIPIENT_RESOLVER_READY | EDDY_RECIPIENT_RESOLVER_READY |
| EDDY_VR01_REPLY_RECONCILIATION_READY | EDDY_REPLY_RECONCILIATION_READY |
| EDDY_VR01_REDMINE_MYSQL_AUDIT_READY | EDDY_REDMINE_MYSQL_AUDIT_READY |
| EDDY_VR01_PORTFOLIO_ENABLED | EDDY_PORTFOLIO_ENABLED |
| EDDY_VR01_PORTFOLIO_INTERNAL_ADVANCE | EDDY_INTERNAL_ADVANCE_ENABLED |
| EDDY_VR01_AUTO_SEND_PORTAL | EDDY_AUTO_SEND_ENABLED |

**Precedencia:** se a variavel legada estiver explicitamente definida, ela prevalece,
inclusive quando definida como `false`. Na ausencia dela, usa-se a global.
Nenhuma flag de homologacao e automaticamente habilitada.

**Escopo:** esta mudanca centraliza a leitura de flags na prontidao VR01,
no scheduler e na ponte de carteira. Nao equivale a uma homologacao da
integracao Graph/Redmine ou a uma liberacao automatica em producao.

**Evolucao:** regras por adquirente (modelos, prazos, dados de contato e
identificacao) devem ser parametrizadas em armazenamento persistente;
segredos e infraestrutura permanecem na configuracao de ambiente.
