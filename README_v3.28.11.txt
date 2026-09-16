EDI Capacity Dashboard / EDNNA — v3.28.11

Release: EDNNA Investigação Resiliente e Cache de Contexto

Principais ajustes:
- investigação interativa usa consulta pontual curta (connect 4s / read 8s / 1 tentativa);
- fallback imediato para cache SQLite válido ou histórico expirado;
- contexto expirado é identificado como parcial, com procedência e timestamp;
- falhas sem cache entram automaticamente na fila SQLite de enriquecimento;
- monitor EDNNA processa a fila em background com política mais tolerante;
- cache de BP, AR, inclusões e relações permanece persistente entre reinícios;
- Central de Descoberta informa REDMINE x MISTA/CACHE e contexto parcial;
- versão continua centralizada em version.py.

Objetivo operacional:
A interface não deve ficar presa em múltiplos timeouts do Redmine. A ação humana
recebe rapidamente o melhor contexto disponível; o enriquecimento pendente ocorre
em background e melhora a base histórica para investigações futuras.
