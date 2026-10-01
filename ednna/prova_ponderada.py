from __future__ import annotations

"""Avaliação pedagógica ponderada da Escola Contínua.

A nota considera recência da evidência histórica e criticidade da divergência.
Ela orienta revisão humana; nunca homologa nem autoriza uma regra.
"""
from datetime import datetime, timezone

CORTE_APROVACAO = 85.0
CORTE_RECUPERACAO = 70.0

# Falhas que podem provocar execução no cliente/destinatário errado continuam fortes.
CRITICIDADE = {
    'IDENTIFICAR_CONTEXTO': 1.00,
    'EXTRAIR_DADOS': 1.00,
    'PREPARAR_SOLICITACAO': 0.90,
    'ENVIAR_EMAIL': 1.00,
    'REGISTRAR_REDMINE': 0.80,
    'CONSULTAR_BLUEPRINT': 0.90,
    'EXECUTAR_API_PORTAL': 1.00,
    'DECISAO_AMBIGUA': 1.00,
    'MONITORAR_RESPOSTA': 0.65,
    'INTERPRETAR_RETORNO': 0.75,
    'ASSINATURA_DOCUMENTO': 0.60,
    'ATUALIZAR_PLANILHA': 0.55,
    'VALIDAR_ARQUIVOS': 0.55,
}


def peso_recencia(dias: int) -> float:
    if dias <= 90: return 1.00
    if dias <= 180: return 0.90
    if dias <= 360: return 0.75
    if dias <= 720: return 0.50
    return 0.25


def _parse_data(valor):
    if not valor: return None
    try:
        return datetime.fromisoformat(str(valor).replace('Z', '+00:00'))
    except Exception:
        return None


def _idade_dias(issue: dict) -> int:
    # updated_on representa melhor a época efetiva da operação que created_on.
    dt = _parse_data(issue.get('closed_on') or issue.get('updated_on') or issue.get('created_on'))
    if not dt: return 0
    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).days)


def avaliar(proposta: dict, prova: dict) -> dict:
    """Reconsulta somente metadados dos casos da prova para obter idade real."""
    from redmine_api import buscar_detalhes_chamado

    detalhes = prova.get('detalhes') or []
    avaliados = []
    soma_pesos = soma_notas = 0.0
    criticas_recentes = []
    erros = []

    for caso in detalhes:
        cid = int(caso.get('chamado_id') or 0)
        try:
            issue = buscar_detalhes_chamado(cid, incluir_journals=False, incluir_relacoes=False,
                                             incluir_anexos=False, consulta_pontual=False, tentativas=1) or {}
        except Exception as exc:
            issue = {}
            erros.append({'chamado_id': cid, 'erro': f'{type(exc).__name__}: {exc}'})
        idade = _idade_dias(issue)
        pr = peso_recencia(idade)
        faltantes = list(caso.get('faltantes') or [])
        cobertura = float(caso.get('cobertura_pct') or 0)

        # A cobertura observada é a base. A penalidade das ausências é reduzida
        # quando a evidência é antiga e quando a etapa é historicamente menos crítica.
        if faltantes:
            crit = sum(CRITICIDADE.get(f, 0.75) for f in faltantes) / len(faltantes)
        else:
            crit = 0.0
        deficit = 100.0 - cobertura
        penalidade = deficit * pr * crit
        nota = max(0.0, 100.0 - penalidade)
        peso_caso = max(0.25, pr)
        soma_notas += nota * peso_caso
        soma_pesos += peso_caso

        # Trava: divergência crítica em evidência recente não pode ser escondida pela média.
        faltantes_criticos = [f for f in faltantes if CRITICIDADE.get(f, 0.75) >= 0.90]
        if idade <= 180 and faltantes_criticos:
            criticas_recentes.append({'chamado_id': cid, 'idade_dias': idade, 'faltantes': faltantes_criticos})

        avaliados.append({
            'chamado_id': cid, 'idade_dias': idade, 'peso_recencia': pr,
            'cobertura_bruta_pct': round(cobertura), 'criticidade_media': round(crit, 2),
            'nota_ponderada_pct': round(nota), 'faltantes': faltantes,
        })

    nota_final = round(soma_notas / soma_pesos) if soma_pesos else 0
    completa = bool(prova.get('completa', True)) and not erros
    if not completa:
        situacao = 'INCOMPLETA'
    elif criticas_recentes:
        situacao = 'REVISAO_CRITICA'
    elif nota_final >= CORTE_APROVACAO:
        situacao = 'APROVADA_PARA_PROFESSOR'
    elif nota_final >= CORTE_RECUPERACAO:
        situacao = 'RECUPERACAO'
    else:
        situacao = 'REPROVADA'

    return {
        'nota_ponderada_pct': nota_final,
        'situacao': situacao,
        'corte_aprovacao_pct': CORTE_APROVACAO,
        'corte_recuperacao_pct': CORTE_RECUPERACAO,
        'criticas_recentes': criticas_recentes,
        'casos': avaliados,
        'erros_metadados': erros,
        'metodologia': 'recencia_x_criticidade',
        'governanca': 'nota orienta revisão; homologação e autorização permanecem humanas',
    }
