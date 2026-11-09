"""Ciclos de observabilidade dos motores EDDY, sem ações externas.

Executa avaliações locais e publica contagens sem consultar o Redmine.
A falta de evidência de recepção nunca é convertida em ausência confirmada.
"""
from __future__ import annotations

import logging
import os
import time
from collections import Counter

LOG = logging.getLogger("eddy.motores")
INTERVALO_MINIMO = 60


def executar_ciclo() -> dict:
    if os.getenv("EDDY_DB_ENGINE", "sqlite").strip().lower() == "mysql":
        from ednna.motores_mysql_repository import inventario, listar_homologacoes, listar_propostas, obter_autorizacao
        status = inventario()
        homologacoes = listar_homologacoes()
        aberturas = []
        for h in homologacoes:
            if str(h.get("regra_id") or "").startswith("ABERTURA-"):
                autorizacao = obter_autorizacao(h["regra_id"])
                aberturas.append({"regra_id": h["regra_id"], "estado": h["estado"],
                                  "modo": autorizacao["modo"], "executavel": False})
        falta = [h for h in homologacoes if str(h.get("regra_id") or "").upper().startswith(("FALTA-ARQUIVO-", "FALTA_ARQUIVO-", "AUSENCIA-ARQUIVO-"))]
        resultado = {"aberturas": len(aberturas),
                     "aberturas_estados": dict(Counter(x["estado"] for x in aberturas)),
                     "falta_arquivo_regras": len(falta),
                     "falta_arquivo_demandas_confirmadas": 0,
                     "envios_externos": 0,
                     "fonte": "MYSQL", "migracao": status,
                     "propostas_abertura": len(listar_propostas())}
        LOG.info("[EDDY] Observabilidade motores MySQL | %s", resultado)
        return resultado
    from ednna.motor_aberturas import avaliar_aberturas_homologadas
    from ednna.motor_falta_arquivo import listar_regras_aprendidas

    aberturas = avaliar_aberturas_homologadas()
    falta = listar_regras_aprendidas()
    estados = Counter(str(item.get("estado") or "INDETERMINADO") for item in aberturas)
    resultado = {
        "aberturas": len(aberturas),
        "aberturas_estados": dict(estados),
        "falta_arquivo_regras": len(falta),
        "falta_arquivo_demandas_confirmadas": 0,
        "envios_externos": 0,
    }
    LOG.info(
        "[EDDY] Motor aberturas | regras=%s | estados=%s | envios_externos=0",
        resultado["aberturas"], resultado["aberturas_estados"],
    )
    LOG.info(
        "[EDDY] Motor falta arquivo | regras=%s | demandas_confirmadas=0 | "
        "motivo=SEM_EVIDENCIA_RECEPCAO_INTEGRADA | envios_externos=0",
        resultado["falta_arquivo_regras"],
    )
    return resultado


def executar_continuamente(*, intervalo: int = 300, dormir=time.sleep) -> None:
    intervalo = max(INTERVALO_MINIMO, int(intervalo))
    LOG.info("[EDDY] Observabilidade motores iniciada | intervalo=%ss", intervalo)
    while True:
        try:
            executar_ciclo()
        except Exception:
            LOG.exception("[EDDY] Observabilidade motores | falha no ciclo; próxima tentativa agendada")
        dormir(intervalo)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    executar_continuamente(intervalo=int(os.getenv("EDDY_MOTORES_INTERVALO_SEGUNDOS", "300")))


if __name__ == "__main__":
    main()
