"""DEBT-0003: CI workflow aggregation gate tests.

The workflow's all-gates job must declare needs: over every gate job so
branch protection can require a single check name instead of six. YAML
is parsed from the repo's ci.yml (pyyaml is a core dependency).

TASK-REAL-012: GATE_JOBS 增加 critic-gate（GATE 8 批判者代码化）。
P0-2 (2026-08-03): 8 GATE 合并为 3 核心门控 quality/policy/critic，
消除脚本堆砌式膨胀；GATE 能力全部保留在合并 job 内。
"""

import pathlib

import yaml

WORKFLOW = pathlib.Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml"
GATE_JOBS = [
    "quality",
    "policy",
    "critic",
]


def _workflow():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


class TestAllGatesAggregation:
    def test_all_gates_job_exists(self):
        jobs = _workflow()["jobs"]
        assert "all-gates" in jobs

    def test_all_gates_depends_on_every_gate(self):
        jobs = _workflow()["jobs"]
        needs = jobs["all-gates"].get("needs", [])
        assert sorted(needs) == sorted(GATE_JOBS), f"needs={needs}"

    def test_gate_jobs_are_defined(self):
        jobs = _workflow()["jobs"]
        for name in GATE_JOBS:
            assert name in jobs, f"gate job {name} missing"
