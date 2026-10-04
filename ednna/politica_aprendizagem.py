"""Política pedagógica do EDDY.

Mantida no package legado `ednna` por compatibilidade técnica da migração 4.0.
A prova mede conhecimento; o reestudo de evidências corrigidas é que ensina.
"""
from __future__ import annotations

NOTA_AUTONOMIA = 90
NOTA_EXCECAO_HUMANA = 85


def diagnosticar_prova(prova: dict) -> dict:
    nota = int(prova.get('nota_ponderada_pct') or 0)
    criticas = list(prova.get('criticas_recentes') or [])
    casos = list(prova.get('casos') or [])
    revisar = []
    lacunas = []
    for caso in casos:
        aderencia = int(caso.get('cobertura_bruta_pct') or caso.get('nota_ponderada_pct') or 0)
        if aderencia < NOTA_AUTONOMIA:
            cid = caso.get('chamado_id')
            if cid is not None: revisar.append(cid)
            lacunas.append({'chamado_id': cid, 'aderencia_pct': aderencia})
    if criticas:
        situacao = 'CORRIGIR_MATERIA'
    elif nota >= NOTA_AUTONOMIA:
        situacao = 'APTO_AUTONOMIA'
    elif nota >= NOTA_EXCECAO_HUMANA:
        situacao = 'EXCECAO_HUMANA'
    else:
        situacao = 'REESTUDAR'
    return {'nota': nota, 'situacao': situacao, 'criticas': criticas, 'casos_para_revisar': revisar, 'lacunas': lacunas}


def orientar_professor(diagnostico: dict) -> str:
    situacao = diagnostico.get('situacao')
    nota = int(diagnostico.get('nota') or 0)
    if situacao == 'APTO_AUTONOMIA':
        return f'Tirei {nota}%. Revise minha prova e, se o procedimento estiver correto, homologue a regra para eu trabalhar.'
    if situacao == 'EXCECAO_HUMANA':
        return f'Tirei {nota}%. Ainda não alcancei {NOTA_AUTONOMIA}%, mas o professor pode avaliar se as lacunas são de baixo risco e homologar excepcionalmente em observação.'
    if situacao == 'CORRIGIR_MATERIA':
        return 'Encontrei divergência crítica recente. Revise os chamados indicados, corrija/complemente a evidência operacional e depois mande eu reestudar antes de uma nova prova.'
    return f'Tirei {nota}%. Melhore os chamados/evidências indicados e depois mande eu reestudar. Repetir a mesma prova sem matéria nova não melhora meu conhecimento.'
