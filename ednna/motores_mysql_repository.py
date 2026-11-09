"""MySQL read model for EDNNA motors. Never silently use legacy SQLite.

The tables are intentionally independent of VR01 and have no automatic
authorization or outbound side effects. Migration of historical rows must be
performed explicitly before the inventory can be considered complete.
"""
from __future__ import annotations

from ednna.mysql_storage import connect

DDL = (
    """CREATE TABLE IF NOT EXISTS eddy_homologacoes_regras (
       id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
       regra_id VARCHAR(191) NOT NULL,
       versao INT NOT NULL,
       player VARCHAR(191),
       estado VARCHAR(40) NOT NULL,
       homologado_por VARCHAR(191) NOT NULL,
       homologado_em VARCHAR(40) NOT NULL,
       nota INT NOT NULL,
       snapshot_json LONGTEXT NOT NULL,
       snapshot_sha256 CHAR(64) NOT NULL,
       motivo TEXT,
       atualizado_em VARCHAR(40) NOT NULL,
       UNIQUE KEY uq_regra_versao (regra_id,versao),
       KEY idx_regra_estado (regra_id,estado)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS eddy_autorizacoes_motor (
       regra_id VARCHAR(191) NOT NULL PRIMARY KEY,
       modo VARCHAR(40) NOT NULL DEFAULT 'BLOQUEADA',
       autorizado_por VARCHAR(191),
       autorizado_em VARCHAR(40),
       observacoes TEXT,
       atualizado_em VARCHAR(40) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS eddy_propostas_regras_abertura (
       regra_id VARCHAR(191) NOT NULL PRIMARY KEY,
       player VARCHAR(191) NOT NULL,
       estado VARCHAR(40) NOT NULL DEFAULT 'CANDIDATA',
       evidencias INT NOT NULL DEFAULT 0,
       compatibilidade INT NOT NULL DEFAULT 0,
       payload_json LONGTEXT NOT NULL,
       atualizado_em VARCHAR(40) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
)

def preparar_modelo() -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            for ddl in DDL:
                cur.execute(ddl)

def inventario() -> dict:
    """Return data availability, not a false claim of successful migration."""
    preparar_modelo()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM eddy_homologacoes_regras")
            homologacoes = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM eddy_autorizacoes_motor")
            autorizacoes = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM eddy_propostas_regras_abertura")
            propostas = int(cur.fetchone()[0])
    return {"homologacoes":homologacoes,"autorizacoes":autorizacoes,
            "propostas":propostas,
            "estado":"SEM_HOMOLOGACOES_MYSQL" if not homologacoes else "INVENTARIO_MYSQL_DISPONIVEL"}

def listar_homologacoes() -> list[dict]:
    preparar_modelo()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT h.regra_id,h.versao,h.player,h.estado,h.homologado_por,
                       h.homologado_em,h.nota,h.motivo
                       FROM eddy_homologacoes_regras h
                       INNER JOIN (
                         SELECT regra_id,MAX(versao) versao
                         FROM eddy_homologacoes_regras GROUP BY regra_id
                       ) ult ON ult.regra_id=h.regra_id AND ult.versao=h.versao
                       ORDER BY h.player,h.regra_id""")
            cols=[d[0] for d in cur.description]
            return [dict(zip(cols,row)) for row in cur.fetchall()]

def obter_autorizacao(regra_id: str) -> dict:
    preparar_modelo()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT regra_id,modo,autorizado_por,autorizado_em,observacoes,atualizado_em FROM eddy_autorizacoes_motor WHERE regra_id=%s",(regra_id,))
            row=cur.fetchone()
            if not row:
                return {"regra_id":regra_id,"modo":"BLOQUEADA"}
            return dict(zip([d[0] for d in cur.description],row))

def listar_propostas() -> list[dict]:
    import json
    preparar_modelo()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT payload_json FROM eddy_propostas_regras_abertura ORDER BY player")
            return [json.loads(row[0]) for row in cur.fetchall()]

def autorizar_abertura_assistida(regra_id: str, responsavel: str, justificativa: str, agora: str) -> None:
    """Atomic authorization for assisted preparation only; never permits dispatch."""
    if not regra_id.startswith("ABERTURA-") or not responsavel or len(justificativa.strip()) < 20:
        raise ValueError("Autorizacao de abertura invalida")
    preparar_modelo()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO eddy_autorizacoes_motor
              (regra_id,modo,autorizado_por,autorizado_em,observacoes,atualizado_em)
              VALUES (%s,%s,%s,%s,%s,%s)
              ON DUPLICATE KEY UPDATE modo=VALUES(modo),
              autorizado_por=VALUES(autorizado_por), autorizado_em=VALUES(autorizado_em),
              observacoes=VALUES(observacoes), atualizado_em=VALUES(atualizado_em)""",
              (regra_id,"ASSISTIDA",responsavel,agora,
               "Motor de abertura: somente preparação assistida; sem envio externo. "+justificativa,agora))
