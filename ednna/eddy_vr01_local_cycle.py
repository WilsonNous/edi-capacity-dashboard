"""Offline-first VR01 analysis: MySQL only, no Redmine/Graph/SQLite calls.

Redmine acquisition, ownership claims and returns are separate, explicit
operations. This entry point never grants permission for external execution.
"""
from __future__ import annotations

from ednna.eddy_vr_mysql_operation import operacao_vr_mysql
from ednna.eddy_vr01_offline_proposals import preparar_intencoes_locais


def executar_ciclo_local_vr01() -> dict:
    try:
        operation = operacao_vr_mysql()
    except Exception as exc:
        return {
            "estado": "BLOQUEADO_MYSQL_INDISPONIVEL",
            "erro": type(exc).__name__,
            "operacao": None,
            "redmine_consultas": 0,
            "redmine_escritas": 0,
            "envios_realizados": 0,
        }
    try:
        propostas = preparar_intencoes_locais()
    except Exception as exc:
        return {
            "estado": "BLOQUEADO_PERSISTENCIA_PROPOSTAS",
            "erro": type(exc).__name__,
            "operacao": operation,
            "redmine_consultas": 0,
            "redmine_escritas": 0,
            "envios_realizados": 0,
            "acoes_externas_autorizadas": False,
        }
    return {
        "estado": "VR01_ANALISE_LOCAL_COM_PROPOSTAS", 
        "propostas": propostas,
        "operacao": operation,
        "fonte": "mysql",
        "redmine_confirmado_agora": False,
        "acoes_externas_autorizadas": False,
        "redmine_consultas": 0,
        "redmine_escritas": 0,
        "envios_realizados": 0,
    }
