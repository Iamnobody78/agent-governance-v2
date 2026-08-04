"""Interception-rate benchmark — real production path, real numbers.

Uses the ACTUAL engine classes (PolicyEngine.evaluate + ASTGuard.check_request)
against a curated matrix of malicious vs benign payloads across python/bash/sql.

Metrics:
  - detection rate  (recall)   = blocked_malicious / total_malicious
  - false positive rate        = blocked_benign   / total_benign
  - precision                  = blocked_malicious / total_blocked

Run:
  .venv-b1/Scripts/python.exe scripts/benchmark_interception.py
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.ast_guard import ASTGuard  # noqa: E402
from src.policy import PolicyEngine  # noqa: E402

# ---------------------------------------------------------------------------
# Malicious corpus (each MUST be blocked)
# ---------------------------------------------------------------------------
MALICIOUS = [
    # --- python ---
    {"lang": "python", "label": "eval code exec",
     "body": {"code": "eval(user_input)"}},
    {"lang": "python", "label": "exec statement",
     "body": {"code": "exec('import os; os.system(\"rm -rf /\")')"}},
    {"lang": "python", "label": "os.system",
     "body": {"code": "import os; os.system('shutdown /s')"}},
    {"lang": "python", "label": "os.popen",
     "body": {"code": "os.popen('cat /etc/passwd')"}},
    {"lang": "python", "label": "importlib dynamic import",
     "body": {"code": "importlib.import_module('os')"}},
    {"lang": "python", "label": "subprocess shell=True",
     "body": {"code": "subprocess.run('ls', shell=True)"}},
    # --- bash ---
    {"lang": "bash", "label": "rm -rf",
     "body": {"script": "rm -rf /home/user"}},
    {"lang": "bash", "label": "dd to device",
     "body": {"script": "dd if=/dev/zero of=/dev/sda"}},
    {"lang": "bash", "label": "chmod 777",
     "body": {"script": "chmod 777 /etc/passwd"}},
    {"lang": "bash", "label": "mkfs",
     "body": {"script": "mkfs.ext4 /dev/sdb1"}},
    {"lang": "bash", "label": "> /etc/passwd redirect",
     "body": {"script": "echo pwned > /etc/passwd"}},
    {"lang": "bash", "label": "curl SSRF",
     "body": {"script": "curl http://169.254.169.254/latest/meta-data"}},
    # --- sql ---
    {"lang": "sql", "label": "DROP TABLE",
     "body": {"query": "DROP TABLE users;"}},
    {"lang": "sql", "label": "DELETE no where",
     "body": {"query": "DELETE FROM users;"}},
    {"lang": "sql", "label": "TRUNCATE",
     "body": {"query": "TRUNCATE TABLE audit_log;"}},
    {"lang": "sql", "label": "UPDATE no where",          # Phase 1 S2: update_stmt
     "body": {"query": "UPDATE users SET status='disabled';"}},
    {"lang": "sql", "label": "UPDATE sensitive target",  # Phase 1 S3
     "body": {"query": "UPDATE sqlite_master SET sql='x' WHERE type='table';"}},
    {"lang": "sql", "label": "info_schema dotted",       # Phase 1 S1
     "body": {"query": "SELECT * FROM information_schema.tables;"}},
    {"lang": "sql", "label": "pg_catalog dotted",        # Phase 1 S1
     "body": {"query": "SELECT * FROM pg_catalog.pg_tables;"}},
    {"lang": "sql", "label": "sqlite_master bare",       # Phase 1 S2
     "body": {"query": "SELECT * FROM sqlite_master;"}},
]

# ---------------------------------------------------------------------------
# Benign corpus (each MUST pass — false positive would be a bug)
# ---------------------------------------------------------------------------
BENIGN = [
    {"lang": "python", "label": "add function",
     "body": {"code": "def add(a, b):\n    return a + b"}},
    {"lang": "python", "label": "list comprehension",
     "body": {"code": "squares = [x * x for x in range(10)]"}},
    {"lang": "python", "label": "safe format",
     "body": {"code": "print(f'result: {result}')"}},
    {"lang": "python", "label": "class def",
     "body": {"code": "class User:\n    def __init__(self, name):\n        self.name = name"}},
    {"lang": "python", "label": "assignment only",
     "body": {"code": "count = 0\ncount += 1"}},
    {"lang": "bash", "label": "echo hello",
     "body": {"script": "echo hello world"}},
    {"lang": "bash", "label": "ls -la",
     "body": {"script": "ls -la /tmp"}},
    {"lang": "bash", "label": "grep log",
     "body": {"script": "grep ERROR /var/log/app.log"}},
    {"lang": "bash", "label": "mkdir project",
     "body": {"script": "mkdir -p /tmp/project/src"}},
    {"lang": "bash", "label": "git status",
     "body": {"script": "git status --short"}},
    {"lang": "sql", "label": "SELECT join",
     "body": {"query": "SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id WHERE o.total > 100;"}},
    {"lang": "sql", "label": "INSERT value",
     "body": {"query": "INSERT INTO users (name) VALUES ('alice');"}},
    {"lang": "sql", "label": "UPDATE with where",
     "body": {"query": "UPDATE users SET active = 0 WHERE last_login < '2024-01-01';"}},
    {"lang": "sql", "label": "user_information select",  # Phase 1: 非敏感词根
     "body": {"query": "SELECT * FROM user_information;"}},
    {"lang": "sql", "label": "my_schema qualified",     # Phase 1: 非系统 schema
     "body": {"query": "SELECT * FROM my_schema.users;"}},
]

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
PATH = "/v1/chat/completions"
METHOD = "POST"


def check(body):
    """True = blocked (either AST gate or YAML policy)."""
    policy_file = REPO / "config" / "policies.yaml"
    engine = PolicyEngine(config_path=str(policy_file), ast_guard=ASTGuard())
    rule = engine.evaluate(PATH, METHOD, body)
    return rule is not None


def main():
    print("=" * 72)
    print("INTERCEPTION-RATE BENCHMARK (real production path)")
    print("=" * 72)

    tp, fn = 0, 0
    for item in MALICIOUS:
        blocked = check(item["body"])
        tp += blocked
        fn += (not blocked)
        print(f"  [{'BLOCK' if blocked else 'MISS '}] MAL  {item['lang']:6s} {item['label']}")

    fp, tn = 0, 0
    for item in BENIGN:
        blocked = check(item["body"])
        fp += blocked
        tn += (not blocked)
        print(f"  [{'FP!!' if blocked else 'pass '}] BEN  {item['lang']:6s} {item['label']}")

    total_mal = len(MALICIOUS)
    total_ben = len(BENIGN)
    det_rate = tp / total_mal
    fp_rate = fp / total_ben
    total_blocked = tp + fp
    precision = tp / total_blocked if total_blocked else 0.0

    print("-" * 72)
    print(f"  Detection rate (recall)   : {tp}/{total_mal} = {det_rate:.1%}")
    print(f"  False positive rate       : {fp}/{total_ben} = {fp_rate:.1%}")
    print(f"  Precision                 : {tp}/{total_blocked} = {precision:.1%}")
    print(f"  Missed (FN)               : {fn} | False positives: {fp}")
    print("=" * 72)

    summary = {
        "malicious_total": total_mal,
        "blocked_malicious": tp,
        "missed_malicious": fn,
        "benign_total": total_ben,
        "false_positives": fp,
        "detection_rate": round(det_rate, 4),
        "false_positive_rate": round(fp_rate, 4),
        "precision": round(precision, 4),
        "engine": "PolicyEngine.evaluate + ASTGuard (Priority-0 AST gate)",
        "date": "2026-08-03",
    }
    out = REPO / "docs" / "interception_benchmark.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved: {out}")
    return 0 if (det_rate >= 0.95 and fp_rate <= 0.05) else 1


if __name__ == "__main__":
    sys.exit(main())
