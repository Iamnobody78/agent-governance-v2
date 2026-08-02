"""Circuit breaker time-decay tests.

Verifies the fix for CRITIQUE_V2 defect: the counter had no time decay,
so an attacker could send 9 ESCALATE requests, wait arbitrarily long,
then send a 10th to trip the breaker and get ALLOW.

Fixed behavior:
1. Time decay: if >300s elapsed since last ESCALATE, counter resets to 1.
2. ALLOW resolution: a successful ALLOW resets the counter to 0.
"""

import time

from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

import src.main as main_module
from src.main import create_app


class TestCircuitBreakerDecay(AioHTTPTestCase):
    async def get_application(self):
        return create_app()

    @unittest_run_loop
    async def test_decay_prevents_breaker_trip_after_300s(self):
        """9 ESCALATEs, then wait 400s, then 10th ESCALATE → still ESCALATE.

        Before the fix: 10th tripped to ALLOW. After: counter resets,
        so 10th stays ESCALATE.
        """
        for _ in range(9):
            resp = await self.client.post(
                "/v1/intercept",
                json={"path": "/api/config/model", "method": "POST"},
            )
            assert resp.status == 202

        # Simulate 400 seconds passing (manipulate module global)
        main_module.last_escalate_time = time.time() - 400.0

        # 10th request — must NOT trip (counter reset by decay)
        resp = await self.client.post(
            "/v1/intercept",
            json={"path": "/api/config/model", "method": "POST"},
        )
        assert resp.status == 202, f"Expected ESCALATE after decay, got {resp.status}"
        data = await resp.json()
        assert data["verdict"] == "ESCALATE"

    @unittest_run_loop
    async def test_continuous_burst_still_trips(self):
        """10 ESCALATEs in quick succession (<300s apart) still trip breaker.

        Time decay must not weaken the original protection.
        """
        for i in range(9):
            resp = await self.client.post(
                "/v1/intercept",
                json={"path": "/api/config/model", "method": "POST"},
            )
            assert resp.status == 202, f"iteration {i}: expected 202, got {resp.status}"

        # 10th within the window → trips
        resp = await self.client.post(
            "/v1/intercept",
            json={"path": "/api/config/model", "method": "POST"},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["verdict"] == "ALLOW"

    @unittest_run_loop
    async def test_allow_resets_counter(self):
        """An ALLOW request in between resets the breaker counter.

        Before the fix: dead code `if rule.action == "ESCALATE"` in the
        ALLOW branch never reset the counter.
        """
        # 5 ESCALATEs
        for _ in range(5):
            resp = await self.client.post(
                "/v1/intercept",
                json={"path": "/api/config/model", "method": "POST"},
            )
            assert resp.status == 202

        # 1 ALLOW (chat) — should reset counter to 0
        resp = await self.client.post(
            "/v1/intercept",
            json={"path": "/api/chat", "method": "POST"},
        )
        assert resp.status == 200
        assert main_module.escalate_count_since_resolve == 0

        # 5 more ESCALATEs — counter restarts from 0, so still 202
        for _ in range(5):
            resp = await self.client.post(
                "/v1/intercept",
                json={"path": "/api/config/model", "method": "POST"},
            )
            assert resp.status == 202

    @unittest_run_loop
    async def test_counter_starts_fresh_after_decay(self):
        """After decay reset, 9 more ESCALATEs should NOT trip.

        Verifies the counter actually reset to 1 (not accumulated).
        """
        for _ in range(9):
            resp = await self.client.post(
                "/v1/intercept",
                json={"path": "/api/config/model", "method": "POST"},
            )
            assert resp.status == 202

        # 400s pass → decay resets to 1
        main_module.last_escalate_time = time.time() - 400.0
        resp = await self.client.post(
            "/v1/intercept",
            json={"path": "/api/config/model", "method": "POST"},
        )
        assert resp.status == 202  # now counter is 1

        # 8 more (total 9 since decay) → still ESCALATE (9 < 10)
        for i in range(8):
            resp = await self.client.post(
                "/v1/intercept",
                json={"path": "/api/config/model", "method": "POST"},
            )
            assert resp.status == 202, f"iteration {i} after decay: expected 202"

        # 10th after decay → trips
        resp = await self.client.post(
            "/v1/intercept",
            json={"path": "/api/config/model", "method": "POST"},
        )
        assert resp.status == 200
