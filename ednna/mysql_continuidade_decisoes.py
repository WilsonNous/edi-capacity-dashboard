"""MySQL persistence for continuity decisions; no external side effects."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from ednna.mysql_storage import connect

_COLUMNS = ("chamado_id", "regra_id", "decisao", "estado", "proxima_acao",
            "responsavel_id", "responsavel_nome", "motivo", "evidencia",
            "prazo_revisao_em", "assinatura", "versao", "atualizado_em")

_DDL = """CREATE TABLE IF NOT EXISTS eddy_continuidade_decisoes (
    chamado_id BIGINT NOT NULL PRIMARY KEY,
    regra_id VARCHAR(191) NOT NULL DEFAULT '',
    decisao VARCHAR(191) NOT NULL,
    estado VARCHAR(191) NOT NULL,
    proxima_acao TEXT NOT NULL,
    responsavel_id BIGINT NULL,
    responsavel_nome VARCHAR(255) NOT NULL DEFAULT '',
    motivo TEXT NOT NULL,
    evidencia TEXT NOT NULL,
    prazo_revisao_em VARCHAR(40) NOT NULL DEFAULT '',
    assinatura CHAR(64) NOT NULL,
    versao INT NOT NULL,
    atualizado_em VARCHAR(40) NOT NULL,
    KEY idx_eddy_continuidade_atualizado (atualizado_em)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""


def _row(values):
    return dict(zip(_COLUMNS, values)) if values else {}


def materializar(itens, *, agora=None, proposta_fn=None, schema=1):
    if proposta_fn is None:
        raise ValueError("proposta_fn obrigatoria")
    agora = agora or datetime.now(timezone.utc)
    result = {"analisados": 0, "novos": 0, "alterados": 0, "inalterados": 0, "erros": 0}
    # A transaction and row lock prevent concurrent cycles from resetting a stable deadline.
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(_DDL)
            for item in itens:
                try:
                    proposta = proposta_fn(item, agora)
                    result["analisados"] += 1
                    assinatura = hashlib.sha256(json.dumps(
                        proposta, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                    cid = proposta["chamado_id"]
                    cur.execute("SELECT assinatura, prazo_revisao_em FROM eddy_continuidade_decisoes WHERE chamado_id=%s FOR UPDATE", (cid,))
                    anterior = cur.fetchone()
                    if anterior and anterior[0] == assinatura:
                        result["inalterados"] += 1
                        continue
                    if not proposta["prazo_revisao_em"]:
                        proposta["prazo_revisao_em"] = (anterior[1] if anterior else "") or (
                            agora + timedelta(hours=48)).isoformat(timespec="seconds")
                    values = {**proposta, "assinatura": assinatura,
                              "versao": schema, "atualizado_em": agora.isoformat()}
                    placeholders = ", ".join(["%s"] * len(_COLUMNS))
                    updates = ", ".join(f"{col}=VALUES({col})" for col in _COLUMNS if col != "chamado_id")
                    cur.execute(
                        f"INSERT INTO eddy_continuidade_decisoes ({', '.join(_COLUMNS)}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {updates}",
                        tuple(values[col] for col in _COLUMNS))
                    result["alterados" if anterior else "novos"] += 1
                except (KeyError, TypeError, ValueError) as exc:
                    result["erros"] += 1
                    print(f"[EDDY] Continuidade MySQL | erro={type(exc).__name__}", flush=True)
    return result


def obter(chamado_id):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(_DDL)
            cur.execute("SELECT " + ", ".join(_COLUMNS) +
                        " FROM eddy_continuidade_decisoes WHERE chamado_id=%s", (int(chamado_id),))
            return _row(cur.fetchone())


def listar(limite=300):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(_DDL)
            cur.execute("SELECT " + ", ".join(_COLUMNS) +
                        " FROM eddy_continuidade_decisoes ORDER BY atualizado_em DESC LIMIT %s",
                        (max(1, min(int(limite), 2000)),))
            return [_row(row) for row in cur.fetchall()]
