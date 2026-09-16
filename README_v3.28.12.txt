EDI Capacity Dashboard / EDNNA — v3.28.12

Objetivo: Investigação Orientada à Adquirente + Síntese Operacional.

Principais ajustes:
- investigação de inclusão passa a priorizar o player/adquirente do chamado atual;
- ARs de outros players deixam de poluir a regra candidata;
- inclusões anteriores são filtradas pelo mesmo player;
- resultado da investigação apresenta síntese operacional antes dos detalhes;
- evidências, dados extraídos e diagnóstico técnico ficam em expansores fechados;
- mantém cache resiliente, fila de enriquecimento e rastreabilidade da v3.28.11;
- nenhuma regra candidata executa ações sem homologação explícita.

Caso de validação recomendado:
#48318 / REDE SANTA LUCIA / VALECARD.
Esperado: VALECARD como investigação principal; inclusões #44872 e #48281 como histórico relevante, sem REDECARD concorrendo na síntese.

Nota de roadmap UX:
A UX completa do produto será redesenhada em etapa própria. O problema identificado é global (arquitetura de informação e navegação), não restrito à Central EDNNA.
