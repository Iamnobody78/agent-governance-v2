"""YAML policy loader + matching engine — declarative, not hardcoded."""

import os
import posixpath
import re
from dataclasses import dataclass, field
from typing import List, Literal, Optional

import yaml

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
        normalized = str(self.action).upper()
        if normalized not in VALID_ACTIONS:
            raise ValueError(
                f"rule '{self.name}': invalid action {self.action!r} — "
                f"must be one of {VALID_ACTIONS} "
                f"(fail-closed: refusing to start with invalid policy)"
            )
        self.action = normalized

    def matches(self, path: str, method: str) -> bool:
        method_ok = self.method is None or self.method.upper() == method.upper()
        path_ok = self._path_matches(path)
        return method_ok and path_ok

    def _path_matches(self, path: str) -> bool:
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
    def __init__(self, config_path: Optional[str] = "config/policies.yaml"):
        if config_path is None:
            config_path = "config/policies.yaml"
        self.config: PolicyConfig = PolicyConfig(name="default", version="0.1.0")
        self.rules: List[Rule] = []
        self._config_path = str(config_path)
        self._last_mtime = 0.0
        self._load(str(config_path))

    def _load(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data:
            return
        new_rules = []
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
            new_rules.append(rule)
        new_rules.sort(key=lambda r: r.priority)
        self.rules = new_rules
        self.config.name = data.get("name", self.config.name)
        self.config.version = data.get("version", self.config.version)
        try:
            self._last_mtime = os.path.getmtime(path)
        except OSError:
            pass

    def reload(self) -> bool:
        """Re-read YAML from self._config_path. On failure keep old rules."""
        try:
            self._load(self._config_path)
            return True
        except Exception:
            return False

    def maybe_reload(self) -> bool:
        """Hot-reload: reload only if config mtime changed (DEBT-0005)."""
        try:
            mtime = os.path.getmtime(self._config_path)
        except OSError:
            return False
        if mtime != self._last_mtime:
            return self.reload()
        return False

    def evaluate(self, path: str, method: str) -> Optional[Rule]:
        for rule in self.rules:
            if rule.matches(path, method):
                return rule
        return None
