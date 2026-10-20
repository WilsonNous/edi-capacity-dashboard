"""Explicit VR01 controlled pilot: Redmine read, MySQL snapshot and audit only."""
from __future__ import annotations
import argparse
import json

from ednna.eddy_vr_redmine_import import importar_chamado_vr
from ednna.eddy_vr_decision_audit import registrar_decisao

PILOT_IDS = (49227, 49289)


def executar_piloto(chamado_ids=PILOT_IDS, *, importar=False):
    """Never sends mail or updates Redmine. Import requires explicit opt-in."""
    results = []
    for chamado_id in chamado_ids:
        if chamado_id not in PILOT_IDS:
            raise ValueError("Chamado fora do piloto VR01")
        if importar:
            importar_chamado_vr(chamado_id)
        results.append(registrar_decisao(chamado_id))
    return results


def main():
    parser = argparse.ArgumentParser(description="EDDY VR01: piloto sem ações externas")
    parser.add_argument("--importar-redmine", action="store_true",
                        help="Ler Redmine e persistir snapshots antes da avaliação")
    parser.add_argument("--chamado", type=int, choices=PILOT_IDS, action="append")
    args = parser.parse_args()
    result = executar_piloto(args.chamado or PILOT_IDS, importar=args.importar_redmine)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
