"""pytest 全局 fixture。

v1.42.2-step3 (可解释主控 Step 3): semantic_hook._drift_windows 是进程级
全局 (per-agent 上下文漂移滑动窗口)。测试间若不清理会跨文件泄漏 — E2E
匿名请求 (无 agent_id) 累积窗口后污染后续测试的漂移检测。autouse 每个
测试后清空, 保证隔离 (生产行为不受影响, 生产按 agent 会话自然累积)。
"""

import pytest

import src.semantic_hook as _sh


@pytest.fixture(autouse=True)
def _clean_drift_windows():
    yield
    _sh._drift_windows.clear()
