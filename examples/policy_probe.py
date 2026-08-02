"""Policy probe: dump YAML rules and cross-check against main._is_dangerous().

Usage:
    python examples/policy_probe.py
Exit code 0 = consistent, 1 = at least one DENY/ESCALATE rule uncovered
or one ALLOW rule wrongly flagged as dangerous.
"""

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Single source of truth: import from src.main, don't duplicate constants.
from src.main import _is_dangerous

BLOCKING_ACTIONS = ("DENY", "ESCALATE")

POLICIES = REPO_ROOT / "config" / "policies.yaml"


def main() -> int:
    with open(POLICIES, encoding="utf-8") as fh:
        rules = yaml.safe_load(fh)["rules"]

    print(f"policy file: {POLICIES}")
    print(f"{'name':<24}{'action':<10}{'priority':<9}path_pattern")
    for r in rules:
        print(f"{r.get('name','?'):<24}{r.get('action','?'):<10}"
              f"{r.get('priority','?'):<9}{r.get('path_pattern','?')}")

    warnings = []
    for r in rules:
        name = r.get("name", "?")
        action = r.get("action", "")
        path = r.get("path_pattern", "")
        method = r.get("method")
        if method is None:
            warnings.append(f"{name}: missing 'method' field")
            continue
        if action in BLOCKING_ACTIONS and not _is_dangerous(path, method):
            warnings.append(f"{name}: DENY/ESCALATE rule NOT covered by _is_dangerous()")
        if action == "ALLOW" and _is_dangerous(path, method):
            warnings.append(f"{name}: ALLOW rule wrongly flagged as dangerous")

    if warnings:
        print(f"WARNING: {len(warnings)} inconsistency(ies):")
        for w in warnings:
            print(f"  - {w}")
        return 1
    print("OK: all blocking rules covered, no ALLOW rule mis-flagged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
