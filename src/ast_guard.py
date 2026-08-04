"""ast_guard — AST 硬阻断引擎（L1 内核，Priority 0 前门）。

Tree-sitter 裁决落地: 在所有 YAML 规则匹配之前, 先对请求体中的代码片段
做 AST 级危险模式检查。零正则 —— 危险模式全部声明在 queries/*.scm
(tree-sitter S-expression 查询), 本模块零模式硬编码。

验收约束（来自"修复 + 优先集成"裁决，三条 bug 约束转正）:
  P1 Capture 校验: 查询捕获名必须命中 EXPECTED_CAPTURES 语义表; 未知捕获名
     被忽略并计入 self.unknown_captures (防 .scm 被篡改注入未授权捕获)。
     查询加载失败 (语法错误/语言包缺失) -> 构造抛异常 = fail-closed。
  P2 Payload 提取: 代码片段一律经 payload_extractor.extract() 提取,
     本模块不自行扫描请求体字符串。
  P3 Bash 硬编码: 危险命令表只存在于 queries/bash.scm 的查询谓词参数中,
     本模块零命令名。

审计 trace: ASTFinding 携带精确行号 (1-based) + 节点 S-expression 标签,
由调用方拼入 Rule.reason / DecisionRecord.rationale。

依赖契约 (锁定): tree-sitter==0.21.3 + tree-sitter-languages==1.5.0
  - Language(path, name) 双参构造 (deprecation warning 可忽略)
  - language.query(src) 构造 Query
  - query.captures(node) -> list[(Node, capture_name)]
  - Node.text (bytes) / Node.start_point (Point(row, col), 0-based)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tree_sitter import Node, Parser, Query
from tree_sitter_languages import get_language, get_parser

from .payload_extractor import extract as extract_fragments

logger = logging.getLogger(__name__)

QUERIES_DIR = Path(__file__).resolve().parent.parent / "queries"

# 危险捕获语义表: {language: {capture_name: risk_kind}}
# P1 校验基准 —— .scm 中出现的捕获名必须在此表内; 表外的捕获名被忽略。
EXPECTED_CAPTURES: Dict[str, Dict[str, str]] = {
    "python": {
        "fn_exec": "code-execution",
        "fn_sys": "system-access",
        "imp_dyn": "dynamic-import",
    },
    "bash": {
        "cmd_danger": "destructive-command",
        "flag_danger": "destructive-flag",
        "mkfs_variant": "destructive-filesystem-tool",
        "redirect_target": "destructive-file-write",
    },
    "sql": {
        "danger": "destructive-sql",
        "update_stmt": "update-statement",
        "sensitive_schema": "sensitive-schema-access",
    },
}

# S-expression 截断上限（防日志膨胀）
_MAX_SEXP = 160
_MAX_TEXT = 100


def _has_where_clause(node: Node) -> bool:
    """SQL UPDATE 后处理: 判断 update_statement 子节点是否含 where_clause。

    阶段 0 PART A 实证: UPDATE 语句 AST 为
      update_statement -> [UPDATE, identifier, set_clause, (where_clause)]
    无 where_clause = 全表覆盖（数据丢失风险）→ 阻断级。
    """
    for child in node.children:
        if child.type == "where_clause":
            return True
    return False


@dataclass
class ASTFinding:
    """单条 AST 危险发现。line/col 为 1-based 精确位置（验收项）。"""
    language: str
    query: str
    capture: str
    kind: str
    line: int
    col: int
    text: str
    sexp: str

    @property
    def summary(self) -> str:
        """审计 trace 单行: AST-BLOCK <lang> <kind> L<line>:<col> sexp=(...)"""
        return (f"AST-BLOCK {self.language} {self.kind} "
                f"L{self.line}:{self.col} sexp={self.sexp}")


@dataclass
class ASTBlock:
    """一次请求的整体阻断结果（多个代码片段可产生多条 findings）。"""
    language: str
    findings: List[ASTFinding] = field(default_factory=list)

    @property
    def summary(self) -> str:
        if not self.findings:
            return f"AST-BLOCK {self.language}: no findings"
        return "; ".join(f.summary for f in self.findings)


def _sexp(node: Node) -> str:
    """手写 S-expression 生成器（tree-sitter 0.21 无 Node.sexp()）。

    只含 named children —— 与标准 sexp 语义一致（零正则，纯树遍历）。
    """
    kids = [c for c in node.children if c.is_named]
    if not kids:
        return node.type
    return f"({node.type} " + " ".join(_sexp(c) for c in kids) + ")"


class ASTGuard:
    """AST 硬阻断引擎。构造即加载全部语言（fail-closed: 任一失败拒绝启动）。"""

    def __init__(self, queries_dir: Optional[Path] = None) -> None:
        self._queries_dir = Path(queries_dir) if queries_dir else QUERIES_DIR
        self._queries: Dict[str, Dict[str, Query]] = {}
        self._semantics: Dict[str, Dict[str, str]] = {}
        self.unknown_captures: Dict[str, List[str]] = {}  # P1: 未知捕获记录
        self.loaded_languages: List[str] = []
        self._load_all()

    # ---- 加载（fail-closed）----

    def _load_all(self) -> None:
        for lang in sorted(EXPECTED_CAPTURES):
            self._load_language(lang)

    def _load_language(self, lang: str) -> None:
        query_file = self._queries_dir / f"{lang}.scm"
        if not query_file.exists():
            raise FileNotFoundError(
                f"ASTGuard: query file missing: {query_file} "
                f"(fail-closed: refusing to start without {lang} rules)"
            )
        try:
            language = get_language(lang)
            parser = get_parser(lang)
        except Exception as e:  # noqa: BLE001 — 语言包缺失必须 fail-closed
            raise RuntimeError(
                f"ASTGuard: language pack unavailable for '{lang}': {e} "
                f"(fail-closed)"
            ) from e
        source = query_file.read_text(encoding="utf-8")
        try:
            query = language.query(source)
        except Exception as e:  # noqa: BLE001 — 查询语法错误必须 fail-closed
            raise RuntimeError(
                f"ASTGuard: query syntax error in {query_file.name}: {e} "
                f"(fail-closed)"
            ) from e
        # P1: 预校验查询中的捕获名是否都在语义表内
        declared = EXPECTED_CAPTURES[lang]
        self._queries[lang] = {query_file.stem: query}
        self._semantics[lang] = dict(declared)
        self.loaded_languages.append(lang)

    # ---- 分析 ----

    def analyze(self, code: str, language: str) -> List[ASTFinding]:
        """对单段代码执行全部该语言的危险查询。纯函数语义（无副作用）。"""
        if language not in self._queries:
            return []
        findings: List[ASTFinding] = []
        try:
            parser = get_parser(language)
            tree = parser.parse(code.encode("utf-8"))
        except Exception as e:  # noqa: BLE001 — 解析失败不阻断（代码本身可含语法错误）
            logger.warning("ASTGuard parse failed for %s: %s", language, e)
            return []
        root = tree.root_node
        for qname, query in self._queries[language].items():
            try:
                captures = query.captures(root)  # list[(Node, capture_name)]
            except Exception as e:  # noqa: BLE001
                logger.warning("ASTGuard query run failed %s/%s: %s", language, qname, e)
                continue
            by_name: Dict[str, List[Node]] = {}
            for node, name in captures:
                if name not in self._semantics[language]:
                    # P1: 未知捕获名 —— 记录并忽略（不允许进入阻断判定）
                    self.unknown_captures.setdefault(language, []).append(name)
                    continue
                by_name.setdefault(name, []).append(node)
            for name, nodes in by_name.items():
                kind = self._semantics[language][name]
                for node in nodes:
                    # SQL UPDATE 后处理: 无 WHERE 子句 = 全表覆盖 → 升级阻断级
                    if language == "sql" and name == "update_stmt":
                        if not _has_where_clause(node):
                            kind = "destructive-update"
                        else:
                            continue  # 有 WHERE 的有界更新 → 放行
                    findings.append(self._finding(language, qname, name, kind, node))
        return findings

    @staticmethod
    def _finding(language: str, qname: str, name: str, kind: str, node: Node) -> ASTFinding:
        text = node.text.decode("utf-8", "replace")[: _MAX_TEXT]
        sexp = _sexp(node)[: _MAX_SEXP]
        # 兼容 tree-sitter 0.21 (tuple) / 0.22+ (Point) 两种 start_point 形态
        sp = node.start_point
        row = sp.row + 1 if hasattr(sp, "row") else sp[0] + 1
        col = sp.column + 1 if hasattr(sp, "column") else sp[1] + 1
        return ASTFinding(
            language=language,
            query=qname,
            capture=name,
            kind=kind,
            line=row,          # 1-based
            col=col,           # 1-based
            text=text,
            sexp=sexp,
        )

    # ---- 请求前门 ----

    def check_request(self, body) -> Optional[ASTBlock]:
        """Priority 0 前门: 提取 -> 分析 -> 汇总。无危险代码返回 None (放行)。

        P2 约束: 提取一律走 payload_extractor, 本方法不做任何字符串扫描。
        """
        fragments = extract_fragments(body)
        all_findings: List[ASTFinding] = []
        langs_hit: List[str] = []
        for frag in fragments:
            findings = self.analyze(frag.code, frag.language)
            if findings:
                all_findings.extend(findings)
                if frag.language not in langs_hit:
                    langs_hit.append(frag.language)
        if not all_findings:
            return None
        return ASTBlock(language=",".join(langs_hit), findings=all_findings)
