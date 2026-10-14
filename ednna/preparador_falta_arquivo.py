"""Preparação conservadora de solicitação consolidada de arquivos EDI.

Não envia e-mails, não altera Redmine e não presume ausência de evidência.
"""
from __future__ import annotations

from datetime import date
from typing import Any


def preparar_solicitacao_falta_arquivo(dados: dict[str, Any]) -> dict[str, Any]:
    """Consolida lacunas de um cliente/convênio em uma única minuta auditável."""
    player = str(dados.get("player") or "").strip()
    cliente = str(dados.get("cliente") or "").strip()
    convenio = str(dados.get("convenio") or "").strip()
    chamados = dados.get("chamados") or []
    arquivos = dados.get("arquivos") or []
    if not player or not cliente or not convenio:
        raise ValueError("player, cliente e convenio são obrigatórios")
    if not isinstance(arquivos, list) or not arquivos:
        raise ValueError("arquivos deve ser uma lista não vazia")
    if not isinstance(chamados, list):
        raise ValueError("chamados deve ser uma lista")
    normalizados = []
    vistos = set()
    for item in arquivos:
        if not isinstance(item, dict):
            raise ValueError("cada arquivo deve ser um objeto")
        nsa = str(item.get("nsa") or "").strip()
        data = str(item.get("data") or "").strip()
        if not nsa or not data:
            raise ValueError("cada arquivo exige nsa e data")
        try:
            date.fromisoformat(data)
        except ValueError as exc:
            raise ValueError("data deve estar no formato AAAA-MM-DD") from exc
        chave = (nsa, data)
        if chave in vistos:
            continue
        vistos.add(chave)
        normalizados.append({"nsa": nsa, "data": data, "ausencia_confirmada": item.get("ausencia_confirmada") is True})
    normalizados.sort(key=lambda x: (x["data"], x["nsa"]))
    linhas = []
    for item in normalizados:
        dia = date.fromisoformat(item["data"]).strftime("%d/%m/%Y")
        linhas.append(f"- NSA {item['nsa']} — {dia}")
    referencias = ", ".join("#" + str(c).lstrip("#") for c in chamados if str(c).strip())
    assunto = f"{player} | {cliente} | Convênio {convenio} | Solicitação de arquivos NSA " + " e ".join(x["nsa"] for x in normalizados)
    corpo = (
        "Prezados, bom dia!\n\n"
        f"Identificamos lacunas na sequência de disponibilização dos arquivos de {player} "
        f"para o cliente {cliente}, convênio {convenio}.\n\n"
        "Solicitamos a verificação e, quando aplicável, o reprocessamento/disponibilização dos arquivos:\n\n"
        + "\n".join(linhas)
        + "\n\nPedimos a confirmação da disponibilidade e, se necessário, a previsão de regularização.\n\n"
        + (f"Referência Netunna: {referencias}.\n\n" if referencias else "")
        + "Atenciosamente,\nEquipe EDI | Netunna\n\n"
        "Esta solicitação foi preparada pelo EDDY, agente de inteligência operacional da Netunna."
    )
    pendencias = []
    if not str(dados.get("destinatario_oficial") or "").strip():
        pendencias.append("destinatario_oficial")
    if not all(x["ausencia_confirmada"] for x in normalizados):
        pendencias.append("confirmacao_ausencia_de_todos_os_arquivos")
    if dados.get("historico_sem_solicitacao") is not True:
        pendencias.append("historico_sem_solicitacao")
    return {
        "assunto": assunto, "corpo": corpo, "arquivos": normalizados,
        "destinatario": str(dados.get("destinatario_oficial") or "").strip(),
        "pendencias": pendencias, "aprovacao_humana_necessaria": True,
        "pronto_para_aprovacao": not pendencias,
        "envio_realizado": False, "redmine_atualizado": False,
    }
