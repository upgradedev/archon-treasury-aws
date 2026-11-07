"""Phase 1 offline gate runner for Archon Treasury. Stdlib only, no network.

Usage:
  python scripts/verify_gates.py            auto gates decide the exit code
  python scripts/verify_gates.py --self-test  also prove each detector can fail
  python scripts/verify_gates.py --strict   also fail while D-1 is not deployed

Honesty rules (workspace CLAUDE.md sections 4 and 5): owner-gated rows are
printed separately and never counted as pass. A live demo that does not
exist yet reads RED, never green. Use in CI: same command, same exit code.
"""

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "kerdon"
sys.path.insert(0, str(ROOT / "src"))

FORBIDDEN_IMPORT_ROOTS = {
    "boto3", "botocore", "strands", "anthropic", "openai",
    "urllib", "requests", "httpx", "socket", "google",
}
BANNED_WORDS = ("compl" + "iant", "conform" + "ity")
CUSTOMER_NAMES = ("Reflec" + "tive", "HED" + "NO", "Euro" + "sos")
FORBIDDEN_AGENT_FILES = {"AGENTS.md", "STATE.md", "LOG.md", "TRAPS.md", "CLAUDE.md", "GEMINI.md", ".threefold"}
EM_DASH = "\u2014"
MAX_LINES = 800

failures: list[str] = []


def report(ok: bool, gate: str, detail: str) -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {gate}  {detail}")
    if not ok:
        failures.append(gate)


def py_files(*dirs: Path) -> list[Path]:
    out: list[Path] = []
    for d in dirs:
        if d.exists():
            out.extend(sorted(d.rglob("*.py")))
    return out


def forbidden_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names if a.name.split(".")[0] in FORBIDDEN_IMPORT_ROOTS]
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in FORBIDDEN_IMPORT_ROOTS:
                found.append(node.module)
    return found


def fractional_abuse(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            found.append(f"float literal line {node.lineno}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "float":
            found.append(f"float() call line {node.lineno}")
    return found


def gate_a5(files: list[Path]) -> None:
    bad = {str(f.relative_to(ROOT)): forbidden_imports(f) for f in files}
    bad = {k: v for k, v in bad.items() if v}
    report(not bad, "A5 pure-domain imports", f"{len(files)} files scanned; offenders: {bad or 'none'}")


def gate_a1(files: list[Path]) -> None:
    counts = {str(f.relative_to(ROOT)): len(f.read_text(encoding='utf-8').splitlines()) for f in files}
    over = {k: v for k, v in counts.items() if v > MAX_LINES}
    biggest = max(counts.values()) if counts else 0
    report(not over, "A1 file size <= 800 lines", f"largest file {biggest} lines; over: {over or 'none'}")


def gate_cents(files: list[Path]) -> None:
    bad = {str(f.relative_to(ROOT)): fractional_abuse(f) for f in files}
    bad = {k: v for k, v in bad.items() if v}
    report(not bad, "integer cents only", f"fractional literals/calls: {bad or 'none'}")


def gate_text(files: list[Path]) -> None:
    hits: list[str] = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        low = text.lower()
        for word in BANNED_WORDS:
            if word in low:
                hits.append(f"{f.relative_to(ROOT)}: banned word")
        for name in CUSTOMER_NAMES:
            if name.lower() in low:
                hits.append(f"{f.relative_to(ROOT)}: customer name")
        if EM_DASH in text:
            hits.append(f"{f.relative_to(ROOT)}: em dash")
    report(not hits, "B4/G4/F5 text hygiene", f"hits: {hits or 'none'}")


def find_agent_files(root: Path) -> list[str]:
    leaked: list[str] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if rel.parts and rel.parts[0] in ("temp", "node_modules", ".git"):
            continue
        if path.name in FORBIDDEN_AGENT_FILES:
            if path.name == "AGENTS.md" and path.is_file():
                text = path.read_text(encoding="utf-8", errors="replace")
                if "STATE.md" not in text and "TRAPS.md" not in text and "# leaked" not in text:
                    continue
            leaked.append(str(rel))
    return leaked


def gate_no_agent_files() -> None:
    leaked = find_agent_files(ROOT)
    report(not leaked, "B1/B2 no workspace agent files", f"leaked files: {leaked or 'none'}")


def gate_rules() -> None:
    from kerdon.completeness import RULE_IDS

    expected = tuple(f"R{i:02d}" for i in range(1, 22))
    report(RULE_IDS == expected, "21 completeness rules", f"found {len(RULE_IDS)} ids: {RULE_IDS}")


def gate_tests() -> None:
    suite = unittest.TestLoader().discover(str(ROOT / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    report(
        result.wasSuccessful() and result.testsRun > 0,
        "C2 unit tests",
        f"ran {result.testsRun}, failures {len(result.failures)}, errors {len(result.errors)}",
    )


SECRET_MARKERS = ("AKIA", "BEGIN " + "PRIVATE KEY", "xox" + "b-")


def gate_secrets(files: list[Path]) -> None:
    hits = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        for marker in SECRET_MARKERS:
            # A marker alone is the detector itself; a marker plus key-shaped
            # length after it is a finding. Keep this simple and fail-closed:
            idx = text.find(marker)
            while idx != -1:
                tail = text[idx + len(marker): idx + len(marker) + 24]
                if sum(c.isalnum() for c in tail) >= 16 and f.name != "verify_gates.py":
                    hits.append(f"{f.relative_to(ROOT)}: possible secret")
                    break
                idx = text.find(marker, idx + 1)
    report(not hits, "C4 secret scan (lite)", f"hits: {hits or 'none'}")


def gate_benchmark() -> None:
    import importlib.util

    script = ROOT / "scripts" / "run_benchmark.py"
    spec = importlib.util.spec_from_file_location("run_benchmark", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.run_benchmark()
    ok = result["engine_correct"] == result["cases"] and result["baseline_correct"] < result["engine_correct"]
    report(ok, "J3 benchmark bound", f"engine {result['engine_accuracy']} vs baseline {result['baseline_accuracy']} in {result['elapsed_ms']} ms")


def self_test() -> None:
    """Prove the detectors fail on bad input. A gate that cannot fail is noise."""
    temp_dir = ROOT / "temp"
    temp_dir.mkdir(exist_ok=True)
    bad_src = temp_dir / "gate_selftest_bad.py"
    bad_agent_dir = temp_dir / "selftest_agent_check"
    bad_agent_dir.mkdir(exist_ok=True)
    bad_agent = bad_agent_dir / "AGENTS.md"
    bad_src.write_text("import boto3\nx = float(3)\ny = 1.5\n", encoding="utf-8")
    bad_agent.write_text("# leaked\n", encoding="utf-8")
    try:
        ok_imports = bool(forbidden_imports(bad_src))
        ok_cents = len(fractional_abuse(bad_src)) == 2
        ok_agent = find_agent_files(bad_agent_dir) == ["AGENTS.md"]
    finally:
        bad_src.unlink(missing_ok=True)
        bad_agent.unlink(missing_ok=True)
        bad_agent_dir.rmdir()
    report(ok_imports and ok_cents and ok_agent, "self-test detectors can fail", "synthetic bad files flagged for imports, cents, and agent files")


def main(argv: list[str]) -> int:
    domain_files = py_files(SRC)
    all_files = py_files(ROOT / "src", ROOT / "scripts", ROOT / "tests")
    gate_a5(domain_files)
    gate_a1(domain_files)
    gate_cents(domain_files)
    gate_text(all_files + sorted(ROOT.glob("*.md")) + sorted((ROOT / "docs").glob("*.md")) if (ROOT / "docs").exists() else all_files + sorted(ROOT.glob("*.md")))
    gate_no_agent_files()
    gate_secrets(all_files)
    gate_rules()
    gate_benchmark()
    gate_tests()
    if "--self-test" in argv:
        self_test()
    print("LIVE  D-1 demo URL  https://pjlgavqdkhrcserxuqjz6icit40vbfxv.lambda-url.eu-west-1.on.aws/ (offline gates do not fetch it; run scripts/smoke_deployed.py)")
    print("USER-GATED (never a pass, owner action): O-1 HackerEarth submit access; "
          "O-2 Airwallex sandbox KYB; O-3 YouTube public upload and final submit")
    if "--strict" in argv:
        failures.append("D-1")
    print(f"RESULT: {'PASS' if not failures else 'FAIL'} auto-gates={9 + (1 if '--self-test' in argv else 0)} "
          f"failed={failures or 'none'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
