"""Audit caller migration before removing the legacy `/api` compatibility layer."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = ROOT / "frontend" / "src"
BACKEND_SCRIPTS = ROOT / "backend" / "scripts"
LEGACY_CALLER_ALLOWLIST = {
    "smoke_auth.py": "Bearer auth compatibility smoke",
    "smoke_performance.py": "legacy daily metric write compatibility smoke",
}
LEGACY_PATH_PATTERN = re.compile(r"/api/(?!v1(?:/|$))")
V1_PATH_PATTERN = re.compile(r"/api/v1(?:/|$)")


def find_legacy_callers(directory: Path) -> list[Path]:
    callers: list[Path] = []
    for path in directory.rglob("*"):
        if not path.is_file() or path.suffix not in {".js", ".jsx", ".ts", ".tsx", ".py"}:
            continue
        if path.name in {"check_app.py", "check_api_callers.py"}:
            continue
        if LEGACY_PATH_PATTERN.search(path.read_text(encoding="utf-8")):
            callers.append(path)
    return callers


def find_uncentralized_v1_callers(directory: Path) -> list[Path]:
    callers: list[Path] = []
    for path in directory.rglob("*"):
        if not path.is_file() or path.suffix not in {".js", ".jsx", ".ts", ".tsx"}:
            continue
        if ".test." in path.name or ".spec." in path.name:
            continue
        if path.name.endswith("Api.js") or path.name in {"httpClient.js"}:
            continue
        if V1_PATH_PATTERN.search(path.read_text(encoding="utf-8")):
            callers.append(path)
    return callers


frontend_callers = find_legacy_callers(FRONTEND_SRC)
assert not frontend_callers, (
    "Frontend còn caller legacy /api: "
    + ", ".join(str(path.relative_to(ROOT)) for path in frontend_callers)
)

uncentralized_v1_callers = find_uncentralized_v1_callers(FRONTEND_SRC)
assert not uncentralized_v1_callers, (
    "Frontend có URL /api/v1 ngoài feature *Api.js hoặc httpClient: "
    + ", ".join(str(path.relative_to(ROOT)) for path in uncentralized_v1_callers)
)

script_callers = find_legacy_callers(BACKEND_SCRIPTS)
unexpected = [path for path in script_callers if path.name not in LEGACY_CALLER_ALLOWLIST]
assert not unexpected, (
    "Script chưa được ghi nhận trong compatibility allowlist: "
    + ", ".join(str(path.relative_to(ROOT)) for path in unexpected)
)

print("Frontend caller audit: không còn caller /api legacy.")
print("Frontend v1 URL centralization audit: đạt.")
for path in script_callers:
    print(f"Compatibility caller: {path.name} — {LEGACY_CALLER_ALLOWLIST[path.name]}")
