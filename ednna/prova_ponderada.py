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

def _normalizar_issue(payload: dict) -> dict:
    """Aceita tanto o issue puro quanto a resposta REST {'issue': {...}}."""
    if not isinstance(payload, dict): return {}
    issue = payload.get('issue')
    return issue if isinstance(issue, dict) else payload

def _data_evidencia(issue: dict):
    """Retorna a data operacional usada na ponderação e sua origem."""
    for campo in ('closed_on', 'updated_on', 'created_on'):
        valor = issue.get(campo)
        dt = _parse_data(valor)
        if dt:
            if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc), campo
    return None, None

def _idade_dias(issue: dict):
    dt, _ = _data_evidencia(issue)
    if not dt: return None
    return max(0, (datetime.now(timezone.utc) - dt).days)

def avaliar(proposta: dict, prova: dict) -> dict:
    """Reconsulta metadados, calcula nota ponderada e aplica auto-homologação apenas em 100%."""
    from redmine_api import buscar_detalhes_chamado

    detalhes = prova.get('detalhes') or []
    avaliados = []; soma_pesos = soma_notas = 0.0; criticas_recentes = []; erros = []
    for caso in detalhes:
        cid = int(caso.get('chamado_id') or 0)
        try:
            bruto = buscar_detalhes_chamado(cid, incluir_journals=False, incluir_relacoes=False,
                                            incluir_anexos=False, consulta_pontual=False, tentativas=1) or {}
            issue = _normalizar_issue(bruto)
        except Exception as exc:
            issue = {}; erros.append({'chamado_id': cid, 'erro': f'{type(exc).__name__}: {exc}'})

        idade = _idade_dias(issue)
        data_evidencia, campo_data = _data_evidencia(issue)
        # Data ausente não pode significar "hoje". Sem metadado temporal, a prova fica incompleta
        # e o caso recebe peso conservador até que a origem seja corrigida.
        if idade is None:
            pr = 0.25
            erros.append({'chamado_id': cid, 'erro': 'METADADO_TEMPORAL_AUSENTE'})
        else:
            pr = peso_recencia(idade)

        faltantes = list(caso.get('faltantes') or []); cobertura = float(caso.get('cobertura_pct') or 0)
        crit = (sum(CRITICIDADE.get(f, 0.75) for f in faltantes) / len(faltantes)) if faltantes else 0.0
        deficit = 100.0 - cobertura; penalidade = deficit * pr * crit; nota = max(0.0, 100.0 - penalidade); peso_caso = max(0.25, pr)
        soma_notas += nota * peso_caso; soma_pesos += peso_caso
        faltantes_criticos = [f for f in faltantes if CRITICIDADE.get(f, 0.75) >= 0.90]
        # Só classificamos como crítica RECENTE quando conhecemos a idade de fato.
        if idade is not None and idade <= 180 and faltantes_criticos:
            criticas_recentes.append({'chamado_id': cid, 'idade_dias': idade, 'faltantes': faltantes_criticos})
        avaliados.append({
            'chamado_id': cid,
            'idade_dias': idade,
            'data_evidencia': data_evidencia.isoformat() if data_evidencia else None,
            'campo_data': campo_data,
            'peso_recencia': pr,
            'cobertura_bruta_pct': round(cobertura),
            'criticidade_media': round(crit, 2),
            'nota_ponderada_pct': round(nota),
            'faltantes': faltantes,
        })

    nota_final = round(soma_notas / soma_pesos) if soma_pesos else 0
    completa = bool(prova.get('completa', True)) and not erros
    if not completa: situacao = 'INCOMPLETA'
    elif criticas_recentes: situacao = 'REVISAO_CRITICA'
    elif nota_final >= CORTE_APROVACAO: situacao = 'APROVADA_PARA_PROFESSOR'
    elif nota_final >= CORTE_RECUPERACAO: situacao = 'RECUPERACAO'
    else: situacao = 'REPROVADA'

    resultado = {'nota_ponderada_pct': nota_final, 'situacao': situacao, 'corte_aprovacao_pct': CORTE_APROVACAO, 'corte_recuperacao_pct': CORTE_RECUPERACAO, 'criticas_recentes': criticas_recentes, 'casos': avaliados, 'erros_metadados': erros, 'metodologia': 'recencia_x_criticidade', 'governanca': '100% sem crítica: auto-homologação EDDY; 90-99%: homologação humana normal; 85-89%: exceção humana justificada'}

    if completa and nota_final == 100 and not criticas_recentes:
        try:
            from ednna.homologacao import auto_homologar_se_perfeito
            auto = auto_homologar_se_perfeito(proposta, resultado)
            if auto: resultado['auto_homologacao'] = auto
        except Exception as exc:
            resultado['erro_auto_homologacao'] = f'{type(exc).__name__}: {exc}'
    return resultado
