"""Avaliar uma decisão VR Benefícios usando snapshot MySQL do EDDY.

Somente leitura; não altera chamados, não envia e-mails.
"""
import argparse
import json
from ednna.mysql_snapshot_repository import carregar_snapshot
from ednna.eddy_vr_rule import avaliar_vr


def main():
    parser = argparse.ArgumentParser(description="EDDY | decisão VR Benefícios")
    parser.add_argument("chamado_id", type=int)
    args = parser.parse_args()
    snapshot = carregar_snapshot(args.chamado_id)
    if not snapshot:
        parser.error("Chamado não está no MySQL; sincronize primeiro")
    print(json.dumps(avaliar_vr(snapshot["chamado"], snapshot["journals"]), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
