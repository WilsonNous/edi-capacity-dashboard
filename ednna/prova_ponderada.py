from __future__ import annotations

"""Avaliação pedagógica ponderada da Escola Contínua.

A nota considera recência da evidência histórica e criticidade da divergência.
Regra de governança: 100% sem divergência crítica permite auto-homologação do EDDY;
demais faixas seguem a política humana da Escola.
"""
from datetime import datetime, timezone

CORTE_APROVACAO = 85.0
CORTE_RECUPERACAO = 70.0

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
    try: return datetime.fromisoformat(str(valor).replace('Z', '+00:00'))
    except Exception: return None

def _idade_dias(issue: dict) -> int:
    dt = _parse_data(issue.get('closed_on') or issue.get('updated_on') or issue.get('created_on'))
    if not dt: return 0
    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).days)

def avaliar(proposta: dict, prova: dict) -> dict:
    """Reconsulta metadados, calcula nota ponderada e aplica auto-homologação apenas em 100%."""
    from redmine_api import buscar_detalhes_chamado

    detalhes = prova.get('detalhes') or []
    avaliados = []; soma_pesos = soma_notas = 0.0; criticas_recentes = []; erros = []
    for caso in detalhes:
        cid = int(caso.get('chamado_id') or 0)
        try:
            issue = buscar_detalhes_chamado(cid, incluir_journals=False, incluir_relacoes=False,
                                             incluir_anexos=False, consulta_pontual=False, tentativas=1) or {}
        except Exception as exc:
            issue = {}; erros.append({'chamado_id': cid, 'erro': f'{type(exc).__name__}: {exc}'})
        idade = _idade_dias(issue); pr = peso_recencia(idade); faltantes = list(caso.get('faltantes') or []); cobertura = float(caso.get('cobertura_pct') or 0)
        crit = (sum(CRITICIDADE.get(f, 0.75) for f in faltantes) / len(faltantes)) if faltantes else 0.0
        deficit = 100.0 - cobertura; penalidade = deficit * pr * crit; nota = max(0.0, 100.0 - penalidade); peso_caso = max(0.25, pr)
        soma_notas += nota * peso_caso; soma_pesos += peso_caso
        faltantes_criticos = [f for f in faltantes if CRITICIDADE.get(f, 0.75) >= 0.90]
        if idade <= 180 and faltantes_criticos: criticas_recentes.append({'chamado_id': cid, 'idade_dias': idade, 'faltantes': faltantes_criticos})
        avaliados.append({'chamado_id': cid, 'idade_dias': idade, 'peso_recencia': pr, 'cobertura_bruta_pct': round(cobertura), 'criticidade_media': round(crit, 2), 'nota_ponderada_pct': round(nota), 'faltantes': faltantes})

    nota_final = round(soma_notas / soma_pesos) if soma_pesos else 0
    completa = bool(prova.get('completa', True)) and not erros
    if not completa: situacao = 'INCOMPLETA'
    elif criticas_recentes: situacao = 'REVISAO_CRITICA'
    elif nota_final >= CORTE_APROVACAO: situacao = 'APROVADA_PARA_PROFESSOR'
    elif nota_final >= CORTE_RECUPERACAO: situacao = 'RECUPERACAO'
    else: situacao = 'REPROVADA'

    resultado = {'nota_ponderada_pct': nota_final, 'situacao': situacao, 'corte_aprovacao_pct': CORTE_APROVACAO, 'corte_recuperacao_pct': CORTE_RECUPERACAO, 'criticas_recentes': criticas_recentes, 'casos': avaliados, 'erros_metadados': erros, 'metodologia': 'recencia_x_criticidade', 'governanca': '100% sem crítica: auto-homologação EDDY; 90-99%: homologação humana normal; 85-89%: exceção humana justificada'}

    # Nota máxima é evidência suficiente para autonomia: o EDDY se homologa sozinho.
    # A trava continua forte: prova precisa estar completa, sem erro de metadado e sem crítica recente.
    if completa and nota_final == 100 and not criticas_recentes:
        try:
            from ednna.homologacao import auto_homologar_se_perfeito
            auto = auto_homologar_se_perfeito(proposta, resultado)
            if auto: resultado['auto_homologacao'] = auto
        except Exception as exc:
            resultado['erro_auto_homologacao'] = f'{type(exc).__name__}: {exc}'
    return resultado
