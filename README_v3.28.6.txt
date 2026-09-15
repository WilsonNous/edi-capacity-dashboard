EDNNA v3.28.6 — CENTRAL DE ATUAÇÃO E CONTEXTO OPERACIONAL

Objetivo
- Generalizar a antiga Central de Cancelamentos para Central de Atuação EDNNA.
- Manter chamados já assumidos pela EDNNA disponíveis para análise mesmo após saírem do primeiro combate.
- Usar BP/Novo Cliente como raiz histórica para reconstruir o contexto operacional.
- Reaproveitar a mesma inteligência para abertura, inclusão, alteração, falta de arquivo, cancelamento e futuras regras homologadas.

Arquitetura
Chamado atual -> relações diretas -> BP/Novo Cliente -> relações do BP -> linha do tempo por player.

Princípios
- BP é raiz histórica, não verdade absoluta atual.
- Eventos posteriores podem alterar o estado conhecido.
- Cada informação mantém a proveniência no chamado Redmine.
- Contexto é somente leitura; execução continua dependendo do catálogo homologado.
- Cancelamento mantém o orquestrador por player da v3.28.5.

Central de Atuação
A carteira é formada pela união de:
1. chamados atribuídos formalmente à EDNNA no snapshot global;
2. chamados presentes na inteligência/classificação EDNNA.

Isso mantém casos como MAIS CAMPUS #48567 acessíveis para contexto mesmo depois de a EDNNA assumir o chamado e alterar seu estado.

Arquivos alterados
- app.py
- ednna/contexto_relacionamentos.py
- ui/ednna_workspace.py
- README_v3.28.6.txt

Deploy
Substituir somente estes arquivos no repositório e realizar um único commit/deploy.
