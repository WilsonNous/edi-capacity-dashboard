
"""Periodic autonomous VR01 scheduler on MySQL, independent of Streamlit sessions.

The existing worker remains unchanged.

The integrated pilot can optionally advance the BUSCAR_CONTATO_BP
transition after Redmine preflight and operational readiness checks.

This scheduler does not autonomously authorize Redmine writes or emails.
All additional integrated pilot operations remain outside this opt-in.
"""
from __future__ import annotations

import json
import logging
import os
import time

from scripts.eddy_vr01_mysql_worker import executar_worker_vr01

LOG = logging.getLogger("eddy.vr01.scheduler")

_LAST_BLUEPRINT_ATTEMPT = 0.0
_LAST_PILOT_BOOTSTRAP_ATTEMPT = 0.0


def flag_ativa(nome: str, default: str = "false") -> bool:
    return os.getenv(nome, default).strip().lower() == "true"


def intervalo_segundos(raw: str | None) -> int:
    try:
        value = int(raw or "900")
    except (ValueError, TypeError):
        raise ValueError(
            "EDDY_VR01_INTERVAL_SECONDS must be an integer"
        ) from None

    if value < 300:
        raise ValueError(
            "EDDY_VR01_INTERVAL_SECONDS must be >= 300"
        )

    return value


def executar_avanco_bp_piloto() -> None:
    """Advance only BUSCAR_CONTATO_BP when explicitly enabled.

    Never invoke the integrated executor from this autonomous path
    for any other lifecycle phase.
    """
    if not flag_ativa("EDDY_VR01_PILOT_BP_AUTO_ADVANCE"):
        return

    if not flag_ativa("EDDY_VR01_EXTERNAL_ENABLED"):
        LOG.info(
            "[EDDY-VR01-BP-AUTO] bloqueado: "
            "EDDY_VR01_EXTERNAL_ENABLED=false"
        )
        return

    if os.getenv("EDDY_DB_ENGINE", "").lower() != "mysql":
        LOG.warning(
            "[EDDY-VR01-BP-AUTO] bloqueado: MySQL obrigatorio"
        )
        return

    try:
        from ednna.eddy_vr01_integrated import (
            _load,
            planejar_vr01,
        )

        ledger = _load()

        if not ledger:
            LOG.info(
                "[EDDY-VR01-BP-AUTO] bloqueado: "
                "ledger indisponivel"
            )
            return

        fase = ledger["fase"]
        pendente = ledger["operacao_pendente"]

        if fase != "ASSUMIDO_EDDY":
            LOG.info(
                "[EDDY-VR01-BP-AUTO] sem avanco: fase=%s",
                fase,
            )
            return

        if pendente is not None:
            LOG.warning(
                "[EDDY-VR01-BP-AUTO] bloqueado: "
                "operacao pendente exige reconciliacao"
            )
            return

        # The integrated executor performs a fresh Redmine preflight,
        # validates lifecycle evidence and checks operation readiness.
        #
        # Only BUSCAR_CONTATO_BP is eligible here. Later lifecycle
        # phases must never be executed by this scheduler path.
        resultado = planejar_vr01(
            approvals=None,
            execute=True,
        )

        LOG.info(
            "[EDDY-VR01-BP-AUTO] %s",
            json.dumps(
                {
                    "chamado_id": 50318,
                    "estado": resultado.get("estado"),
                    "acao": resultado.get("acao"),
                    "fase": resultado.get("fase"),
                    "proxima_fase": resultado.get("proxima_fase"),
                },
                ensure_ascii=False,
                default=str,
            ),
        )

    except Exception as exc:
        LOG.warning(
            "[EDDY-VR01-BP-AUTO] falha segura: %s",
            type(exc).__name__,
        )


def executar_uma_vez() -> dict:
    # Autonomous pilot Blueprint import: MySQL only;
    # never writes Redmine or sends email.
    #
    # Explicit opt-in only: this discovery makes live Redmine
    # requests and is not yet covered by a shared distributed
    # collection lease.
    #
    # Rate limit independent of scheduler interval to avoid
    # hammering unstable Redmine.
    global _LAST_BLUEPRINT_ATTEMPT

    if flag_ativa("EDDY_VR01_BLUEPRINT_AUTO_SYNC"):
        now = time.monotonic()

        if (
            now - _LAST_BLUEPRINT_ATTEMPT >= 3600
            or _LAST_BLUEPRINT_ATTEMPT == 0
        ):
            _LAST_BLUEPRINT_ATTEMPT = now

            LOG.info(
                "[EDDY-VR01-BLUEPRINT-AUTO] "
                "tentativa_inicio chamado_id=50318"
            )

            try:
                from ednna.mysql_blueprint_participants import (
                    descobrir_e_sincronizar_participantes_mysql,
                )

                bp = descobrir_e_sincronizar_participantes_mysql(
                    {50318: "SUPERMERCADOS MAMBO"},
                    aplicar=True,
                    skip_imported=True,
                )

                LOG.info(
                    "[EDDY-VR01-BLUEPRINT-AUTO] %s",
                    json.dumps(
                        {
                            "chamado_id": 50318,
                            "participantes_processados": bp.get(
                                "participantes_processados", 0
                            ),
                            "participantes_reutilizados": bp.get(
                                "participantes_reutilizados", 0
                            ),
                            "fontes_descobertas": bp.get(
                                "fontes_descobertas", 0
                            ),
                            "descoberta": bp.get("descoberta", []),
                            "resultados": bp.get("resultados", []),
                            "emails_enviados": 0,
                            "redmine_escritas": 0,
                        },
                        ensure_ascii=False,
                        default=str,
                    ),
                )

            except Exception as exc:
                LOG.warning(
                    "[EDDY-VR01-BLUEPRINT-AUTO] falha segura: %s",
                    type(exc).__name__,
                )

    LOG.info("[EDDY-VR01-SCHEDULER] ciclo_inicio")

    result = executar_worker_vr01()

    sync = result.get("sincronizacao") or {}
    offline = result.get("propostas")
    fila = result.get("fila") or {}

    planejamento = (
        {
            "avaliados": offline.get("avaliados"),
            "intencoes": offline.get("propostas"),
            "propostas": offline.get("propostas"),
            "bloqueados": len(
                offline.get("bloqueados") or []
            ),
            "detalhes_bloqueios": offline.get(
                "bloqueados"
            ) or [],
            "situacao_fila": offline.get("situacao_fila"),
            "estado_persistencia": offline.get("estado"),
        }
        if isinstance(offline, dict)
        else {
            "avaliados": fila.get("avaliados"),
            "intencoes": fila.get("intencoes"),
            "bloqueados": fila.get("bloqueados"),
        }
    )

    LOG.info(
        "[EDDY-VR01-SCHEDULER] %s",
        json.dumps(
            {
                "estado": result.get("estado"),
                "abertos_consultados": sync.get(
                    "abertos_consultados"
                ),
                "vr_identificados": sync.get(
                    "vr_identificados"
                ),
                "importados": len(
                    sync.get("importados") or []
                ),
                "reutilizados_mysql": len(
                    sync.get("reutilizados_mysql") or []
                ),
                "falhas": len(
                    sync.get("falhas") or []
                ),
                "envios_realizados": result.get(
                    "envios_realizados", 0
                ),
                "redmine_escritas": result.get(
                    "redmine_escritas", 0
                ),
                "bloqueios_prontidao": (
                    result.get("prontidao_externa") or {}
                ).get("bloqueios", []),
                "estado_executor": (
                    result.get("execucao") or {}
                ).get("estado"),
                "acoes_avaliadas": (
                    result.get("execucao") or {}
                ).get("avaliados", 0),
                "planejamento": planejamento,
                "total_snapshots_vr_mysql": (
                    result.get("operacao") or {}
                ).get("total_snapshots_vr"),
                "chamados_vr_mysql": [
                    item.get("chamado_id")
                    for item in (
                        result.get("operacao") or {}
                    ).get("chamados", [])
                ],
                "modo_offline": isinstance(
                    offline, dict
                ),
                "cobertura_completa": sync.get(
                    "cobertura_completa"
                ),
                "motivo_degradacao": sync.get("motivo"),
                "erro_ciclo": result.get("erro"),
                "redmine_confirmado_agora": (
                    result.get("operacao") or {}
                ).get("carteira_confirmada_agora"),
                "resultados_executor": [
                    {
                        "chamado_id": item.get("chamado_id"),
                        "estado": item.get("estado"),
                    }
                    for item in (
                        result.get("execucao") or {}
                    ).get("resultados", [])
                ],
                "estado_reconciliacao_envios": (
                    result.get("evidencias_graph") or {}
                ).get("estado"),
                "estado_reconciliacao_respostas": (
                    result.get("respostas_graph") or {}
                ).get("estado"),
            },
            ensure_ascii=False,
            default=str,
        ),
    )

    # Bootstrap is a local MySQL ledger INSERT only.
    # Fresh Redmine preflight validates identity and ownership.
    # Limit attempts to once per hour per process.
    global _LAST_PILOT_BOOTSTRAP_ATTEMPT

    if (
        flag_ativa("EDDY_VR01_PILOT_OBSERVE")
        and flag_ativa(
            "EDDY_VR01_PILOT_BOOTSTRAP", "true"
        )
    ):
        now = time.monotonic()

        if (
            _LAST_PILOT_BOOTSTRAP_ATTEMPT == 0
            or now - _LAST_PILOT_BOOTSTRAP_ATTEMPT >= 3600
        ):
            _LAST_PILOT_BOOTSTRAP_ATTEMPT = now

            try:
                from ednna.eddy_vr01_bootstrap import (
                    inicializar_piloto_local,
                )

                bootstrap = inicializar_piloto_local()

                LOG.info(
                    "[EDDY-VR01-BOOTSTRAP] %s",
                    json.dumps(
                        bootstrap,
                        ensure_ascii=False,
                    ),
                )

            except Exception as exc:
                LOG.warning(
                    "[EDDY-VR01-BOOTSTRAP] falha segura: %s",
                    type(exc).__name__,
                )

    # Preserve the existing observational pilot.
    # Observation never advances phases.
    if flag_ativa("EDDY_VR01_PILOT_OBSERVE"):
        try:
            from ednna.eddy_vr01_integrated_scheduler import (
                ciclo_piloto,
            )

            pilot = ciclo_piloto(execute=False)

            from ednna.eddy_vr01_stage_readiness import (
                diagnosticar_etapas_vr01,
            )

            stages = diagnosticar_etapas_vr01()

            LOG.info(
                "[EDDY-VR01-STAGES] %s",
                json.dumps(
                    stages,
                    ensure_ascii=False,
                    default=str,
                ),
            )

            LOG.info(
                "[EDDY-VR01-PILOT] %s",
                json.dumps(
                    {
                        "chamado_id": pilot.get(
                            "chamado_id", 50318
                        ),
                        "fase": pilot.get("fase"),
                        "acao": pilot.get("acao"),
                        "estado": pilot.get("estado"),
                        "followup_situacao": (
                            pilot.get("followup") or {}
                        ).get("situacao"),
                        "execucao_externa": False,
                    },
                    ensure_ascii=False,
                ),
            )

        except Exception as exc:
            LOG.warning(
                "[EDDY-VR01-PILOT] "
                "observacao indisponivel: %s",
                type(exc).__name__,
            )

    # New opt-in autonomous pilot transition.
    # Only BUSCAR_CONTATO_BP is eligible.
    executar_avanco_bp_piloto()

    LOG.info(
        "[EDDY-VR01-SCHEDULER] ciclo_fim estado=%s",
        result.get("estado"),
    )

    return result


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )

    if os.getenv("EDDY_DB_ENGINE", "").lower() != "mysql":
        raise SystemExit(
            "[EDDY-VR01-SCHEDULER] "
            "MySQL obrigatório; execução recusada"
        )

    interval = intervalo_segundos(
        os.getenv("EDDY_VR01_INTERVAL_SECONDS")
    )

    LOG.info(
        "[EDDY-VR01-SCHEDULER] iniciado; "
        "intervalo_s=%s; "
        "execucao_externa_condicionada_a_prontidao=true; "
        "bp_auto_advance=%s",
        interval,
        flag_ativa(
            "EDDY_VR01_PILOT_BP_AUTO_ADVANCE"
        ),
    )

    while True:
        try:
            executar_uma_vez()

        except Exception as exc:
            LOG.exception(
                "[EDDY-VR01-SCHEDULER] falha segura: %s",
                type(exc).__name__,
            )

        LOG.info(
            "[EDDY-VR01-SCHEDULER] "
            "heartbeat ativo=true proximo_ciclo_em_s=%s",
            interval,
        )

        time.sleep(interval)


if __name__ == "__main__":
    main()
