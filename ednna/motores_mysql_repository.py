"""MySQL read model for EDNNA motors. Never silently use legacy SQLite.

The tables are intentionally independent of VR01 and have no automatic
authorization or outbound side effects. Migration of historical rows must be
performed explicitly before the inventory can be considered complete.
"""
from __future__ import annotations

from ednna.mysql_storage import connect

DDL = (
    """CREATE TABLE IF NOT EXISTS eddy_aprendizados_operacionais (regra_id VARCHAR(191) NOT NULL PRIMARY KEY, player VARCHAR(191) NOT NULL, operacao VARCHAR(80) NOT NULL, estado VARCHAR(80) NOT NULL, completude INT NOT NULL DEFAULT 0, payload_json LONGTEXT NOT NULL, atualizado_em VARCHAR(40) NOT NULL, KEY idx_aprendizado_estado (estado), KEY idx_aprendizado_player (player,operacao)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS eddy_revisoes_regras_operacionais (regra_id VARCHAR(191) NOT NULL PRIMARY KEY, estado VARCHAR(80) NOT NULL DEFAULT 'PENDENTE_REVISAO', destinatario_confirmado TEXT, observacoes TEXT, revisado_por VARCHAR(191), revisado_em VARCHAR(40), homologado_em VARCHAR(40), payload_json LONGTEXT NOT NULL, atualizado_em VARCHAR(40) NOT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS eddy_mineracao_aberturas (
       chamado_id BIGINT NOT NULL PRIMARY KEY,
       player VARCHAR(191) NOT NULL,
       status VARCHAR(191), assunto TEXT, score INT NOT NULL DEFAULT 0,
       payload_json LONGTEXT NOT NULL, minerado_em VARCHAR(40) NOT NULL,
       KEY idx_mineracao_player (player)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
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

def estado_regra(regra_id: str) -> dict | None:
    preparar_modelo()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT regra_id,versao,player,estado,homologado_por,homologado_em,
                        nota,snapshot_sha256,motivo FROM eddy_homologacoes_regras
                        WHERE regra_id=%s ORDER BY versao DESC LIMIT 1""", (regra_id,))
            row=cur.fetchone()
            return dict(zip([d[0] for d in cur.description],row)) if row else None

def homologar(regra_id: str, player: str, estado: str, professor: str,
              nota: int, raw: str, sha: str, motivo: str, agora: str) -> dict:
    """Version allocation serialized by MySQL advisory lock across processes."""
    preparar_modelo()
    if not regra_id or not professor or estado not in ("ATIVA","EM_OBSERVACAO"):
        raise ValueError("Homologacao invalida")
    # Named lock prevents two workers from allocating the same version.
    import hashlib
    lock="eddy_homologacao_"+hashlib.sha256(regra_id.encode()).hexdigest()[:32]
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT GET_LOCK(%s, 10)", (lock,))
            if cur.fetchone()[0] != 1:
                raise TimeoutError("Homologacao concorrente: bloqueio indisponivel")
            try:
                cur.execute("SELECT COALESCE(MAX(versao),0) FROM eddy_homologacoes_regras WHERE regra_id=%s", (regra_id,))
                versao=int(cur.fetchone()[0])+1
                cur.execute("""UPDATE eddy_homologacoes_regras SET estado='SUSPENSA',atualizado_em=%s
                            WHERE regra_id=%s AND estado IN ('ATIVA','EM_OBSERVACAO')""", (agora,regra_id))
                cur.execute("""INSERT INTO eddy_homologacoes_regras
                  (regra_id,versao,player,estado,homologado_por,homologado_em,nota,snapshot_json,snapshot_sha256,motivo,atualizado_em)
                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                  (regra_id,versao,player,estado,professor,agora,nota,raw,sha,motivo,agora))
                conn.commit()
            finally:
                cur.execute("SELECT RELEASE_LOCK(%s)", (lock,))
    return {"regra_id":regra_id,"versao":versao,"estado":estado,"nota":nota,
            "homologado_por":professor,"homologado_em":agora,"snapshot_sha256":sha}

def alterar_estado(regra_id: str, estado: str, professor: str, motivo: str, agora: str) -> dict:
    if estado not in ("ATIVA","EM_OBSERVACAO","SUSPENSA"):
        raise ValueError("Estado invalido")
    preparar_modelo()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM eddy_homologacoes_regras WHERE regra_id=%s ORDER BY versao DESC LIMIT 1 FOR UPDATE",(regra_id,))
            row=cur.fetchone()
            if not row:
                raise ValueError("Regra ainda nao homologada")
            cur.execute("UPDATE eddy_homologacoes_regras SET estado=%s,motivo=%s,atualizado_em=%s WHERE id=%s",
                        (estado,(professor+": "+motivo).strip(),agora,row[0]))
    return estado_regra(regra_id)

def atualizar_motivo(regra_id: str, versao: int, motivo: str, agora: str) -> None:
    preparar_modelo()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE eddy_homologacoes_regras SET motivo=%s,atualizado_em=%s WHERE regra_id=%s AND versao=%s",
                        (motivo,agora,regra_id,versao))

def salvar_mineracao_abertura(r: dict, agora: str) -> None:
    import json
    preparar_modelo()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO eddy_mineracao_aberturas
              (chamado_id,player,status,assunto,score,payload_json,minerado_em)
              VALUES (%s,%s,%s,%s,%s,%s,%s)
              ON DUPLICATE KEY UPDATE player=VALUES(player),status=VALUES(status),
              assunto=VALUES(assunto),score=VALUES(score),
              payload_json=VALUES(payload_json),minerado_em=VALUES(minerado_em)""",
              (r["chamado_id"],r["player"],r["status"],r["assunto"],r["score"],
               json.dumps(r,ensure_ascii=False),agora))

def salvar_proposta_abertura(p: dict, agora: str) -> None:
    import json
    preparar_modelo()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO eddy_propostas_regras_abertura
              (regra_id,player,estado,evidencias,compatibilidade,payload_json,atualizado_em)
              VALUES (%s,%s,%s,%s,%s,%s,%s)
              ON DUPLICATE KEY UPDATE player=VALUES(player),estado=VALUES(estado),
              evidencias=VALUES(evidencias),compatibilidade=VALUES(compatibilidade),
              payload_json=VALUES(payload_json),atualizado_em=VALUES(atualizado_em)""",
              (p["regra_id"],p["player"],p["estado"],p["evidencias"],p["compatibilidade"],
               json.dumps(p,ensure_ascii=False),agora))

def atualizar_proposta_abertura(p: dict, agora: str) -> None:
    import json
    preparar_modelo()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE eddy_propostas_regras_abertura SET payload_json=%s,
                           atualizado_em=%s WHERE regra_id=%s""",
                        (json.dumps(p,ensure_ascii=False),agora,p["regra_id"]))

def listar_mineracoes_player(player: str) -> list[dict]:
    import json
    preparar_modelo()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT payload_json FROM eddy_mineracao_aberturas WHERE player=%s",(player,))
            return [json.loads(row[0]) for row in cur.fetchall()]

def salvar_aprendizado_operacional(resultado: dict) -> None:
    import json
    preparar_modelo()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO eddy_aprendizados_operacionais
                (regra_id,player,operacao,estado,completude,payload_json,atualizado_em)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE player=VALUES(player),operacao=VALUES(operacao),
                estado=VALUES(estado),completude=VALUES(completude),
                payload_json=VALUES(payload_json),atualizado_em=VALUES(atualizado_em)""",
                (resultado["regra_id"],resultado["player"],resultado["operacao"],
                 resultado["estado"],resultado["completude"],json.dumps(resultado,ensure_ascii=False),
                 resultado["aprendido_em"]))

def obter_aprendizado_operacional(regra_id: str) -> dict | None:
    import json
    preparar_modelo()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT payload_json FROM eddy_aprendizados_operacionais WHERE regra_id=%s",(regra_id,))
            row=cur.fetchone()
            return json.loads(row[0]) if row else None

def listar_aprendizados_incompletos() -> list[dict]:
    import json
    preparar_modelo()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT payload_json FROM eddy_aprendizados_operacionais
                        WHERE estado IN ('APRENDIZADO_INCOMPLETO','AGUARDANDO_ENRIQUECIMENTO')""")
            return [json.loads(row[0]) for row in cur.fetchall()]

def obter_revisao_operacional(regra_id: str) -> dict:
    import json
    preparar_modelo()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM eddy_revisoes_regras_operacionais WHERE regra_id=%s",(regra_id,))
            row=cur.fetchone()
            if not row:
                return {"regra_id":regra_id,"estado":"PENDENTE_REVISAO"}
            d=dict(zip([x[0] for x in cur.description],row))
            try:
                d["payload"]=json.loads(d.get("payload_json") or "{}")
            except (ValueError,TypeError):
                d["payload"]={}
            return d

def salvar_revisao_operacional(regra_id: str, email: str, observacoes: str,
                              revisado_por: str, payload: dict, agora: str) -> None:
    import json
    preparar_modelo()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO eddy_revisoes_regras_operacionais
                (regra_id,estado,destinatario_confirmado,observacoes,revisado_por,revisado_em,payload_json,atualizado_em)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE estado='REVISADA',
                destinatario_confirmado=VALUES(destinatario_confirmado),
                observacoes=VALUES(observacoes),revisado_por=VALUES(revisado_por),
                revisado_em=VALUES(revisado_em),payload_json=VALUES(payload_json),
                atualizado_em=VALUES(atualizado_em)""",
                (regra_id,"REVISADA",email,observacoes,revisado_por,agora,
                 json.dumps(payload,ensure_ascii=False),agora))

def homologar_revisao_operacional(regra_id: str, revisado_por: str, agora: str) -> None:
    preparar_modelo()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE eddy_revisoes_regras_operacionais
                SET estado='HOMOLOGADA',revisado_por=%s,homologado_em=%s,atualizado_em=%s
                WHERE regra_id=%s AND estado IN ('REVISADA','HOMOLOGADA')""",
                (revisado_por,agora,agora,regra_id))
            if cur.rowcount != 1:
                raise ValueError("Revisao nao homologavel")

def listar_regras_operacionais() -> list[dict]:
    preparar_modelo()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT a.regra_id,a.player,a.operacao,a.estado,a.completude,a.payload_json,a.atualizado_em,
                r.estado AS estado_revisao,r.destinatario_confirmado,r.observacoes,
                r.revisado_em,r.homologado_em
                FROM eddy_aprendizados_operacionais a
                LEFT JOIN eddy_revisoes_regras_operacionais r ON r.regra_id=a.regra_id
                WHERE a.operacao='INCLUSAO' ORDER BY a.player,a.regra_id""")
            cols=[x[0] for x in cur.description]
            return [dict(zip(cols,row)) for row in cur.fetchall()]

def salvar_autorizacao_motor(regra_id: str, modo: str, autorizado_por: str,
                            observacoes: str, agora: str) -> None:
    preparar_modelo()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO eddy_autorizacoes_motor
                (regra_id,modo,autorizado_por,autorizado_em,observacoes,atualizado_em)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE modo=VALUES(modo),autorizado_por=VALUES(autorizado_por),
                autorizado_em=VALUES(autorizado_em),observacoes=VALUES(observacoes),
                atualizado_em=VALUES(atualizado_em)""",
                (regra_id,modo,autorizado_por,agora,observacoes,agora))
