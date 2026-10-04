from __future__ import annotations

"""Política pedagógica do EDDY 4.0.

A prova mede conhecimento; não ensina. O professor melhora a matéria-prima,
o EDDY reestuda e só então uma nova prova independente mede generalização.
"""

NOTA_AUTONOMIA = 90
NOTA_EXCECAO_HUMANA = 85


def faixa_nota(nota: int, criticas_recentes=None) -> dict:
    nota = int(nota or 0)
    criticas = list(criticas_recentes or [])
    if criticas:
        return {
            'codigo': 'REVISAO_CRITICA',
            'titulo': 'Preciso do professor',
            'acao': 'Corrija a matéria crítica antes de uma nova prova.',
            'pode_homologar': False,
            'excepcional': False,
        }
    if nota >= NOTA_AUTONOMIA:
        return {
            'codigo': 'APTO_AUTONOMIA',
            'titulo': 'Apto para homologação',
            'acao': 'O professor pode homologar esta versão para produção.',
            'pode_homologar': True,
            'excepcional': False,
        }
    if nota >= NOTA_EXCECAO_HUMANA:
        return {
            'codigo': 'EXCECAO_HUMANA',
            'titulo': 'Professor pode autorizar em observação',
            'acao': 'Revise os riscos e registre uma justificativa para homologação excepcional.',
            'pode_homologar': True,
            'excepcional': True,
        }
    return {
        'codigo': 'REESTUDAR',
        'titulo': 'Preciso estudar mais',
        'acao': 'Melhore os chamados/evidências indicados, depois mande o EDDY reestudar antes de aplicar nova prova.',
        'pode_homologar': False,
        'excepcional': False,
    }


def plano_estudo(detalhes: list[dict]) -> dict:
    """Transforma erros da prova em orientação concreta ao professor."""
    reprovados = [d for d in (detalhes or []) if int(d.get('cobertura_pct') or 0) < 80]
    chamados = [d.get('chamado_id') for d in reprovados if d.get('chamado_id')]
    faltas: dict[str, int] = {}
    for d in reprovados:
        for falta in d.get('faltantes') or []:
            chave = str(falta)
            faltas[chave] = faltas.get(chave, 0) + 1
    return {
        'chamados_para_revisar': chamados,
        'lacunas': sorted(faltas.items(), key=lambda x: (-x[1], x[0])),
        'orientacao': 'Corrija ou complete a fonte operacional; depois reestude. Repetir a prova sem matéria nova não representa aprendizado.',
    }
