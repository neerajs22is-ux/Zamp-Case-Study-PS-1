"""Read-only advisory snapshot for installed AP requirements; no app imports.

Run from repository root: python research/audit_production_dependencies.py
Only public package names/versions are sent to the official PyPI JSON API.
This checks installed versions, not a future resolver result or exploitability.
"""
import importlib.metadata
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


root = Path(__file__).resolve().parents[1]
names = [
    re.match(r"[A-Za-z0-9_-]+", line).group()
    for line in (root / "requirements.txt").read_text().splitlines()
    if line.strip() and not line.startswith("#")
]
# Starlette owns FastAPI request parsing and is a material transitive dependency.
names.append("starlette")
packages = []
for name in names:
    try:
        version = importlib.metadata.version(name)
        source = f"https://pypi.org/pypi/{name}/{version}/json"
        with urllib.request.urlopen(source, timeout=20) as response:
            metadata = json.load(response)
        packages.append({"name": name, "installed": version, "source": source,
                         "vulnerabilities": metadata.get("vulnerabilities", [])})
    except Exception as exc:
        packages.append({"name": name, "error": str(exc)})
report = {"checked_at": datetime.now(timezone.utc).isoformat(), "packages": packages}
output = root / "research" / "production_hardening_pypi_final.json"
output.write_text(json.dumps(report, indent=2), encoding="utf-8")
for package in packages:
    print(package["name"], package.get("installed", "UNAVAILABLE"),
          len(package.get("vulnerabilities", [])), "advisory entries",
          package.get("error", ""))
print(output)
