"""Phase 0: memory_query.py 单元测试 (用 tmp_path 假记忆目录, 不触碰真实记忆)."""

import os
import pathlib
import subprocess
import sys

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "memory_query.py"


def _make_memory(root: pathlib.Path) -> pathlib.Path:
    """构造带 frontmatter + MEMORY.md 索引的假记忆目录, 返回目录。"""
    root.mkdir(parents=True, exist_ok=True)
    (root / "MEMORY.md").write_text(
        "## 2026-08-01\n"
        "- alpha.md | Alpha milestone | project | ...\n"
        "## 2026-08-02\n"
        "- beta.md | Beta lesson | project | ...\n",
        encoding="utf-8",
    )
    (root / "alpha.md").write_text(
        "---\nname: alpha\ndescription: Alpha milestone\n"
        "type: project\n---\n# Alpha\n关键内容 sql 注入\n",
        encoding="utf-8",
    )
    (root / "beta.md").write_text(
        "---\nname: beta\ndescription: Beta lesson\n"
        "type: project\n---\n# Beta\n超时陷阱\n",
        encoding="utf-8",
    )
    # 无索引日期 → 回退 mtime
    (root / "gamma.md").write_text(
        "---\nname: gamma\ndescription: Gamma decision\n"
        "type: decision\n---\n# Gamma\n",
        encoding="utf-8",
    )
    return root


def _run(root: pathlib.Path, *args):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *args],
        capture_output=True, text=True, encoding="utf-8", env=env,
    )


def test_type_filter(tmp_path):
    r = _run(_make_memory(tmp_path), "--type", "project", "--format", "plain")
    assert r.returncode == 0
    assert "alpha" in r.stdout and "beta" in r.stdout
    assert "gamma" not in r.stdout  # type=decision 被过滤


def test_date_range_from_index(tmp_path):
    r = _run(_make_memory(tmp_path), "--since", "2026-08-02", "--format", "plain")
    assert r.returncode == 0
    assert "alpha" not in r.stdout  # 索引日期 08-01 < 08-02
    assert "beta" in r.stdout  # 索引日期 08-02 命中
    assert "gamma" in r.stdout  # 无索引 → mtime(今天) 命中


def test_keyword_fulltext(tmp_path):
    r = _run(_make_memory(tmp_path), "--keyword", "sql", "--format", "plain")
    assert r.returncode == 0
    assert "alpha" in r.stdout  # body 含 "sql 注入"
    assert "beta" not in r.stdout


def test_keyword_case_insensitive(tmp_path):
    r = _run(_make_memory(tmp_path), "--keyword", "SQL", "--format", "plain")
    assert r.returncode == 0
    assert "alpha" in r.stdout


def test_combo_filter(tmp_path):
    r = _run(_make_memory(tmp_path), "--type", "project",
              "--since", "2026-08-01", "--until", "2026-08-01",
              "--keyword", "sql", "--format", "plain")
    assert r.returncode == 0
    assert "alpha" in r.stdout
    assert "beta" not in r.stdout  # until=08-01 排除 08-02


def test_no_match_returns_zero(tmp_path):
    r = _run(_make_memory(tmp_path), "--keyword", "不存在xyz")
    assert r.returncode == 0
    assert "无匹配" in r.stdout


def test_invalid_date_returns_two(tmp_path):
    r = _run(_make_memory(tmp_path), "--since", "2026-13-99")
    assert r.returncode == 2
    assert "YYYY-MM-DD" in r.stderr


def test_table_output_escapes_pipe(tmp_path):
    root = _make_memory(tmp_path)
    (root / "alpha.md").write_text(
        "---\nname: alpha\ndescription: 'a|b'\ntype: project\n---\nx\n",
        encoding="utf-8",
    )
    r = _run(root, "--keyword", "a")
    assert r.returncode == 0
    assert "a\\|b" in r.stdout  # pipe 被转义, 不破坏表格
