"""Line coverage with the stdlib tracer. No coverage package, no installs.

Executable lines come from compiled code objects. Executed lines come from
sys.settrace while the full unittest suite runs. Percentages use integer
math and print as "covered/total" so anyone can recompute them.

Run: python scripts/coverage_check.py [minimum_percent_for_src_kerdon]
Exit code is 1 when the pure core falls below the minimum (default 85).
"""

import dis
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tests"))


def executable_lines(path: Path) -> set[int]:
    code = compile(path.read_text(encoding="utf-8"), str(path), "exec")
    lines: set[int] = set()
    stack = [code]
    while stack:
        current = stack.pop()
        for _offset, lineno in dis.findlinestarts(current):
            if lineno:
                lines.add(lineno)
        stack.extend(c for c in current.co_consts if hasattr(c, "co_consts"))
    return lines


def measure() -> dict:
    targets = {str(p.resolve()): executable_lines(p) for p in sorted(SRC.rglob("*.py"))}
    executed: dict[str, set[int]] = {name: set() for name in targets}

    resolved_cache: dict[str, str | None] = {}

    def tracer(frame, event, _arg):
        raw = frame.f_code.co_filename
        name = resolved_cache.get(raw)
        if name is None and raw not in resolved_cache:
            resolved = str(Path(raw).resolve())
            name = resolved if resolved in executed else None
            resolved_cache[raw] = name
        if name is None:
            return None  # prune stdlib and test frames; only src lines count
        if event == "line":
            executed[name].add(frame.f_lineno)
        return tracer

    import threading

    sys.settrace(tracer)
    threading.settrace(tracer)
    try:
        # Discover after tracing starts so import-time lines count as covered.
        suite = unittest.TestLoader().discover(str(ROOT / "tests"), pattern="test_*.py")
        result = unittest.TextTestRunner(verbosity=0).run(suite)
    finally:
        sys.settrace(None)
        threading.settrace(None)
    packages: dict[str, tuple[int, int]] = {}
    for name, lines in targets.items():
        package = Path(name).relative_to(SRC).parts[0]
        covered = len(lines & executed[name])
        done, total = packages.get(package, (0, 0))
        packages[package] = (done + covered, total + len(lines))
    report = {
        pkg: {"covered": c, "total": t, "percent": (100 * c // t if t else 100)}
        for pkg, (c, t) in sorted(packages.items())
    }
    report["tests_run"] = result.testsRun
    report["tests_ok"] = result.wasSuccessful()
    return report


if __name__ == "__main__":
    minimum = int(sys.argv[1]) if len(sys.argv) > 1 else 85
    outcome = measure()
    print(json.dumps(outcome, indent=2))
    core = outcome.get("kerdon", {"percent": 0})
    raise SystemExit(0 if outcome["tests_ok"] and core["percent"] >= minimum else 1)
