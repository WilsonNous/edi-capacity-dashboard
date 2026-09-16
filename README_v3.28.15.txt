EDI Capacity Dashboard v3.28.15
SQLite First + Aprendizado Semântico

1. Painel stale-while-revalidate
- Se existe snapshot SQLite, ele é servido imediatamente mesmo vencido.
- Snapshot vencido agenda atualização Redmine em thread de background.
- Apenas a ausência total de snapshot exige carga síncrona inicial.
- force_refresh=True preserva atualização síncrona explícita.

2. Aprendizado semântico EDNNA
- Completude deixa de medir apenas fontes/campos e passa a medir sinais operacionais.
- constantes=0 nunca produz PRONTA_PARA_REVISAO.
- Novo estado APRENDIZADO_INCOMPLETO.
- Bloqueios explícitos: histórico insuficiente, procedimento recorrente ausente,
  fontes pendentes, destinatário não confirmado e evidência de conclusão ausente.
- Fontes stale/parciais impedem homologação.

3. Enriquecimento e reaprendizado
- Fontes indisponíveis continuam entrando na fila já existente.
- Após o worker enriquecer uma fonte, regras incompletas relacionadas são
  reprocessadas automaticamente.

4. UX
- A Central informa fontes aguardando enriquecimento e recolhe pendências
  técnicas em expander.
- Nenhuma execução automática de inclusão foi habilitada nesta versão.
