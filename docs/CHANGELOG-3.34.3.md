# EDNNA 3.34.3

## Correção de resiliência Redmine
- Pre-flight continua fail-safe, porém deixa de furar o circuit breaker global.
- Com circuit breaker aberto, ações externas são bloqueadas imediatamente sem nova chamada ao Redmine.
- Após o cooldown, o fluxo normal volta a consultar o Redmine e mantém a validação fresca antes de efeitos externos.
- Mantidos gateway serializado, snapshot SQLite, cache local e stale-while-revalidate.

## Observabilidade
- Pre-flight indisponível, circuit breaker, estado terminal, monitor adiado e executor automático bloqueado passam a gerar eventos estruturados.
- Eventos repetitivos recebem deduplicação temporal para não transformar observabilidade em nova fonte de carga.
- Mensagem vazia da tela de Observabilidade foi atualizada para não referenciar versão antiga.

## Segurança preservada
- Nenhum envio é liberado quando o estado atual do chamado não pode ser confirmado.
- Estados terminais continuam bloqueando atuação e encerrando acompanhamento conforme regra existente.
