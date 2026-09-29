# EDNNA 3.33.0

- SICREDI Banco consolidado a partir dos casos históricos analisados: abertura via gerente/Blueprint, Supply Mídia, CNAB 240 Febraban 5.0 Aberto diário, múltiplos domicílios e estados de continuidade banco/cliente/VAN/transmissão/arquivos.
- E-mail inicial SICREDI passa a declarar CNPJ, domicílios agência/conta quando disponíveis, VAN Supply Mídia, layout e periodicidade.
- Monitor de respostas ganha interpretação conservadora de eventos SICREDI (assinatura, divergência de VAN, ausência/férias, encaminhamento à VAN, transmissão e pedido de esclarecimento), sem assumir decisão financeira ou troca de VAN.
- Central de Regras passa a exibir o catálogo declarativo completo mesmo quando não há regras pendentes de aprendizado.
- Cada regra declarativa mostra configuração, dados obrigatórios, etapas, canal, executor e estado; permite inativação e overrides seguros persistidos em SQLite.
- Construtor de Regras pode usar uma regra existente como modelo e permite reabrir regra ensinada para edição/teste.
- Regra inativada passa a ter prontidão INATIVA e deixa de ficar elegível para operação.
