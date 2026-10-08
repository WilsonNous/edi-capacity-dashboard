"""Eventos operacionais persistentes para observabilidade dentro da EDNNA."""
from __future__ import annotations

import sqlite3
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# No Azure, manter o histórico no mesmo volume persistente dos demais bancos.
# Em desenvolvimento local, conservar o caminho anterior.
DB = Path(os.getenv("EDNNA_OBSERVABILIDADE_DB") or (
    "/home/data/ednna_observabilidade.db"
    if os.getenv("WEBSITE_INSTANCE_ID") or os.getenv("WEBSITE_SITE_NAME")
    else str(ROOT / "data" / "ednna_observabilidade.db")
))
LEGACY_DB = ROOT / "data" / "ednna_observabilidade.db"


def _preparar_db() -> None:
    """Migra eventos legados para o volume persistente quando possível."""
    if DB.exists() or DB == LEGACY_DB or not LEGACY_DB.is_file():
        return
    DB.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(LEGACY_DB, timeout=5) as origem:
            with sqlite3.connect(DB, timeout=5) as destino:
                origem.backup(destino)
    except (OSError, sqlite3.Error):
        # Não ocultar dados antigos: leitura continua disponível no legado.
        pass


def _db_leitura() -> Path:
    _preparar_db()
    return DB if DB.exists() else LEGACY_DB



def log_event(categoria: str, evento: str, *, nivel: str = "INFO", chamado_id: int | None = None,
              regra_id: str = "", player: str = "", detalhe: str = "", dedup_seconds: int = 0) -> None:
    try:
        _preparar_db()
        DB.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DB, timeout=5) as con:
            con.execute("""CREATE TABLE IF NOT EXISTS eventos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                nivel TEXT NOT NULL,
                categoria TEXT NOT NULL,
                evento TEXT NOT NULL,
                chamado_id INTEGER,
                regra_id TEXT,
                player TEXT,
                detalhe TEXT
            )""")
            con.execute("CREATE INDEX IF NOT EXISTS idx_obs_created ON eventos(created_at DESC)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_obs_chamado ON eventos(chamado_id)")
            agora = datetime.now(timezone.utc)
            if int(dedup_seconds or 0) > 0:
                desde = (agora - timedelta(seconds=int(dedup_seconds))).isoformat()
                existe = con.execute(
                    """SELECT 1 FROM eventos WHERE created_at>=? AND categoria=? AND evento=?
                       AND COALESCE(chamado_id,0)=? AND COALESCE(regra_id,'')=? AND COALESCE(player,'')=? LIMIT 1""",
                    (desde, str(categoria), str(evento), int(chamado_id or 0), str(regra_id or ''), str(player or ''))
                ).fetchone()
                if existe:
                    return
            con.execute("INSERT INTO eventos(created_at,nivel,categoria,evento,chamado_id,regra_id,player,detalhe) VALUES(?,?,?,?,?,?,?,?)",
                        (agora.isoformat(), str(nivel).upper(), str(categoria), str(evento),
                         int(chamado_id) if chamado_id else None, str(regra_id or ''), str(player or ''), str(detalhe or '')[:4000]))
    except Exception:
        pass


def listar_eventos(*, limite: int = 300, nivel: str = "", categoria: str = "", chamado_id: int | None = None, busca: str = "") -> list[dict]:
    origem = _db_leitura()
    if not origem.exists():
        return []
    sql = "SELECT id,created_at,nivel,categoria,evento,chamado_id,regra_id,player,detalhe FROM eventos WHERE 1=1"
    args: list[object] = []
    if nivel:
        sql += " AND nivel=?"; args.append(nivel.upper())
    if categoria:
        sql += " AND categoria=?"; args.append(categoria)
    if chamado_id:
        sql += " AND chamado_id=?"; args.append(int(chamado_id))
    if busca:
        sql += " AND (evento LIKE ? OR detalhe LIKE ? OR regra_id LIKE ? OR player LIKE ?)"
        q=f"%{busca}%"; args.extend([q,q,q,q])
    sql += " ORDER BY id DESC LIMIT ?"; args.append(max(1,min(int(limite),2000)))
    with sqlite3.connect(origem, timeout=5) as con:
        con.row_factory = sqlite3.Row
        return [dict(r) for r in con.execute(sql,args).fetchall()]


def url_chamado(chamado_id) -> str:
    """URL canônica para qualquer evento vinculado a chamado."""
    try:
        cid = int(chamado_id)
        return f"https://chamados.nteia.com/issues/{cid}" if cid > 0 else ""
    except (TypeError, ValueError):
        return ""


def status_evento(evento: dict) -> str:
    """Resultado visível conservador: tentativa não equivale a sucesso."""
    nivel = str(evento.get("nivel") or "").upper()
    texto = " ".join(str(evento.get(k) or "") for k in ("evento", "detalhe")).upper()
    if nivel == "ERROR" or any(x in texto for x in ("FALHA", "ERRO ", "TIMEOUT")):
        return "Falha"
    if nivel == "BLOCKED" or any(x in texto for x in ("BLOQUEADO", "BLOQUEADA")):
        return "Bloqueada"
    if any(x in texto for x in ("CONFIRMADO", "CONFIRMADA", "CONCLUÍDO", "CONCLUIDO", "SUCESSO", "HTTP 202", "ATUALIZADO")):
        return "Concluída"
    return "Registrada / verificar resultado"


def detalhe_publico(evento: dict) -> str:
    """Resumo operacional seguro para usuários de consulta.

    Detalhes livres podem conter e-mail, cabeçalhos ou dados técnicos:
    não são expostos no painel de acesso geral.
    """
    categoria = str(evento.get("categoria") or "").upper()
    nivel = str(evento.get("nivel") or "").upper()
    if nivel in {"ERROR", "BLOCKED"}:
        return "Ocorrência registrada; equipe EDI pode consultar o diagnóstico."
    if categoria == "FOLLOWUP":
        return "Movimentação de acompanhamento registrada."
    if categoria == "REDMINE":
        return "Movimentação no Redmine registrada."
    if categoria == "EMAIL":
        return "Movimentação de e-mail registrada."
    return "Movimentação operacional registrada."
