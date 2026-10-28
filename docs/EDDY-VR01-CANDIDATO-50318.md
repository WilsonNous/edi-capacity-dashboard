# VR01 — candidato de piloto #50318 (28/10/2026)

**Status:** PRÉ-SELECIONADO, NÃO HOMOLOGADO OPERACIONALMENTE.

Fonte: exportação Redmine `issues (12).csv` fornecida pelo operador em 28/10/2026. O arquivo tem quatro chamados com origem VR BENEFICIO.

- **#50318**, SUPERMERCADOS MAMBO — inclusão de EC; estado **Aberto**, 0% completo, criado/alterado em 27/10/2026, atribuído a Wilson Martins; sem notas finais no CSV.
- **#49119**, POSTOS ROTA — Aguardando Retorno Cliente, atribuído a ednna .ia; contém histórico de follow-up. Alternativa para observar reconciliação de respostas.
- **#48786**, POSTOS ANDREAZZA — Em Andamento, atribuído a ednna .ia; retorno da adquirente sem confirmação segura da habilitação.
- **#50120**, REDE SANDER — Aberto, falta de vendas, atribuído a Wilson Martins; fluxo distinto de inclusão.

O piloto anterior **#49227** está concluído desde 26/10/2026 e não deve ser aprovado novamente como piloto ativo.

O gate `eddy_vr01_homologation.py` passa a aceitar **somente o ID #50318 como escopo de candidato**, mas **não autoriza por si só a homologação**: `homologar_observacao_vr01` continua exigindo `autorizacao_explicita=True`, e não deve ser invocada como aceite do novo piloto antes da confirmação atualizada do Redmine e da decisão explícita do operador. Nenhuma permissão de envio ou escrita é concedida.

**Validações pendentes:** status atual via Redmine, histórico/journals individualizados, estado do responsável, existência de pendência operacional, snapshot MySQL, documentação do aceite específico e implantação Azure.
