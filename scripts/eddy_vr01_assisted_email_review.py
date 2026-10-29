"""Generate human-review email drafts from reconciled VR01 observational proposals.

No transport, approval mutation, Redmine writes, or guessed recipient addresses.
This command is deliberately read-only and safe to run in Azure.
"""
from __future__ import annotations

import json

from ednna.eddy_vr01_offline_proposals import PILOT_IDS
from scripts.eddy_vr01_validation_report import validar_pilotos

REMETENTE = "edi@netunna.com.br"

TEMPLATES = {
    "VERIFICAR_HABILITACAO_COM_CLIENTE": (
        "Confirmação de habilitação",
        "Olá,\n\nPoderiam confirmar se a habilitação referente ao chamado #{id} foi concluída? "
        "Caso esteja concluída, solicitamos informar a data e as evidências disponíveis.\n\n"
        "Atenciosamente,\nEquipe EDI Netunna",
    ),
}

def preparar_revisao(ids=PILOT_IDS) -> dict:
    relatorio = validar_pilotos(ids)
    propostas = []
    for item in relatorio["chamados"]:
        if item.get("estado") != "PROPOSTA_OBSERVACIONAL_CONFERIDA":
            propostas.append({"chamado_id": item["chamado_id"], "estado": "BLOQUEADO_RECONCILIACAO"})
            continue
        acao = item.get("acao")
        if acao not in TEMPLATES:
            propostas.append({"chamado_id": item["chamado_id"], "estado": "REVISAO_HUMANA_SEM_MINUTA"})
            continue
        assunto, corpo = TEMPLATES[acao]
        propostas.append({
            "chamado_id": item["chamado_id"],
            "estado": "MINUTA_PARA_REVISAO",
            "remetente": REMETENTE,
            "destinatario": None,
            "destinatario_validado": False,
            "assunto": f"[EDI Netunna] Chamado #{item['chamado_id']} - {assunto}",
            "corpo": corpo.format(id=item["chamado_id"]),
            "versao_redmine": item["versao_redmine"],
            "aprovado_para_envio": False,
        })
    return {
        "modo": "PRODUCAO_ASSISTIDA_PREPARACAO",
        "propostas": propostas,
        "avaliados": len(propostas),
        "minutas": sum(p["estado"] == "MINUTA_PARA_REVISAO" for p in propostas),
        "envios_realizados": 0,
        "redmine_escritas": 0,
        "envio_automatico_habilitado": False,
    }

def main() -> None:
    print(json.dumps(preparar_revisao(), ensure_ascii=False))

if __name__ == "__main__":
    main()
