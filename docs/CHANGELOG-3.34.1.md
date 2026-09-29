# EDNNA 3.34.1

- Nova página administrativa **Observabilidade**, com eventos estruturados persistidos em SQLite e filtros por nível, categoria, chamado e texto.
- Evidências `.eml` deixam de usar nome fixo GETNET/CANCELAMENTO e passam a derivar player/workflow da regra real (ex.: GREENCARD_RETORNO_INCLUSAO_...).
- Saudação passa a usar o primeiro nome derivado da identidade autenticada no Entra ID.
- Central de Operações passa a usar pluralização e concordância naturais, eliminando `chamado(s)`, `situação(ões)`, `acompanhamento(s)` e `atualização(ões)` nessa tela.
- Versão 3.34.1 mantém RBAC/Entra ID da 3.34.0.
