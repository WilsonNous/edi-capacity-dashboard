# Diretriz global EDDY — registro de e-mails no Redmine

**Escopo:** todas as regras, adquirentes, benefícios e canais operados pelo EDDY, incluindo VR Benefícios, REDECARD/REDE, GETNET, SAFRAPAY e demais integrações. Esta diretriz é transversal e não pode ficar restrita à implementação de uma regra.

## Obrigação

Quando o EDDY receber uma resposta de e-mail pertinente a um chamado, deve publicar **o texto da resposta diretamente como nota no histórico do chamado Redmine**, legível sem abrir anexos. Não substituir o texto por arquivo .eml, .msg, PDF, imagem, link ou resumo. Anexos originais relevantes podem ser preservados adicionalmente, mas não substituem a nota textual.

Cada nota deve identificar:
- Remetente, destinatários pertinentes, data/hora com fuso, assunto e identificador da mensagem, quando disponível.
- **Corpo completo da nova resposta**, mantendo seu sentido e conteúdo original, com formatação textual legível. Não omitir trechos relevantes nem inventar conteúdo.
- Análise separada e claramente rotulada do EDDY: interpretação, fase do chamado, próxima ação, responsável/canal e prazo aplicável.
- Referência a anexos relevantes, se existirem.

## Segurança e qualidade

- Evitar repetir automaticamente toda a cadeia de mensagens citadas anteriormente; preservar integralmente a **nova resposta** e incluir contexto anterior somente quando necessário à compreensão.
- Sanitizar HTML para texto seguro e legível; nunca executar conteúdo de e-mail nem incluir scripts.
- Proteger segredos, credenciais e dados sensíveis segundo as políticas de segurança e LGPD; não replicar informação desnecessária.
- Impedir duplicações usando ID estável da mensagem e do chamado, com confirmação da escrita no Redmine.
- Se a escrita falhar, registrar falha operacional, reprocessar de forma idempotente e **não declarar documentação concluída**.
- Somente registrar envio ou cobrança como executado após evidência verificável; jamais fabricar protocolo, destinatário ou horário.
- Não alterar chamados terminais nem disparar mensagens sem autorização operacional aplicável.

## Exemplo de estrutura de nota

EDDY | RESPOSTA DE E-MAIL RECEBIDA
Data/hora: [data/hora e fuso]
De: [remetente]
Para: [destinatários pertinentes]
Assunto: [assunto]
ID da mensagem: [identificador]

RESPOSTA RECEBIDA — TEXTO INTEGRAL
[corpo da nova mensagem]

ANÁLISE DO EDDY
Fase: [fase]
Interpretação: [interpretação]
Próxima ação: [ação]
Próximo follow-up: [prazo ou não aplicável]

## Critério de aceite transversal

A pessoa que abrir o chamado no Redmine deve conseguir **ler a resposta recebida e compreender o andamento sem abrir anexos ou consultar a caixa de e-mail**.

**Estado:** diretriz de projeto registrada; implementação e homologação da escrita automática no Redmine devem ser comprovadas em cada fluxo antes de considerar a regra operacional.
