"""Deterministic DevSecOps Security Stage: SAST, Secret Scan, IaC Audit, and OWASP Headers.

Runs with Python stdlib only so it executes identically offline and in GitHub Actions CI.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
FRONTEND_SRC = ROOT / "frontend" / "src"

BANNED_PYTHON_CALLS = {
    "eval",
    "exec",
    "compile",
    "os.system",
    " os.popen",
    "pickle.loads",
    "pickle.load",
    "marshal.loads",
    "marshal.load",
    "tempfile.mktemp",
    "hashlib.md5",
    "hashlib.sha1",
}

SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ASIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{40,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
]

FRONTEND_DANGEROUS_PATTERNS = [
    re.compile(r"dangerouslySetInnerHTML"),
    re.compile(r"\beval\s*\("),
    re.compile(r"\bnew\s+Function\s*\("),
    re.compile(r"document\.write\s*\("),
]


def _dotted_call_name(node: ast.AST) -> str:
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def check_python_sast() -> tuple[bool, str]:
    offenders: list[str] = []
    files = sorted(SRC.rglob("*.py"))
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel = path.relative_to(ROOT)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _dotted_call_name(node.func)
                if name in BANNED_PYTHON_CALLS:
                    offenders.append(f"{rel}:{node.lineno}:{name}")
                if name.startswith("subprocess."):
                    for kw in node.keywords:
                        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            offenders.append(f"{rel}:{node.lineno}:subprocess(shell=True)")
    return (not offenders), f"{len(files)} Python files AST-scanned; issues={offenders or 'none'}"


def check_frontend_sast() -> tuple[bool, str]:
    if not FRONTEND_SRC.exists():
        return True, "no frontend/src directory"
    offenders: list[str] = []
    files = sorted(list(FRONTEND_SRC.rglob("*.ts")) + list(FRONTEND_SRC.rglob("*.tsx")))
    for path in files:
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT)
        for pat in FRONTEND_DANGEROUS_PATTERNS:
            m = pat.search(text)
            if m:
                offenders.append(f"{rel}:{m.group(0)}")
    return (not offenders), f"{len(files)} TS/TSX files scanned; issues={offenders or 'none'}"


def check_secrets() -> tuple[bool, str]:
    hits: list[str] = []
    count = 0
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(ROOT).parts
        if any(p in {".git", "__pycache__", "temp", "node_modules", "dist"} for p in rel_parts):
            continue
        if path.suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".json", ".md", ".yml", ".yaml", ".tf", ".html"}:
            continue
        count += 1
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pat in SECRET_PATTERNS:
            m = pat.search(text)
            if m:
                hits.append(f"{path.relative_to(ROOT)}:{m.group(0)[:10]}...")
    return (not hits), f"{count} source/config files scanned; secret hits={hits or 'none'}"


def check_iac_policy() -> tuple[bool, str]:
    tf_path = ROOT / "infra" / "main.tf"
    if not tf_path.exists():
        return False, "infra/main.tf missing"
    tf = tf_path.read_text(encoding="utf-8")
    issues: list[str] = []
    if re.search(r'(?:Action|Resource)\s*=\s*(?:\[\s*)?"\*"', tf):
        issues.append("wildcard IAM Action/Resource policy detected")
    if "timeout" not in tf or "memory_size" not in tf:
        issues.append("Lambda resource missing explicit timeout/memory_size limits")
    if "lambda:InvokeFunctionUrl" not in tf or "lambda:InvokeFunction" not in tf:
        issues.append("Lambda Function URL permissions incomplete")
    return (not issues), f"infra/main.tf verified; issues={issues or 'none'}"


def check_owasp_runtime_headers() -> tuple[bool, str]:
    sys.path.insert(0, str(SRC))
    from archon_demo.lambda_handler import handler

    resp = handler({"rawPath": "/", "requestContext": {"http": {"method": "GET"}}}, None)
    headers = {k.lower(): v for k, v in (resp.get("headers") or {}).items()}
    issues: list[str] = []
    if headers.get("x-content-type-options") != "nosniff":
        issues.append("missing X-Content-Type-Options: nosniff")
    if headers.get("referrer-policy") != "no-referrer":
        issues.append("missing Referrer-Policy: no-referrer")
    csp = headers.get("content-security-policy", "")
    for directive in ("default-src 'self'", "frame-ancestors 'none'", "object-src 'none'"):
        if directive not in csp:
            issues.append(f"CSP missing {directive}")

    oversized = handler(
        {
            "rawPath": "/api/simulate-deposit",
            "requestContext": {"http": {"method": "POST"}},
            "body": '{"pad":"' + ("A" * 17000) + '"}',
        },
        None,
    )
    if oversized.get("statusCode") != 413:
        issues.append(f"oversized payload returned {oversized.get('statusCode')} instead of 413")
    return (not issues), f"CSP, nosniff, referrer-policy, and 413 body cap verified; issues={issues or 'none'}"


def main() -> int:
    checks = [
        ("SAST Python AST (banned sinks & weak crypto)", check_python_sast),
        ("SAST Frontend TS/TSX (XSS & eval sinks)", check_frontend_sast),
        ("Secret & Credential Pattern Scan", check_secrets),
        ("IaC Terraform Security Policy Audit", check_iac_policy),
        ("OWASP HTTP Headers & DoS Body Cap", check_owasp_runtime_headers),
    ]
    failed: list[str] = []
    for label, fn in checks:
        ok, detail = fn()
        print(f"{'PASS' if ok else 'FAIL'}  {label}  ({detail})")
        if not ok:
            failed.append(label)
    print(f"SECURITY AUDIT: {'PASS' if not failed else 'FAIL'} checks={len(checks)} failed={failed or 'none'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
