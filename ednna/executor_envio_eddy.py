"""Executor assistido EDDY com reserva SQLite e envio desabilitado por padrão.

A reserva é persistente, atômica e conservadora: falha ambígua nunca
dispara uma segunda tentativa automaticamente.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ednna.aprovacao_envio_edi import avaliar_autorizacao_envio


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def executar_envio_assistido(
    *, chamado_id: int, minuta: dict[str, Any], aprovacao: dict[str, Any],
    remetente: str, db_path: str, habilitar_envio: bool = False,
    enviar=None,
) -> dict[str, Any]:
    """Envia no máximo uma tentativa por chamado + digest, sem retry automático.

    SQLite deve estar em volume compartilhado/persistente por todos os workers.
    Se o Graph aceitar mas a confirmação se perder, a operação fica INDETERMINADA.
    """
    if int(chamado_id) <= 0:
        raise ValueError("chamado_id inválido")
    gate = avaliar_autorizacao_envio(minuta, aprovacao)
    if not gate["autorizacao_valida"]:
        return {"estado": "BLOQUEADO", "pendencias": gate["pendencias"], "envio_realizado": False}
    if not habilitar_envio or os.getenv("EDDY_GRAPH_SEND_ENABLED", "").strip().lower() != "true":
        return {"estado": "SIMULACAO", "digest": gate["digest_minuta"], "envio_realizado": False}
    if not remetente or not db_path:
        raise ValueError("remetente e db_path são obrigatórios")
    path = Path(db_path)
    if not path.parent.exists():
        raise ValueError("diretório de banco inexistente; exigir armazenamento persistente compartilhado")
    digest = gate["digest_minuta"]
    # Um chamado só pode ter uma solicitação externa em andamento.\n    # Mudanças no texto não autorizam novo envio sem conciliação humana.\n    chave = f"{int(chamado_id)}:{digest}"
    with sqlite3.connect(str(path), timeout=30, isolation_level=None) as con:
        con.execute("PRAGMA busy_timeout=30000")
        con.execute("""CREATE TABLE IF NOT EXISTS eddy_envios (
            chave TEXT PRIMARY KEY, chamado_id INTEGER NOT NULL, digest TEXT NOT NULL,
            estado TEXT NOT NULL, criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL,
            graph_message_id TEXT NOT NULL DEFAULT '', erro TEXT NOT NULL DEFAULT ''
        )""")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_eddy_envios_chamado ON eddy_envios(chamado_id)")\n        con.execute("BEGIN IMMEDIATE")
        try:
            registro = con.execute("SELECT estado, graph_message_id, digest FROM eddy_envios WHERE chamado_id=?", (int(chamado_id),)).fetchone()
            if registro:
                con.execute("COMMIT")
                return {"estado": "JA_REGISTRADO", "estado_anterior": registro[0],
                        "graph_message_id": registro[1], "envio_realizado": False, "chave": chave,\n                        "minuta_alterada": registro[2] != digest}
            agora = _agora()
            con.execute("INSERT INTO eddy_envios (chave,chamado_id,digest,estado,criado_em,atualizado_em) VALUES (?,?,?,?,?,?)",
                        (chave, int(chamado_id), digest, "RESERVADO", agora, agora))
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
    # RESERVADO é deliberadamente tratado como ambíguo após interrupção.
    try:
        if enviar is None:
            from ednna.email_sender import enviar_email_graph
            enviar = enviar_email_graph
        resposta = enviar(remetente=remetente, para=[minuta["destinatario"]], cc=[],
                          assunto=minuta["assunto"], corpo=minuta["corpo"], chamado_id=int(chamado_id))
        if not resposta.get("ok") or resposta.get("status_code") != 202:
            raise RuntimeError("Graph não confirmou HTTP 202")
        estado = "ACEITO_GRAPH"
        mid = str(resposta.get("message_id") or "")
        erro = ""
    except Exception as exc:
        estado, mid, erro = "INDETERMINADO", "", str(exc)[:500]
    with sqlite3.connect(str(path), timeout=30) as con:
        con.execute("UPDATE eddy_envios SET estado=?, atualizado_em=?, graph_message_id=?, erro=? WHERE chave=?",
                    (estado, _agora(), mid, erro, chave))
    return {"estado": estado, "chave": chave, "graph_message_id": mid,
            "envio_realizado": estado == "ACEITO_GRAPH",
            "redmine_atualizado": False, "requer_conciliacao": estado == "INDETERMINADO"}
