"""Motor de falta de arquivo EDDY: triagem conservadora sem ação externa.

Uma ausência de arquivo não é falha comprovada até validar calendário,
janela, expectativa de entrega e histórico de recepção.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any


def avaliar_falta_arquivo(demanda: dict[str, Any]) -> dict[str, Any]:
    """Gera decisão explicável. Não abre chamados nem dispara cobranças."""
    dados = dict(demanda or {})
    player = str(dados.get("player") or "").strip().upper()
    cliente = str(dados.get("cliente") or "").strip()
    arquivo = str(dados.get("arquivo_esperado") or "").strip()
    obrigatorios = ("player", "cliente", "arquivo_esperado",
                    "janela_vencida", "dia_util_confirmado",
                    "entrega_esperada_confirmada", "recepcao_verificada")
    faltantes = [campo for campo in obrigatorios if dados.get(campo) is None or dados.get(campo) == ""]
    if faltantes:
        estado, acao = "AGUARDANDO_DADOS", "Confirmar expectativa, calendário e recepção"
    elif not dados.get("dia_util_confirmado"):
        estado, acao = "FORA_CALENDARIO", "Aguardar dia útil aplicável"
    elif not dados.get("entrega_esperada_confirmada"):
        estado, acao = "SEM_EXPECTATIVA_CONFIRMADA", "Validar contrato e frequência"
    elif not dados.get("janela_vencida"):
        estado, acao = "DENTRO_DA_JANELA", "Aguardar horário de entrega"
    elif not dados.get("recepcao_verificada"):
        estado, acao = "AGUARDANDO_CONFERENCIA_RECEPCAO", "Conferir pasta, mailbox e processador"
    elif dados.get("arquivo_recebido") is True:
        estado, acao = "ARQUIVO_RECEBIDO", "Validar processamento e conciliação"
    elif dados.get("arquivo_recebido") is not False:
        estado, acao = "AGUARDANDO_CONFIRMACAO_AUSENCIA", "Confirmar ausência real"
    else:
        estado, acao = "FALTA_CONFIRMADA", "Preparar tratativa conforme regra homologada"
    return {
        "operacao": "FALTA_ARQUIVO", "player": player, "cliente": cliente,
        "arquivo_esperado": arquivo, "estado": estado, "proxima_acao": acao,
        "dados_pendentes": faltantes, "executavel": False,
        "envio_externo_autorizado": False,
        "evidencia_necessaria": ["arquivo esperado", "janela e calendário",
                                "verificação de recepção", "último arquivo recebido"],
    }


def listar_regras_aprendidas() -> list[dict]:
    """Inventaria homologações reais de falta de arquivo da Escola."""
    from ednna.homologacao import listar_homologacoes_mais_recentes
    prefixos = ("FALTA-ARQUIVO-", "FALTA_ARQUIVO-", "AUSENCIA-ARQUIVO-")
    return [
        {"regra_id": h["regra_id"], "player": h.get("player"),
         "estado": h.get("estado"), "nota": h.get("nota"),
         "operacao": "FALTA_ARQUIVO",
         "executavel": False, "autorizacao_externa": "PENDENTE_EXECUTOR"}
        for h in listar_homologacoes_mais_recentes()
        if str(h.get("regra_id") or "").upper().startswith(prefixos)
    ]


def avaliar_regra_aprendida(regra_id: str, demanda: dict) -> dict:
    """Combina conhecimento homologado e evidência real, sem disparar."""
    resultado = avaliar_falta_arquivo(demanda)
    regra = next((r for r in listar_regras_aprendidas()
                  if r["regra_id"] == regra_id), None)
    resultado["regra_id"] = regra_id
    resultado["homologacao"] = (regra or {}).get("estado", "NAO_ENCONTRADA")
    resultado["executavel"] = False
    if not regra or regra["estado"] not in {"ATIVA", "EM_OBSERVACAO"}:
        resultado["estado"] = "AGUARDANDO_HOMOLOGACAO"
    elif resultado["estado"] == "FALTA_CONFIRMADA":
        resultado["estado"] = "TRATATIVA_APRENDIDA_AGUARDANDO_EXECUTOR"
    return resultado
