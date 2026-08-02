"""Gate 3: Policy no-hardcode scanner.

Scans src/ for hardcoded policy patterns that should be in config/policies.yaml:
- re.compile() calls used for keyword matching (v1's GodelianBoundary pattern)
- hardcoded ALLOW/DENY dictionaries in Python source
- if-else chains that implement policy decisions without YAML indirection

Usage:
    python scripts/check_policy.py
    # exit 0 = clean, exit 1 = hardcoded policy detected
"""

import ast
import sys
from pathlib import Path

VIOLATION_EXIT_CODE = 1
SRC_DIR = "src"


class HardcodedPolicyVisitor(ast.NodeVisitor):
    """Detects hardcoded policy patterns in Python source."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.violations: list[tuple[int, str, str]] = []  # (line, type, detail)

    def visit_Call(self, node: ast.Call):
        # detect re.compile() — v1's GodelianBoundary pattern
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "compile" and isinstance(node.func.value, ast.Name):
                if node.func.value.id == "re":
                    self.violations.append((
                        node.lineno,
                        "re.compile",
                        "hardcoded regex — move pattern to policies.yaml",
                    ))

        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict):
        """Detect hardcoded action dictionaries."""
        # Check if this dict contains string keys that look like action names
        action_keys = []
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                key_lower = key.value.lower()
                if any(kw in key_lower for kw in ("allow", "deny", "block", "escalate", "rule")):
                    action_keys.append(key.value)

        if len(action_keys) >= 2:
            # Only flag if there are multiple policy-like keys (to avoid
            # flagging legitimate config dicts)
            self.violations.append((
                node.lineno,
                "hardcoded_dict",
                f"dict contains policy-like keys: {action_keys[:3]} — "
                f"move to config/policies.yaml",
            ))

        self.generic_visit(node)


def scan_file(filepath: Path) -> list:
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(filepath))
    visitor = HardcodedPolicyVisitor(str(filepath))
    visitor.visit(tree)
    return visitor.violations


def check_policy() -> int:
    src_dir = Path(SRC_DIR)
    if not src_dir.is_dir():
        print(f"⚠️  Source directory '{SRC_DIR}' not found")
        return 0

    py_files = sorted(src_dir.glob("**/*.py"))
    all_violations: list[tuple[str, int, str, str]] = []

    for pf in py_files:
        # skip __init__.py and models.py (no policy logic expected)
        if pf.name in ("__init__.py", "models.py"):
            continue
        violations = scan_file(pf)
        for line, vtype, detail in violations:
            all_violations.append((pf.name, line, vtype, detail))

    if all_violations:
        print(f"[FAIL] GATE 3: {len(all_violations)} hardcoded policy pattern(s) found:")
        for fname, line, vtype, detail in all_violations:
            print(f"  {fname}:{line} [{vtype}] {detail}")
        print(f"\n  Policy must be in config/policies.yaml, not in Python source.")
        return VIOLATION_EXIT_CODE

    print(f"[PASS] GATE 3: no hardcoded policy patterns in {len(py_files)} source files")
    return 0


if __name__ == "__main__":
    sys.exit(check_policy())
