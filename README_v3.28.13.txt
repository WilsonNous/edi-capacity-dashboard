EDI Capacity Dashboard / EDNNA — v3.28.13

Objetivo: fixar o PLAYER_ALVO do chamado de inclusão e impedir concorrência indevida de players históricos.

Principais ajustes:
- PLAYER_ALVO é extraído prioritariamente do assunto do chamado atual;
- aliases genéricos do histórico não podem substituir um player explícito;
- proteção específica contra falso positivo REDE SANTA LUCIA -> REDECARD;
- BP confirma o contexto, mas não escolhe o player quando o chamado já o informa;
- AR e inclusões anteriores são filtradas exclusivamente pelo PLAYER_ALVO;
- logs mostram chamado, origem do player, BP, AR, históricos filtrados e players secundários ignorados;
- regra permanece CANDIDATA_NAO_HOMOLOGADA e sem ações externas.

Caso de validação:
#48318 / REDE SANTA LUCIA / VALECARD.
Esperado: PLAYER_ALVO=VALECARD; BP #8812; AR #43943; inclusões anteriores #44872 e #48281; REDECARD apenas como contexto secundário, nunca como investigação concorrente.

Roadmap UX:
Redesenho completo da UX do produto, não apenas da Central EDNNA, será tratado em entrega própria após estabilização funcional.
