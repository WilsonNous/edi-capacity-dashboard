EDNNA v3.28.1 — Limpeza de Retornos + Carteira EDNNA + Disparo GETNET
Data: 15/09/2026

Arquivos alterados nesta atualização:
- ednna/monitor_respostas.py
- ednna/planejador_cancelamentos.py
- ui/ednna_workspace.py

1) Retornos de e-mail
- O journal do Redmine passa a registrar somente a parte nova da resposta da adquirente.
- Remove blocos citados iniciados por "Mensagem original", "Original Message" ou cabeçalhos Outlook De/Enviado/Para.
- Mantém remetente, assunto, recebido em e inteligência/complementação EDNNA.

2) Chamados com a EDNNA
- Nova carteira na Visão geral da Central EDNNA.
- Usa o campo "Atribuído a" do snapshot atual e lista chamados cujo responsável contém "ednna".
- Exibe total e dados operacionais principais.

3) Cancelamentos GETNET
- O plano assistido passa a permitir disparo real após aprovação humana explícita.
- Continua sem execução automática.
- Antes do envio exige Cliente + pelo menos 1 EC + destinatários + assunto + corpo e valida que todos os ECs aparecem no corpo.
- Ao enviar: Graph -> acompanhamento local -> atribuição EDNNA (ID configurado) -> journal/status Redmine -> monitor de respostas.
- Status pós-envio: Aguardando Retorno Adquirente.
- O chamado atual é consultado antes do histórico para aproveitar EC informado diretamente na solicitação.

Configuração esperada no Azure:
REDMINE_EDNNA_USER_ID=166
REDMINE_EDNNA_USERNAME=ednna.ia

Observação de segurança:
CANCELAMENTO-GETNET-001 continua sujeito a aprovação humana. Não há disparo automático em lote.
