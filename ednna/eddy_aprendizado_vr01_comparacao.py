"""Evidence-only cross-check of learned inclusion rules against VR01 governance.

Does not approve, authorize, write data, call Redmine or send email.
"""
from __future__ import annotations

PLAYERS = ("GREENCARD", "SAFRAPAY", "ITAU")
HISTORICAL_REFERENCES = {"GREENCARD": (46968,), "SAFRAPAY": (45956,), "ITAU": ()}
VR01_GATES = (
    "redmine_snapshot_fresco", "mysql_snapshot_journals_conciliados",
    "responsavel_original_persistido", "assuncao_confirmada_redmine",
    "retorno_confirmado_redmine", "transport_mysql_testado_sem_envio",
    "destinatario_validado", "respostas_reconciliadas",
    "auditoria_mysql_validada",
)


def comparar_aprendizado_vr01(player: str, aprendizado: dict | None,
                             revisao: dict | None, autorizacao: dict | None,
                             evidencias: dict | None = None) -> dict:
    player = str(player or "").strip().upper()
    if player not in PLAYERS:
        raise ValueError("Player fora do escopo de comparacao")
    aprendizado, revisao = aprendizado or {}, revisao or {}
    autorizacao, evidencias = autorizacao or {}, evidencias or {}
    regra_id = str(aprendizado.get("regra_id") or "")
    esperado = "INCLUSAO-" + player + "-"
    referencias = set(HISTORICAL_REFERENCES[player])
    fontes = aprendizado.get("fontes") or {}
    ids = {int(x) for x in (fontes.get("historicos") or []) if str(x).isdigit()}
    if str(fontes.get("chamado_historico") or "").isdigit():
        ids.add(int(fontes["chamado_historico"]))
    pendencias = []
    if not regra_id.startswith(esperado) or aprendizado.get("operacao") != "INCLUSAO":
        pendencias.append("REGRA_DE_INCLUSAO_NAO_IDENTIFICADA")
    if not fontes or not (ids or fontes.get("autoridade")):
        pendencias.append("ORIGEM_DO_APRENDIZADO_NAO_COMPROVADA")
    if referencias and not (referencias & ids):
        pendencias.append("REFERENCIA_HISTORICA_NAO_CONCILIADA")
    if revisao.get("estado") != "HOMOLOGADA":
        pendencias.append("REVISAO_HUMANA_NAO_HOMOLOGADA")
    if not revisao.get("revisado_por") or not revisao.get("homologado_em"):
        pendencias.append("AUTORIA_OU_DATA_HOMOLOGACAO_AUSENTE")
    evidencias_faltantes = [
        gate for gate in VR01_GATES
        if not isinstance(evidencias.get(gate), dict)
        or evidencias[gate].get("confirmado") is not True
        or not str(evidencias[gate].get("referencia") or "").strip()
    ]
    return {
        "player": player, "regra_id": regra_id or None,
        "historicos_referencia": sorted(referencias),
        "historicos_identificados": sorted(ids),
        "estado": "APTA_A_REVISAO_DOCUMENTAL" if not pendencias else "APRENDIZADO_A_CONCILIAR",
        "pendencias_aprendizado": pendencias,
        "pendencias_execucao_vr01": evidencias_faltantes,
        "autorizacao_atual": autorizacao.get("modo", "BLOQUEADA"),
        "homologacao_automatica": False,
        "execucao_externa_liberada": False,
    }
