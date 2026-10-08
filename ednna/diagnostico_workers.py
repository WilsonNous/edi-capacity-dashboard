"""Leitura honesta de evidências de execução dos workers no Azure."""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")


def diagnosticar_workers():
    caminho = Path(os.getenv("EDDY_WORKER_HEARTBEATS", "/home/data/eddy_worker_heartbeats.json"))
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        if not isinstance(dados, dict):
            raise ValueError("invalid heartbeat")
    except (OSError, ValueError, TypeError):
        dados = {}
    linhas = []
    for nome in ("monitor_email", "followup", "aprendizado", "redmine"):
        info = dados.get(nome) or {}
        ultimo = str(info.get("ultimo_ciclo_em") or "")
        erro = str(info.get("ultimo_erro") or "")
        estado = "SEM_EVIDENCIA"
        try:
            momento = datetime.fromisoformat(ultimo.replace("Z", "+00:00"))
            if momento.tzinfo is None:
                raise ValueError("missing timezone")
            idade = datetime.now(TZ) - momento.astimezone(TZ)
            if idade < timedelta(0):
                estado = "RELOGIO_INCONSISTENTE"
            elif idade > timedelta(minutes=int(os.getenv("EDDY_WORKER_STALE_MINUTES", "30"))):
                estado = "SEM_CICLO_RECENTE"
            else:
                estado = "ERRO_REPORTADO" if erro else "CICLO_RECENTE_REPORTADO"
        except (ValueError, TypeError, OverflowError):
            pass
        linhas.append({"Worker": nome, "Situação": estado,
                       "Último ciclo": ultimo or "Sem evidência",
                       "Último erro": erro or "—"})
    return linhas


def indicadores_impacto():
    return {"Chamados resolvidos automaticamente": None,
            "Follow-ups confirmados": None,
            "Intervenções evitadas": None,
            "Falhas": None,
            "Minutos economizados": None}
