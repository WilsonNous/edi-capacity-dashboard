# EDNNA v3.28.51

## Integridade operacional + TrioCard

- Extração de EC/Convênio de inclusões agora é contextual: somente assunto/descrição e linhas semanticamente rotuladas.
- IDs de anexos, screenshots, URLs e journals deixam de contaminar a lista de estabelecimentos.
- TICKET multi-EC preserva todos os ECs válidos do chamado e usa a mesma lista no preview e no envio.
- Nova regra assistida `FALTA-TRIOCARD-001` para chamados de Falta de Arquivo.
- TrioCard usa `arquivos@personalcard.com.br` e CC institucional BPO + EDI + Consultores.
- Template TrioCard exige cliente, origem, data inicial, tipo de arquivo, último NSA, Convênio/EC e ação marcada `[X]`.
- Todos os Convênios/ECs rotulados no template são preservados no e-mail.
- A regra TrioCard é executável somente com aprovação humana (`auto_executar=false`).
- Mantida a reconciliação genérica do Redmine pós-envio existente na v3.28.50.
