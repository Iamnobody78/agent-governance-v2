"""Temporary fixture: deliberately vulnerable code to prove GATE 6 catches it.
NOT part of the gateway — deleted after verification."""

import asyncio


def breaker_bad(count):
    verdict = "ESCALATE"
    if count >= 10:  # CIRCUIT_BREAKER_LIMIT pattern
        verdict = "ALLOW"  # anti-pattern 1: breaker trips to ALLOW
    return verdict


def timeout_bad():
    try:
        return asyncio.wait_for(None, timeout=0.5)
    except asyncio.TimeoutError:
        verdict = "ALLOW"  # anti-pattern 2: timeout defaults to ALLOW
        return verdict


def swallow_bad():
    try:
        return 1 / 0
    except ZeroDivisionError:
        pass  # anti-pattern 3: silent swallow


def path_bad(p):
    return p.startswith("/api/delete")  # anti-pattern 4: startswith only
