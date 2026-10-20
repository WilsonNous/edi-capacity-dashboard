"""Leitura da carteira MySQL somente quando coincide com o snapshot Redmine.

Não executa automações e nunca apresenta importações parciais como carteira completa.
"""
from __future__ import annotations
import json
from ednna.mysql_storage import connect


def carregar_carteira_mysql(ids_esperados: set[int], snapshot_em: str) -> list[dict] | None:
    """Retorna payloads Redmine do MySQL apenas com cobertura integral e mesma versão."""
    if not ids_esperados or not snapshot_em:
        return None
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, payload_json, sincronizado_em FROM eddy_chamados"
            )
            rows = cursor.fetchall()
    # Registros históricos ou encerrados não devem aparecer na carteira ativa.
    por_id = {int(row[0]): row for row in rows if int(row[0]) in ids_esperados}
    if set(por_id) != ids_esperados:
        return None
    if any(row[2] != snapshot_em for row in por_id.values()):
        return None
    issues = [json.loads(por_id[issue_id][1]) for issue_id in sorted(ids_esperados)]
    if any(not isinstance(issue, dict) or int(issue.get("id", 0)) != issue_id
           for issue_id, issue in zip(sorted(ids_esperados), issues)):
        return None
    return issues
