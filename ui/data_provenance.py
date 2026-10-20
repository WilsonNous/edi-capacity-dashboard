"""Explain the source and age of EDDY Home indicators without extra queries."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

BR = ZoneInfo("America/Sao_Paulo")


def fonte_carteira(frame, *, agora=None) -> dict:
    """Never infer freshness from page-load time; read persisted snapshot timestamp."""
    if frame is None or frame.empty:
        return {"fonte": "indisponível", "atualizado_em": None, "idade_minutos": None, "situacao": "sem dados"}
    fonte = str(frame["_fonte_operacional"].iloc[0]) if "_fonte_operacional" in frame else "desconhecida"
    marca = str(frame["_snapshot_atualizado_em"].iloc[0]) if "_snapshot_atualizado_em" in frame else ""
    nome = {
        "painel.db/status=open": "Redmine via snapshot do Painel EDI (SQLite)",
        "mysql/eddy_chamados": "Redmine via carteira persistida no MySQL",
        "ednna.db/fallback": "Memória histórica SQLite (contingência)",
    }.get(fonte, fonte)
    if not marca or marca.lower() in ("none", "nan", "nat"):
        return {"fonte": nome, "atualizado_em": None, "idade_minutos": None, "situacao": "data desconhecida"}
    try:
        data = datetime.fromisoformat(marca.replace("Z", "+00:00"))
        if data.tzinfo is None:
            data = data.replace(tzinfo=BR)
        data = data.astimezone(BR)
        now = agora or datetime.now(BR)
        age = max(0, int((now - data).total_seconds() // 60))
        return {"fonte": nome, "atualizado_em": data.strftime("%d/%m/%Y às %H:%M"),
                "idade_minutos": age, "situacao": "possivelmente desatualizado" if age >= 30 else "snapshot recente"}
    except (TypeError, ValueError, OverflowError):
        return {"fonte": nome, "atualizado_em": None, "idade_minutos": None, "situacao": "data inválida"}
