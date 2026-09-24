# EDNNA 3.30.0 — Orquestração Greencard

- Greencard deixa de ficar em `AGUARDANDO_EXECUTOR`: `FORMULARIO_GREENCARD` passa a existir como executor assistido.
- Geração do termo `TERMO_GREEN_BENEFICIOS.docx` a partir do chamado + Base de Conhecimento.
- CNPJ(s), cliente e participante principal são pré-preenchidos quando conhecidos; campos desconhecidos permanecem para complemento do cliente.
- O primeiro envio é dirigido aos participantes do cliente, com o formulário DOCX anexado via Microsoft Graph.
- Estado persistente do processo: PREPARAR_TERMO → AGUARDANDO_CLIENTE → VALIDAR_DOCUMENTACAO → AGUARDANDO_GREENCARD → AGUARDANDO_ARQUIVOS → VALIDAR_ARQUIVOS → ABRIR_IMPLANTACAO (abertura) → CONCLUIDO.
- Inclusão e abertura usam o mesmo orquestrador; abertura terá a etapa final de implantação. Dados FTP não são obrigatórios nesta versão.
- A primeira movimentação Greencard é também registrada no BP principal quando localizado.
- Preparada a arquitetura para validar futuramente ECs solicitados versus ECs efetivamente recebidos no FTP.
- `python-docx` adicionado às dependências e Graph passa a suportar anexos de arquivo.

## Segurança
A 3.30.0 automatiza a primeira etapa documental, mas não presume assinatura do cliente, não encaminha automaticamente documento não validado à Greencard e não conclui o chamado pela simples chegada de um arquivo.

## Ajuste de Home — Leitura da EDNNA
- `fotografia atual` foi substituída por `agora`.
- Removida da leitura principal a concentração por responsável (ex.: Wilson), que pertence à visão de Equipe e capacidade.
- A leitura passa a responder somente: situação da operação, trabalho assumido pela EDNNA e decisões humanas pendentes.
- Indicadores: aguardando terceiros (quantidade + percentual), chamados em acompanhamento pela EDNNA e decisões pendentes.
- Incluída frase operacional dinâmica abaixo dos indicadores.
