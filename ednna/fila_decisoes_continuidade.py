"""Fila assistida de decisões da continuidade; leitura sem efeitos externos."""
from __future__ import annotations
from datetime import datetime, timezone

ESTADOS_REVISAO = frozenset({"REVISAO_HUMANA", "REVISAO_RETORNO", "AGUARDANDO_DOCUMENTACAO"})


def organizar_fila(decisoes: list[dict], *, agora: datetime | None = None, limite: int = 100) -> dict:
    agora = agora or datetime.now(timezone.utc)
    itens = []
    for decisao in decisoes:
        estado = str(decisao.get("estado") or "")
        if estado not in ESTADOS_REVISAO:
            continue
        cid = int(decisao.get("chamado_id") or 0)
        if cid <= 0:
            continue
        prazo = str(decisao.get("prazo_revisao_em") or "")
        vencido = False
        if prazo:
            try:
                data = datetime.fromisoformat(prazo)
                if data.tzinfo is None:
                    data = data.replace(tzinfo=timezone.utc)
                vencido = data <= agora
            except ValueError:
                vencido = False
        itens.append({
            "chamado_id": cid,
            "estado": estado,
            "decisao": str(decisao.get("decisao") or ""),
            "motivo": str(decisao.get("motivo") or ""),
            "evidencia": str(decisao.get("evidencia") or ""),
            "responsavel_id": decisao.get("responsavel_id"),
            "responsavel_nome": str(decisao.get("responsavel_nome") or ""),
            "proxima_acao": str(decisao.get("proxima_acao") or ""),
            "prazo_revisao_em": prazo,
            "vencido": vencido,
            "executavel_automaticamente": False,
        })
    itens.sort(key=lambda x: (not x["vencido"], x["prazo_revisao_em"] or "9999", x["chamado_id"]))
    return {
        "total": len(itens),
        "vencidos": sum(int(x["vencido"]) for x in itens),
        "sem_responsavel": sum(int(not x["responsavel_id"]) for x in itens),
        "itens": itens[:max(0, int(limite))],
    }


def consultar_fila(limite: int = 100) -> dict:
    from ednna.continuidade_decisoes import listar_decisoes
    return organizar_fila(listar_decisoes(limite=2000), limite=limite)
