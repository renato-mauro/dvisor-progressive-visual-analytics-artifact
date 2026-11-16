"""Rebuild the offline analyses for both experimental phases."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
PHASES = (
    ROOT / "phases" / "01-fixed-order",
    ROOT / "phases" / "02-order-sensitivity",
)


def main() -> None:
    for phase in PHASES:
        print(f"\n== Rebuilding {phase.name} ==")
        environment = os.environ.copy()
        mpl_dir = phase / "output" / ".matplotlib"
        mpl_dir.mkdir(parents=True, exist_ok=True)
        environment["MPLCONFIGDIR"] = str(mpl_dir)
        subprocess.run(
            [sys.executable, str(phase / "analysis" / "build_all.py")],
            cwd=phase,
            env=environment,
            check=True,
        )


if __name__ == "__main__":
    main()
