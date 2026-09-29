# EDNNA 3.32.4 — Greencard inclusão direta

- Homologa o procedimento real de inclusão Greencard com base no chamado histórico #46968.
- `INCLUSAO-GREENCARD-001` deixa de exigir formulário/assinatura para inclusão simples de estabelecimento.
- Destinatário oficial: `suporte.credenciado@grupogreencard.com.br`.
- Corpo informa cliente, CNPJ e EC solicitado e pede disponibilização dos arquivos na CAIXA POSTAL NETUNNA junto à Greencard.
- Contatos do cliente obtidos do Blueprint entram em CC junto aos CCs institucionais da Netunna.
- Pós-envio: `Aguardando Retorno Adquirente` e estado interno `AGUARDANDO_GREENCARD`.
- Movimentação do BP principal registra o envio direto à Greencard.
- A regra canônica de inclusão Greencard é migrada para `AUTOMATICA`, conforme autorização operacional desta evolução.
- Abertura de relacionamento Greencard NÃO herda este procedimento; continua tratada como fluxo distinto até homologação específica.
- ROTACARD permanece inalterado nesta versão.
