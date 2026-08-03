"""YAML policy loader + matching engine — declarative, not hardcoded."""

import posixpath
import re
from dataclasses import dataclass, field
from typing import List, Literal, Optional

import yaml

# Valid governance actions. A typo'd action (e.g. "DENYy") would silently fall
# through the gateway's if/elif chain into the else→ALLOW branch — a quiet
# governance bypass. Constrain + normalize at load time (fail-closed: bad
# config refuses to start instead of mis-serving).
VALID_ACTIONS: tuple = ("ALLOW", "DENY", "ESCALATE")


@dataclass
class Rule:
    name: str
    path_pattern: str
    method: Optional[str] = None
    action: Literal["ALLOW", "DENY", "ESCALATE"] = "ALLOW"
    reason: str = ""
    priority: int = 100
    escalation_timeout: int = 300
    escalation_channel: str = "slack"

    def __post_init__(self) -> None:
        # normalize case so YAML "deny" behaves identically to "DENY"
        normalized = str(self.action).upper()
        if normalized not in VALID_ACTIONS:
            raise ValueError(
                f"rule '{self.name}': invalid action {self.action!r} — "
                f"must be one of {VALID_ACTIONS} "
                f"(fail-closed: refusing to start with invalid policy)"
            )
        self.action = normalized

    def matches(self, path: str, method: str) -> bool:
        """Check if this rule matches the request path and method."""
        method_ok = self.method is None or self.method.upper() == method.upper()
        path_ok = self._path_matches(path)
        return method_ok and path_ok

    def _path_matches(self, path: str) -> bool:
        """Support exact match and wildcard patterns like /api/* or /api/config/*.

        v0.2.1 (AUDIT-0006 companion): normpath normalization kills
        '/api/config/../admin' traversal bypasses before matching.
        """
        normalized = posixpath.normpath(path.split("?", 1)[0])
        if self.path_pattern == normalized:
            return True
        if "*" in self.path_pattern:
            pattern = "^" + re.escape(self.path_pattern).replace(r"\*", ".*") + "$"
            return bool(re.match(pattern, normalized))
        if self.path_pattern.endswith("/") and normalized.startswith(self.path_pattern):
            return True
        return False


@dataclass
class PolicyConfig:
    name: str
    version: str
    rules: List[Rule] = field(default_factory=list)


class PolicyEngine:
    def __init__(self, config_path: str = "config/policies.yaml"):
        self.config: PolicyConfig = PolicyConfig(name="default", version="0.1.0")
        self.rules: List[Rule] = []
        self._load(config_path)

    def _load(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data:
            return
        self.config.name = data.get("name", self.config.name)
        self.config.version = data.get("version", self.config.version)
        for rule_data in data.get("rules", []):
            rule = Rule(
                name=rule_data["name"],
                path_pattern=rule_data.get("path_pattern", "/"),
                method=rule_data.get("method"),
                action=rule_data.get("action", "ALLOW"),
                reason=rule_data.get("reason", ""),
                priority=rule_data.get("priority", 100),
                escalation_timeout=rule_data.get("escalation_timeout", 300),
                escalation_channel=rule_data.get("escalation_channel", "slack"),
            )
            self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority)

    def evaluate(self, path: str, method: str) -> Optional[Rule]:
        """Return the first matching rule, or None if nothing matches."""
        for rule in self.rules:
            if rule.matches(path, method):
                return rule
        return None
