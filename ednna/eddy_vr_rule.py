"""EDDY | piloto VR Benefícios: decisão conservadora baseada em evidências.

Não envia e-mails, altera Redmine ou libera BAT. Executa sobre payload e journals.
"""
from __future__ import annotations
import json
import re
from typing import Any
from ednna.eddy_vr_origin import identificar_vr


def _texto(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_texto(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(_texto(v) for v in value)
    return ""


def avaliar_vr(chamado: dict, journals: list[dict] | None = None) -> dict:
    """Retorna decisão auditável, sem executar ações externas."""
    journals = journals or []
    issue = chamado.get("payload_json") or chamado
    if isinstance(issue, str):
        issue = json.loads(issue)
    if not isinstance(issue, dict):
        raise ValueError("Payload Redmine inválido")
    issue_id = int(issue.get("id") or chamado.get("id"))
    if not identificar_vr(chamado):
        return {"chamado_id": issue_id, "regra": "VR_BENEFICIOS", "estado": "NAO_ELEGIVEL", "acao": "NENHUMA", "execucao_externa": False}
    estado = _texto([chamado.get("estado"), issue.get("status")]).lower()
    if any(k in estado for k in ("concluído", "concluido", "fechado", "rejeitado", "closed")):
        return {"chamado_id": issue_id, "regra": "VR_BENEFICIOS", "estado": "CONCLUIDO", "acao": "NENHUMA", "execucao_externa": False, "evidencias": ["estado_terminal_redmine"]}
    assunto = _texto(issue.get("subject") or chamado.get("assunto"))
    tipo = _texto(issue.get("tracker") or chamado.get("tipo"))
    descricao = _texto(issue.get("description"))
    if any(marker in (assunto + " " + tipo).casefold() for marker in ("falta de arquivo", "arquivos faltantes", "salto de nsa")):
        return {"chamado_id": issue_id, "regra": "VR_BENEFICIOS",
                "estado": "ARQUIVOS_FALTANTES", "acao": "INVESTIGAR_NSA_E_ARQUIVOS",
                "execucao_externa": False,
                "observacao": "Exige verificação de NSA e recepção; não tratar como inclusão."}
    historico = _texto(journals or issue.get("journals") or [])
    texto = (descricao + " " + historico).lower()
    evidencias = []
    # 'cadastro realizado' não equivale a confirmação de autorização no portal.
    autorizacao = bool(re.search(r"(habilita.{0,35}(realizad|conclu|efetuad)|autoriz.{0,35}(realizad|conclu|efetuad))", texto))
    consulta = bool(re.search(r"(time vr|equipe vr|conciliacao@vr\\.com\\.br|canalec@vr\\.com\\.br)", texto))
    arquivos = bool(re.search(r"(arquivos recepcionados|recep.{0,25}arquivos|arquivos capturados)", texto))
    if autorizacao: evidencias.append("autorizacao_informada")
    if consulta: evidencias.append("consulta_vr_registrada")
    if arquivos: evidencias.append("recepcao_mencionada_na_narrativa")
    if consulta:
        fase, acao = "AGUARDANDO_CONFIRMACAO_VR", "VERIFICAR_RESPOSTA_VR"
    elif autorizacao:
        fase, acao = "AUTORIZACAO_INFORMADA", "PREPARAR_CONSULTA_VR"
    else:
        fase, acao = "AUTORIZACAO_NAO_COMPROVADA", "VERIFICAR_PORTAL_E_CONTATO_CLIENTE"
    return {"chamado_id": issue_id, "regra": "VR_BENEFICIOS", "estado": fase, "acao": acao,
            "execucao_externa": False, "evidencias": evidencias,
            "observacao": "Não concluir sem evidência técnica de recepção, BAT e produção."}
