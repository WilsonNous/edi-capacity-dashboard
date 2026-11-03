"""Read-only VR01 Blueprint recovery status from the durable MySQL catalog.

Never touches Redmine, Graph, SQLite or writes to MySQL. A missing contact
in this catalog is not evidence that the original Blueprint lacks a contact.
"""
from __future__ import annotations

import json

from ednna.mysql_storage import connect

PILOTS = {50318: "SUPERMERCADOS MAMBO"}


def diagnosticar(chamado_id: int = 50318) -> dict:
    if chamado_id not in PILOTS:
        raise ValueError("Piloto nao homologado")
    cliente = PILOTS[chamado_id]
    result = {
        "chamado_id": chamado_id,
        "cliente_verificado": cliente,
        "modo": "SOMENTE_LEITURA_MYSQL",
        "redmine_consultado": False,
        "sqlite_consultado": False,
        "emails_enviados": 0,
        "redmine_escritas": 0,
        "mysql_escritas": 0,
    }
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT area, source_id, documento_id, chamado_id,
                              attachment_id, fonte_arquivo, email
                       FROM eddy_blueprint_participants
                       WHERE cliente=%s AND ativo=1
                       ORDER BY source_id""",
                    (cliente,),
                )
                rows = cur.fetchall()
    except Exception as exc:
        result.update(estado="CATALOGO_INDISPONIVEL", erro_tipo=type(exc).__name__)
        return result
    valid = [r for r in rows if r[1] and r[2] and r[3] and r[6]]
    gerente = [r for r in valid if "GERENTE/COORD" in str(r[0] or "").upper()]
    result.update(
        estado=("CONTATOS_RASTREAVEIS_NO_MYSQL" if valid
                else "SEM_CONTATOS_PERSISTIDOS_REDMINE_NAO_VERIFICADO"),
        registros_ativos=len(rows),
        contatos_rastreaveis=len(valid),
        gerentes_projeto_cliente=len(gerente),
        origens_documentais=len({(r[2], r[4]) for r in valid}),
        requer_aprovacao_destinatario=True,
    )
    return result


def main() -> None:
    print(json.dumps(diagnosticar(), ensure_ascii=False))


if __name__ == "__main__":
    main()
