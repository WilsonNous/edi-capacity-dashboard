# EDNNA 3.30.2 — Rotacard + SICREDI via Blueprint

- ROTACARD passa a ser identificado como player e reutiliza o workflow documental da Greencard, com a mesma base de formulário, porém assunto, artefato e movimentação identificados como ROTACARD.
- Abertura de Relacionamento ROTACARD entra na descoberta operacional, além de inclusão.
- SICRED/SICREDI passa a ser normalizado como SICREDI e Abertura de Relacionamento bancário entra na descoberta.
- SICREDI usa a Base de Conhecimento/Blueprint, aba de Domicílios Bancários, para localizar contato/e-mail do gerente por banco 167, nome SICREDI e/ou contas descritas no chamado.
- O rascunho SICREDI inclui as contas e adquirentes descritas no chamado, usa o gerente do BP como destinatário, aplica CC operacional + contato principal do cliente e registra a movimentação no BP principal.
- Se o Blueprint não trouxer contato bancário confiável ou o chamado não trouxer conta, a EDNNA bloqueia em AGUARDANDO_DADOS em vez de inventar informação.
