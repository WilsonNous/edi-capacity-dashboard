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
