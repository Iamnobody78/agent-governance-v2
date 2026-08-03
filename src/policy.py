"""YAML policy loader + matching engine — declarative, not hardcoded."""

import json
import logging
import os
import posixpath
import re
import traceback
from dataclasses import dataclass, field
from typing import List, Literal, Optional

import yaml

logger = logging.getLogger(__name__)

VALID_ACTIONS: tuple = ("ALLOW", "ALLOW_WITH_WARNING", "DENY", "ESCALATE", "SUSPEND")


# ── B 阶段 (TASK-REAL-010): json_path 条件规则支持 ──────────────────
# 规则可选携带 json_path (+ json_pattern): 规则在路径/方法匹配之外, 还要求
# 请求体 JSON 中该路径提取出的值匹配模式。语法为零依赖的 JSONPath 子集:
#   $         根 (可选前缀)
#   .key      字典成员
#   ..name    递归下降 — 任意深度的 'name' 成员
#   [N]       列表索引
#   [*]       任意列表元素 / 任意字典值
# 安全语义: 非 JSON 体 / 无法提取 → 条件不满足 → 规则不匹配 (结构化体才承载
# 工具调用; 无法解析体的兜底由 fail-closed 层负责, 见 docs/)。

def _parse_json_path(path: str) -> list:
    """Tokenize a json_path into segments: ('key', n) | ('idx', n) | ('wild',) | ('descend',).

    Raises ValueError on malformed syntax — callers treat that as fail-closed.
    """
    if not isinstance(path, str) or not path.strip():
        raise ValueError("json_path must be a non-empty string")
    rest = path.strip()
    if rest[:1] == "$":
        rest = rest[1:]
    segments = []
    i = 0
    n = len(rest)
    while i < n:
        c = rest[i]
        if c == ".":
            # '..' = recursive descent; single '.' is a separator
            if i + 1 < n and rest[i + 1] == ".":
                segments.append(("descend",))
                i += 2
            else:
                i += 1
            continue
        if c == "[":
            j = rest.find("]", i)
            if j == -1:
                raise ValueError(f"json_path: unterminated '[' at position {i}")
            inner = rest[i + 1:j].strip()
            if inner == "*":
                segments.append(("wild",))
            elif inner.isdigit():
                segments.append(("idx", int(inner)))
            else:
                raise ValueError(f"json_path: unsupported bracket {inner!r} at position {i}")
            i = j + 1
            continue
        # bare key — read until '.' or '['
        j = i
        while j < n and rest[j] not in ".[":
            j += 1
        segments.append(("key", rest[i:j]))
        i = j
    return segments


def _node_children(node):
    """Child nodes for traversal: dict values / list items / none."""
    if isinstance(node, dict):
        return list(node.values())
    if isinstance(node, list):
        return node
    return []


def _extract_at(node, segments, idx, out) -> None:
    """Depth-first walk; append every node reached by the full segment list."""
    if idx >= len(segments):
        out.append(node)
        return
    kind = segments[idx][0]
    if kind == "descend":
        # (1) try matching the remainder at the current node
        _extract_at(node, segments, idx + 1, out)
        # (2) keep descending into children with 'descend' still active
        for child in _node_children(node):
            _extract_at(child, segments, idx, out)
        return
    if isinstance(node, dict):
        if kind == "key":
            key = segments[idx][1]
            if key in node:
                _extract_at(node[key], segments, idx + 1, out)
        elif kind == "wild":
            for value in node.values():
                _extract_at(value, segments, idx + 1, out)
        return
    if isinstance(node, list):
        if kind == "idx":
            j = segments[idx][1]
            if 0 <= j < len(node):
                _extract_at(node[j], segments, idx + 1, out)
        elif kind == "wild":
            for item in node:
                _extract_at(item, segments, idx + 1, out)
        return


def _json_extract(body, json_path: str) -> List[str]:
    """Extract json_path values from a body as a list of matchable strings.

    Values are stringified for regex matching: scalars via str, containers
    via compact JSON. Non-dict/list bodies (None, undecodable str, scalar)
    yield [] — the caller treats an unextractable body as 'rule cannot apply'
    (safe fallback: no structured tool call can exist in an unparseable body).
    """
    if isinstance(body, str) and body.strip():
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            return []
    if body is None or isinstance(body, (str, int, float, bool)):
        return []
    segments = _parse_json_path(json_path)  # validated at rule load; still guarded
    found = []
    _extract_at(body, segments, 0, found)
    strings = []
    for v in found:
        if isinstance(v, bool):
            strings.append("true" if v else "false")
        elif isinstance(v, (dict, list)):
            strings.append(json.dumps(v, separators=(",", ":"), ensure_ascii=False))
        else:
            strings.append(str(v))
    return strings


@dataclass
class Rule:
    name: str
    path_pattern: str
    method: Optional[str] = None
    action: Literal["ALLOW", "ALLOW_WITH_WARNING", "DENY", "ESCALATE", "SUSPEND"] = "ALLOW"
    reason: str = ""
    priority: int = 100
    escalation_timeout: int = 300
    escalation_channel: str = "slack"
    # TASK-REAL-010 (B): 条件规则字段 — 命中路径/方法后还需检查请求体 JSON
    json_path: Optional[str] = None      # JSONPath 子集 (见 _parse_json_path)
    json_pattern: Optional[str] = None   # 与提取值匹配的正则 (re.search 语义)

    def __post_init__(self) -> None:
        normalized = str(self.action).upper()
        if normalized not in VALID_ACTIONS:
            raise ValueError(
                f"rule '{self.name}': invalid action {self.action!r} — "
                f"must be one of {VALID_ACTIONS} "
                f"(fail-closed: refusing to start with invalid policy)"
            )
        self.action = normalized
        # TASK-REAL-010 (B): json_path 规则加载期校验 — 语法错误/缺配对字段的
        # 规则拒绝载入 (fail-closed), 不允许带病规则进入热加载。
        if self.json_pattern is not None and self.json_path is None:
            raise ValueError(
                f"rule '{self.name}': json_pattern requires json_path — "
                f"body 模式规则必须有提取路径 (fail-closed)"
            )
        if self.json_path is not None:
            _parse_json_path(self.json_path)  # raises ValueError on bad syntax
            if self.json_pattern is not None:
                try:
                    re.search(self.json_pattern, "")
                except re.error as e:
                    raise ValueError(
                        f"rule '{self.name}': invalid json_pattern "
                        f"{self.json_pattern!r} — {e} (fail-closed)"
                    ) from e

    def matches(self, path: str, method: str, body=None) -> bool:
        method_ok = self.method is None or self.method.upper() == method.upper()
        path_ok = self._path_matches(path)
        if not (method_ok and path_ok):
            return False
        if self.json_path is None:
            return True
        # 条件规则: 请求体 JSON 中 json_path 提取值需匹配 json_pattern。
        # 非 JSON 体/无法提取 → 条件不满足 → 规则不匹配 (安全回退)。
        values = _json_extract(body, self.json_path)
        if not values:
            return False
        if self.json_pattern is None:
            return True  # 仅要求路径存在 (调用方自行保证该语义的合理性)
        return any(re.search(self.json_pattern, v) for v in values)

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
            # DEBT-0012: empty policies.yaml must NOT silently start with zero rules
            # (all requests would ALLOW). Fail-closed: refuse to load.
            # reload() catches this and keeps old rules (safe hot-reload); only the
            # initial __init__ load propagates → gateway refuses to start.
            raise ValueError("policies.yaml is empty — refusing to load (fail-closed); add at least one rule or fix the YAML")
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
                json_path=rule_data.get("json_path"),
                json_pattern=rule_data.get("json_pattern"),
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
        """Re-read YAML from self._config_path. On failure keep old rules.

        P0 (暗雷区): 之前 `except Exception: return False` 完全静默 —— reload 失败
        时运维无任何线索。改为 error 级完整堆栈（保留旧规则的行为不变，fail-safe）。
        """
        try:
            self._load(self._config_path)
            return True
        except Exception as e:  # noqa: BLE001 — keep old rules on any load error
            logger.exception("policy reload FAILED (keeping %d old rules): %s",
                             len(self.rules), e)
            logger.debug("policy reload traceback:\n%s", traceback.format_exc())
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

    def evaluate(self, path: str, method: str, body=None) -> Optional[Rule]:
        """First matching rule by priority; json_path rules inspect `body`.

        Backward compatible: rules without json_path ignore `body` entirely,
        so existing callers (path/method only) keep identical behavior.
        """
        for rule in self.rules:
            if rule.matches(path, method, body):
                return rule
        return None
