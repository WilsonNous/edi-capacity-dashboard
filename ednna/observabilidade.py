"""Eventos operacionais persistentes para observabilidade dentro da EDNNA."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "ednna_observabilidade.db"


def log_event(categoria: str, evento: str, *, nivel: str = "INFO", chamado_id: int | None = None,
              regra_id: str = "", player: str = "", detalhe: str = "") -> None:
    try:
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
            con.execute("INSERT INTO eventos(created_at,nivel,categoria,evento,chamado_id,regra_id,player,detalhe) VALUES(?,?,?,?,?,?,?,?)",
                        (datetime.now(timezone.utc).isoformat(), str(nivel).upper(), str(categoria), str(evento),
                         int(chamado_id) if chamado_id else None, str(regra_id or ''), str(player or ''), str(detalhe or '')[:4000]))
    except Exception:
        pass


def listar_eventos(*, limite: int = 300, nivel: str = "", categoria: str = "", chamado_id: int | None = None, busca: str = "") -> list[dict]:
    if not DB.exists():
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
    with sqlite3.connect(DB, timeout=5) as con:
        con.row_factory = sqlite3.Row
        return [dict(r) for r in con.execute(sql,args).fetchall()]
