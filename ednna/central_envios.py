"""Portão central de comunicação externa NETUNNA: dias úteis, 07-19h BRT.

Calendários versionados por ano e localidade, fornecidos pela operação. Sem
calendário validado ou localidade definida: falha fechada (nenhum Graph POST).
Atividades internas não usam este portão.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")


class JanelaExternaFechada(RuntimeError):
    def __init__(self, motivo: str, proxima_janela: str | None = None):
        self.motivo = motivo
        self.proxima_janela = proxima_janela
        super().__init__(f"{motivo}; proxima_janela={proxima_janela or 'INDEFINIDA'}")


def _calendario(ano: int, uf: str, municipio: str) -> set[str]:
    arquivo = Path(os.getenv("EDDY_FERIADOS_ARQUIVO", "/home/data/eddy_feriados.json"))
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        if not isinstance(dados, dict):
            raise ValueError("formato invalido")
        # Exigir as três listas para cada ano: não presumir feriado inexistente.
        chaves = (f"nacional:{ano}", f"estadual:{uf}:{ano}", f"municipal:{uf}:{municipio}:{ano}")
        if any(chave not in dados or not isinstance(dados[chave], list) for chave in chaves):
            raise ValueError("calendario nacional/estadual/municipal incompleto")
        feriados = set()
        for chave in chaves:
            for dia in dados[chave]:
                data = datetime.strptime(str(dia), "%Y-%m-%d").date()
                if data.year != ano:
                    raise ValueError("feriado fora do ano")
                feriados.add(data.isoformat())
        return feriados
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise JanelaExternaFechada(f"CALENDARIO_INDISPONIVEL:{type(exc).__name__}") from exc


def avaliar_janela_externa(*, agora: datetime | None = None, uf: str | None = None,
                           municipio: str | None = None) -> dict:
    uf = str(uf or os.getenv("EDDY_ENVIO_UF", "")).strip().upper()
    municipio = str(municipio or os.getenv("EDDY_ENVIO_MUNICIPIO", "")).strip().upper()
    if not uf or not municipio:
        raise JanelaExternaFechada("LOCALIDADE_NAO_CONFIGURADA")
    instante = (agora or datetime.now(TZ)).astimezone(TZ)
    feriados = _calendario(instante.year, uf, municipio)
    permitido = instante.weekday() < 5 and instante.date().isoformat() not in feriados and time(7) <= instante.time() < time(19)
    if permitido:
        return {"permitido": True, "motivo": "JANELA_ABERTA", "proxima_janela": None}
    # O calendário do próximo ano também precisa estar validado antes de agendar.
    candidato = instante.date()
    for _ in range(370):
        if candidato.year != instante.year:
            feriados = _calendario(candidato.year, uf, municipio)
        if candidato.weekday() < 5 and candidato.isoformat() not in feriados:
            abertura = datetime.combine(candidato, time(7), TZ)
            if abertura > instante:
                return {"permitido": False, "motivo": "FORA_DA_JANELA_OU_FERIADO",
                        "proxima_janela": abertura.isoformat()}
        candidato += timedelta(days=1)
    raise JanelaExternaFechada("PROXIMA_JANELA_INDEFINIDA")


def exigir_janela_externa(*, agora: datetime | None = None) -> dict:
    estado = avaliar_janela_externa(agora=agora)
    if not estado["permitido"]:
        raise JanelaExternaFechada(estado["motivo"], estado["proxima_janela"])
    return estado
