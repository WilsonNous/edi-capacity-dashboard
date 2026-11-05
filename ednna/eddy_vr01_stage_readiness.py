"""VR01 four-stage production handoff: local, read-only and fail-closed.

A readiness report is not an execution authorization. No network calls to
Redmine/Graph, phase transitions or changes to readiness flags occur here.
"""
from __future__ import annotations

from ednna.eddy_vr01_integrated import ISSUE_ID, ORIGINAL_OWNER_ID, _identity, _load
from ednna.eddy_vr_readiness import verificar_prontidao_vr01

STAGES = (
    ("ASSUMIR_CHAMADO", ("PRONTO_PARA_ASSUMIR",)),
    ("SOLICITAR_AUTORIZACAO", ("ASSUMIDO_EDDY", "AGUARDA_CONTATO_BP")),
    ("CONCILIAR_RESPOSTA", ("SOLICITACAO_ENVIADA", "AGUARDA_CONFIRMACAO_CLIENTE")),
    ("REGISTRAR_E_DEVOLVER", ("CONFIRMACAO_RECEBIDA", "EVIDENCIAS_REGISTRADAS",
                             "DEVOLVIDO_ORIGEM", "NOTIFICACAO_INTERNA_CONFIRMADA")),
)


def diagnosticar_etapas_vr01() -> dict:
    """Return evidence-backed stage visibility without performing external actions."""
    row = _load()
    readiness = verificar_prontidao_vr01()
    result = {"chamado_id": ISSUE_ID, "modo": "DIAGNOSTICO_LOCAL",
              "execucao_externa": False, "prontidao_externa": readiness,
              "etapas": []}
    if row is None:
        return {**result, "estado": "AGUARDA_INICIALIZACAO_MYSQL",
                "etapas": [{"nome": name, "estado": "BLOQUEADA_LEDGER"}
                           for name, _ in STAGES]}
    try:
        identity_ok = (row["original_owner_id"] == ORIGINAL_OWNER_ID
                       and row["eddy_owner_id"] == _identity())
    except (ValueError, TypeError):
        identity_ok = False
    phase = row.get("fase")
    result["fase"] = phase
    if not identity_ok or phase not in {p for _, phases in STAGES for p in phases}:
        return {**result, "estado": "BLOQUEADO_IDENTIDADE_OU_FASE",
                "etapas": [{"nome": name, "estado": "BLOQUEADA"}
                           for name, _ in STAGES]}
    current = next(i for i, (_, phases) in enumerate(STAGES) if phase in phases)
    for i, (name, _) in enumerate(STAGES):
        state = "CONCLUIDA_NO_LEDGER" if i < current else (
            "AGUARDA_HOMOLOGACAO" if i == current and not readiness["pronto"]
            else "AGUARDA_APROVACAO_E_EVIDENCIAS" if i == current
            else "AGUARDA_ETAPA_ANTERIOR")
        result["etapas"].append({"nome": name, "estado": state})
    result["estado"] = "CONCLUIDO_NO_LEDGER" if (
        phase == "NOTIFICACAO_INTERNA_CONFIRMADA" and row.get("notificado")
    ) else "PENDENTE_EXECUCAO_HOMOLOGADA"
    result["operacao_pendente"] = row.get("operacao_pendente")
    if row.get("operacao_pendente"):
        result["estado"] = "AGUARDA_RECONCILIACAO_MANUAL"
    return result
