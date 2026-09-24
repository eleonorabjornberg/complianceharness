"""Regenerate the golden reports in tests/golden/.

Run this only when a change to the report is intended, then read the
diff it produces before committing it: that diff is the change every
consumer of the JSON report will see.

    make golden
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from test_golden import GOLDEN, render  # noqa: E402
from dossier import packs  # noqa: E402

for name in packs.names():
    target = GOLDEN / f"{name}.json"
    target.write_text(render(name), encoding="utf-8")
    print(f"wrote {target.relative_to(ROOT)}")
