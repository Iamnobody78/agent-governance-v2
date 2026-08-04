#!/usr/bin/env python3
"""Phase 0: 结构化记忆检索 — memory_query.py (零依赖, 纯标准库).

按 type / 日期范围 / 关键词组合查询 aionrs 记忆目录, 输出 Markdown 表格.
日期来源优先级: MEMORY.md 索引分组日期 > frontmatter date 字段 > mtime.
type 为 frontmatter 真实值 (project/user/feedback/reference), 非语义类.
keyword 对全文 (name+description+body) 大小写不敏感.

用法:
  python scripts/memory_query.py --type project
  python scripts/memory_query.py --since 2026-08-01 --until 2026-08-31
  python scripts/memory_query.py --keyword sql --type project
"""

import argparse
import os
import pathlib
import re
import sys
from datetime import datetime

DEFAULT_ROOT = pathlib.Path(
    os.environ.get(
        "AIONRS_MEMORY_ROOT",
        r"C:\Users\ivy\AppData\Roaming\aionrs\projects"
        r"\C--Users-ivy-AppData-Roaming-AionUi-aionui-conversations"
        r"-2026-07-27-aionrs-temp-48324704\memory",
    )
)
_FM = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_GROUP = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$")
_INDEX = re.compile(r"^-\s+([\w.\-]+\.md)\s*\|")


def parse_frontmatter(text):
    """返回 (fields: dict, body: str)。frontmatter 缺失时 fields 为空 dict。"""
    m = _FM.match(text)
    if not m:
        return {}, text
    fields = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fields[k.strip()] = v.strip()
    return fields, text[m.end():]


def index_dates(root):
    """解析 MEMORY.md 的 '## 日期' 分组: {filename: 日期}。"""
    idx = root / "MEMORY.md"
    if not idx.exists():
        return {}
    result, current = {}, None
    for line in idx.read_text(encoding="utf-8").splitlines():
        g = _GROUP.match(line)
        if g:
            current = g.group(1)
            continue
        m = _INDEX.match(line)
        if m and current:
            result[m.group(1)] = current
    return result


def collect(root):
    """返回 [{name, path, type, date, date_src, description, body}]。"""
    idx_dates = index_dates(root)
    entries = []
    for p in sorted(root.glob("*.md")):
        if p.name == "MEMORY.md":
            continue
        fields, body = parse_frontmatter(p.read_text(encoding="utf-8"))
        d, src = idx_dates.get(p.name), "index"
        if not d and fields.get("date"):
            d, src = fields["date"], "frontmatter"
        if not d:
            d, src = datetime.fromtimestamp(p.stat().st_mtime).date().isoformat(), "mtime"
        entries.append({
            "name": fields.get("name", p.stem), "path": p,
            "type": fields.get("type", ""), "date": d, "date_src": src,
            "description": fields.get("description", ""), "body": body,
        })
    return entries


def match(e, a):
    if a.type and e["type"] != a.type:
        return False
    if a.since and e["date"] < a.since:
        return False
    if a.until and e["date"] > a.until:
        return False
    if a.keyword:
        hay = f'{e["name"]}\n{e["description"]}\n{e["body"]}'.lower()
        if a.keyword.lower() not in hay:
            return False
    return True


def main(argv=None):
    # Windows 控制台 cp950 无法编码 CJK 记忆内容 → 强制 UTF-8 输出
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="结构化记忆检索 (Phase 0)")
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="记忆目录")
    ap.add_argument("--type", help="frontmatter type 精确匹配")
    ap.add_argument("--since", help="起始日期 YYYY-MM-DD (含)")
    ap.add_argument("--until", help="结束日期 YYYY-MM-DD (含)")
    ap.add_argument("--keyword", help="全文大小写不敏感关键词")
    ap.add_argument("--format", choices=["table", "plain"], default="table")
    args = ap.parse_args(argv)

    root = pathlib.Path(args.root)
    if not root.is_dir():
        print(f"ERROR: 记忆目录不存在: {root}", file=sys.stderr)
        return 2
    try:
        since = args.since or None
        until = args.until or None
        for v in (since, until):
            if v:
                datetime.strptime(v, "%Y-%m-%d")  # 验证格式, 非法则抛 ValueError
    except ValueError:
        print("ERROR: 日期格式须为 YYYY-MM-DD", file=sys.stderr)
        return 2

    ns = argparse.Namespace(type=args.type, since=since, until=until, keyword=args.keyword)
    hits = [e for e in collect(root) if match(e, ns)]
    if not hits:
        print("(无匹配记忆条目)")
        return 0

    if args.format == "plain":
        for e in hits:
            src = "" if e["date_src"] == "index" else f" [{e['date_src']}]"
            print(f"{e['date']}{src}  {e['type']:9}  {e['name']}")
            print(f"    {e['description']}")
    else:
        print("| date | type | name | description |")
        print("|------|------|------|-------------|")
        for e in hits:
            src = "" if e["date_src"] == "index" else f" ({e['date_src']})"
            desc = e["description"].replace("|", "\\|")
            print(f"| {e['date']}{src} | {e['type']} | {e['name']} | {desc} |")
    print(f"\n共 {len(hits)} 条记忆")
    return 0


if __name__ == "__main__":
    sys.exit(main())
