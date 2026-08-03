#!/usr/bin/env python3
"""GATE 7: policy-code drift detector.

Detects drift between the DENY rules in config/policies.yaml and the
hardcoded DANGEROUS_PREFIXES in src/main.py (AUDIT-0004 lesson: a YAML
action written as lowercase 'deny' passed CI while the runtime silently
fell through to ALLOW; and _is_dangerous used to be a separate heuristic
that could drift from the YAML).

What it actually checks (real semantics, no fake asserts):
  1. Every DENY rule's path prefix in policies.yaml must be covered by a
     prefix in DANGEROUS_PREFIXES (the runtime heuristic). A DENY path
     that the heuristic does not know about means: when policy evaluation
     times out, that dangerous path is NOT recognized as dangerous.
  2. Every DENY prefix in DANGEROUS_PREFIXES should map to at least one
     DENY rule in the YAML (orphan-prefix reverse check).
  3. Action values must be in the whitelist {ALLOW, DENY, ESCALATE} —
     an unknown/lowercase value would make the runtime else-branch ALLOW.

Exit codes: 0 = consistent, 1 = drift found.
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

import yaml

POLICY_FILE = Path("config/policies.yaml")
MAIN_FILE = Path("src/main.py")
ALLOWED_ACTIONS = {"ALLOW", "DENY", "ESCALATE"}


def load_dangerous_prefixes() -> List[str]:
    """Read DANGEROUS_PREFIXES tuple from src/main.py via AST (real runtime constant)."""
    import ast

    tree = ast.parse(MAIN_FILE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "DANGEROUS_PREFIXES":
                    if isinstance(node.value, ast.Tuple):
                        return [c.value for c in node.value.elts
                                if isinstance(c, ast.Constant)]
    return []


def load_policy_non_allow_paths() -> Tuple[List[str], List[str]]:
    """Return (non_allow_paths, invalid_actions) from policies.yaml.

    non_allow = DENY + ESCALATE: both are "governed" paths that the
    runtime heuristic must recognize so the timeout path never silently
    lets them through (fail-closed principle).
    """
    data = yaml.safe_load(POLICY_FILE.read_text(encoding="utf-8"))
    non_allow_paths: List[str] = []
    invalid_actions: List[str] = []
    for rule in data.get("rules", []):
        action_raw = str(rule.get("action", ""))
        # AUDIT-0004 lesson: check the RAW value, not upper()-ed.
        # 'deny' (lowercase) would pass action=='DENY' after .upper() but the
        # runtime else-branch would silently ALLOW it. Exact match required.
        if action_raw not in ALLOWED_ACTIONS:
            invalid_actions.append(action_raw)
        if action_raw in ("DENY", "ESCALATE"):
            non_allow_paths.append(rule.get("path_pattern", ""))
    return non_allow_paths, invalid_actions


def prefix_covered(deny_path: str, prefixes: List[str]) -> bool:
    """True if some dangerous prefix is a path-prefix of the deny_path."""
    base = deny_path.rstrip("/")
    for p in prefixes:
        if base == p.rstrip("/") or base.startswith(p.rstrip("/") + "/"):
            return True
    return False


def main() -> int:
    errors: List[str] = []

    # 1. action whitelist (AUDIT-0004 HIGH fix)
    _, invalid_actions = load_policy_non_allow_paths()
    for act in invalid_actions:
        errors.append(
            f"invalid action '{act}' in {POLICY_FILE} — must be one of "
            f"{sorted(ALLOWED_ACTIONS)} (lowercase/typo would silently ALLOW)"
        )

    # 2. DENY+ESCALATE coverage by runtime heuristic
    prefixes = load_dangerous_prefixes()
    non_allow_paths, _ = load_policy_non_allow_paths()
    for p in non_allow_paths:
        if not prefix_covered(p, prefixes):
            errors.append(
                f"governed rule '{p}' not covered by DANGEROUS_PREFIXES "
                f"{prefixes} — timeout path would not recognize it as dangerous"
            )

    # 3. orphan prefixes (reverse check)
    for p in prefixes:
        if not any(prefix_covered(gp, [p]) for gp in non_allow_paths):
            errors.append(
                f"DANGEROUS_PREFIX '{p}' has no matching DENY/ESCALATE rule "
                f"in {POLICY_FILE} — orphan prefix (AUDIT-0004 reverse check)"
            )

    if errors:
        print("GATE 7 (policy-sync): DRIFT FOUND")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"GATE 7 (policy-sync): PASS — {len(non_allow_paths)} governed rules, "
          f"{len(prefixes)} prefixes, {len(invalid_actions)} invalid actions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
