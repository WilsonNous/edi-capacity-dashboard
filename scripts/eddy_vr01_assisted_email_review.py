"""Generate human-review email drafts from reconciled VR01 observational proposals.

No transport, approval mutation, Redmine writes, or guessed recipient addresses.
This command is deliberately read-only and safe to run in Azure.
"""
from __future__ import annotations

import json
import re

from ednna.eddy_vr01_offline_proposals import PILOT_IDS
from ednna.mysql_snapshot_repository import carregar_snapshot
from ednna.planejador_inclusoes import _extrair_dados
from ednna.blueprint_knowledge import selecionar_contatos_cliente
from ednna.eddy_vr_mysql_sync import clientes_do_redmine
from ednna.mysql_redmine_catalog import mapa_persistido
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


def candidatos_destinatarios(chamado_id: int) -> dict:
    """Reuse the existing operational extractor on the persisted issue snapshot.

    Candidates are not validated recipients. VR habilitation targets the client,
    never VR or Netunna. Human review remains mandatory.
    """
    try:
        stored = carregar_snapshot(chamado_id)
        raw = (stored or {}).get("chamado", {}).get("payload_json")
        issue = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(issue, dict) or int(issue.get("id") or 0) != chamado_id:
            return {"candidatos": [], "fonte": "SNAPSHOT_INDISPONIVEL"}
        clientes = clientes_do_redmine(issue)
        cliente_mysql = str((stored or {}).get("chamado", {}).get("cliente") or "").strip()
        if len(clientes) > 1:
            cliente = ""
            cliente_estado = "MULTIPLOS_CLIENTES_REVISAO_HUMANA"
        elif len(clientes) == 1:
            cliente = clientes[0]
            cliente_estado = "CLIENTE_IDENTIFICADO"
        else:
            cliente = cliente_mysql
            cliente_estado = "CLIENTE_IDENTIFICADO" if cliente else "CLIENTE_NAO_IDENTIFICADO"
        # Numeric values in Redmine's multi-select are option IDs, not names.
        # Only a durable, verified MySQL catalog can resolve them.
        catalogo_estado = "NAO_NECESSARIO"
        if cliente and cliente.isdecimal():
            try:
                mapa = mapa_persistido(1)
                nome = str(mapa.get(cliente) or "").strip()
                if nome and nome != cliente:
                    cliente = nome
                    catalogo_estado = "RESOLVIDO_MYSQL"
                else:
                    cliente = ""
                    cliente_estado = "CLIENTE_ID_SEM_CATALOGO"
                    catalogo_estado = "ID_NAO_RESOLVIDO"
            except Exception as catalogo_exc:
                cliente = ""
                cliente_estado = "CLIENTE_CATALOGO_INDISPONIVEL"
                catalogo_estado = "INDISPONIVEL_" + type(catalogo_exc).__name__
        # The existing Blueprint selector prioritizes Finance, project management,
        # and andamento/status contacts. It may be unavailable while SQLite is damaged.
        bp_contatos = []
        bp_estado = cliente_estado
        if cliente:
            try:
                bp_contatos = selecionar_contatos_cliente(cliente, limite=10)
                bp_estado = "CONSULTADO" if bp_contatos else "SEM_PARTICIPANTES"
            except Exception as bp_exc:
                bp_estado = "INDISPONIVEL_" + type(bp_exc).__name__
        dados = _extrair_dados({
            "subject": issue.get("subject") or "",
            "description": issue.get("description") or "",
            "journals": [],
        })
        encontrados = []
        fontes = {}
        def incluir(email, fonte):
            email = str(email or "").strip().lower()
            if (re.fullmatch(r"[^@\\s]+@[^@\\s]+\\.[^@\\s]+", email)
                    and not email.endswith(("@vr.com.br", "@netunna.com.br"))
                    and email not in encontrados):
                encontrados.append(email)
                fontes[email] = fonte
        for contato in bp_contatos:
            incluir(contato.get("email"), "BLUEPRINT_PARTICIPANTES")
        for email in dados.get("emails") or []:
            incluir(email, "EXTRATOR_OPERACIONAL_SNAPSHOT")
        return {
            "candidatos": encontrados,
            "fonte": "BLUEPRINT_E_EXTRATOR_OPERACIONAL",
            "fontes_por_destinatario": fontes,
            "estado_blueprint": bp_estado,
            "cliente_blueprint": cliente,
            "clientes_redmine": clientes,
            "estado_catalogo_clientes": catalogo_estado,
        }
    except Exception as exc:
        return {"candidatos": [], "fonte": "EXTRACAO_INDISPONIVEL",
                "erro_tipo": type(exc).__name__}

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
        destinatarios = candidatos_destinatarios(item['chamado_id'])
        propostas.append({
            "chamado_id": item["chamado_id"],
            "estado": "MINUTA_PARA_REVISAO",
            "remetente": REMETENTE,
            "destinatario": None,
            "candidatos_destinatarios": destinatarios["candidatos"],
            "fonte_destinatarios": destinatarios["fonte"],
            "fontes_por_destinatario": destinatarios.get("fontes_por_destinatario", {}),
            "estado_blueprint": destinatarios.get("estado_blueprint", "NAO_CONSULTADO"),
            "cliente_blueprint": destinatarios.get("cliente_blueprint", ""),
            "clientes_redmine": destinatarios.get("clientes_redmine", []),
            "estado_catalogo_clientes": destinatarios.get("estado_catalogo_clientes", "NAO_CONSULTADO"),
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
