"""Run the VR01 pilot planner. Default: no Redmine/Graph writes.

Usage:
  python -m scripts.eddy_vr01_integrated --dry-run
This entrypoint never enables external operations. Explicit execution is
reserved for the audited operator workflow after full homologation.
"""
from __future__ import annotations

import argparse
import json

from ednna.eddy_vr01_integrated import planejar_vr01


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", default=True)
    args = parser.parse_args()
    print(json.dumps(planejar_vr01(execute=False), ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
