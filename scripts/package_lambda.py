"""Build the Lambda deployment zip deterministically. Stdlib only.

Same source in, same zip bytes out (fixed timestamps, sorted entries), so
the printed SHA-256 can travel as the artifact provenance value until a
git commit exists to name instead.

Run: python scripts/package_lambda.py [output_path]
"""

import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
FIXED_DATE = (2026, 1, 1, 0, 0, 0)


def build(output: Path) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(SRC.rglob("*.py"))
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            info = zipfile.ZipInfo(str(path.relative_to(SRC)).replace("\\", "/"), date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return {
        "zip": str(output),
        "sha256": digest,
        "bytes": output.stat().st_size,
        "entries": len(files),
        "handler": "archon_demo.lambda_handler.handler",
        "runtime": "python3.12",
    }


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "temp" / "archon-lambda.zip"
    print(json.dumps(build(target), indent=2))
