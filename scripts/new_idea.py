#!/usr/bin/env python3
"""新建一条奇思妙想，或者刷新 README 里的想法索引。

用法::

    python scripts/new_idea.py "会自己长大的桌面植物" --tags 桌面,养成
    python scripts/new_idea.py "标题" --status exploring --date 2026-10-20
    python scripts/new_idea.py --reindex

只依赖 Python 标准库。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IDEAS_DIR = ROOT / "ideas"
TEMPLATE_PATH = IDEAS_DIR / "_template.md"
README_PATH = ROOT / "README.md"

INDEX_START = "<!-- ideas:start -->"
INDEX_END = "<!-- ideas:end -->"

STATUS_ICONS = {
    "seed": "🌱",
    "exploring": "🔭",
    "building": "🛠️",
    "done": "✅",
    "shelved": "🧊",
}
STATUSES = tuple(STATUS_ICONS)

FALLBACK_TEMPLATE = """---
title: {{title}}
date: {{date}}
tags: [{{tags}}]
status: {{status}}
spark:
---

## 想法

<!-- 一句话：它是什么？ -->

## 为什么心动

<!-- 哪里好玩？解决了什么小问题？ -->

## 怎么做

<!-- 第一条实现路径，越具体越好 -->

## 下一步

- [ ]

## 参考

-
"""


def configure_stdio() -> None:
    """让 Windows 控制台也按 UTF-8 输出，避免中文和 emoji 报错。"""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


def slugify(title: str) -> str:
    """从标题生成一个适合做文件名的短后缀。"""
    text = unicodedata.normalize("NFKC", title).strip()
    text = re.sub(r"[^\w\s-]", " ", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-.")
    text = text.lower()[:48].strip("-.")
    return text or "idea"


def load_template() -> str:
    if TEMPLATE_PATH.exists():
        return TEMPLATE_PATH.read_text(encoding="utf-8")
    return FALLBACK_TEMPLATE


def render_template(template: str, *, title: str, day: str, tags: list[str], status: str) -> str:
    return (
        template.replace("{{title}}", json.dumps(title, ensure_ascii=False))
        .replace("{{date}}", day)
        .replace("{{tags}}", ", ".join(tags))
        .replace("{{status}}", status)
    )


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        if value[0] == '"':
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        return value[1:-1]
    return value


def read_meta(path: Path) -> dict:
    """从 Markdown 文件的 front matter 里读出索引需要的字段。"""
    text = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    if text.startswith("---"):
        block_end = text.find("\n---", 3)
        if block_end != -1:
            for line in text[3:block_end].splitlines():
                key, sep, raw = line.partition(":")
                if sep:
                    meta[key.strip().lower()] = raw.strip()

    tags_raw = meta.get("tags", "").strip()
    if tags_raw.startswith("["):
        tags_raw = tags_raw[1:]
        if tags_raw.endswith("]"):
            tags_raw = tags_raw[:-1]

    return {
        "title": _unquote(meta.get("title", "")) or path.stem,
        "date": _unquote(meta.get("date", "")),
        "status": _unquote(meta.get("status", "")) or "seed",
        "tags": [t.strip().strip("'\"") for t in tags_raw.split(",") if t.strip()],
        "filename": path.name,
    }


def build_index() -> str:
    """根据 ideas/ 目录生成 Markdown 表格。"""
    entries = [read_meta(p) for p in sorted(IDEAS_DIR.glob("*.md")) if not p.name.startswith("_")]
    entries.sort(key=lambda e: (e["date"], e["filename"]), reverse=True)

    lines = ["| 日期 | 想法 | 状态 | 标签 |", "| --- | --- | --- | --- |"]
    for entry in entries:
        title = (entry["title"] or entry["filename"]).replace("|", "\\|")
        status = entry["status"]
        icon = STATUS_ICONS.get(status, "🌱")
        tags = " ".join(f"`{tag}`" for tag in entry["tags"]) or "—"
        lines.append(
            f"| {entry['date'] or '—'} | [{title}](ideas/{entry['filename']}) | {icon} {status} | {tags} |"
        )
    if not entries:
        lines.append("| — | 还没有想法，去写第一条吧。 | — | — |")
    return "\n".join(lines)


def update_readme() -> None:
    if not README_PATH.exists():
        raise RuntimeError(f"找不到 {README_PATH}")
    text = README_PATH.read_text(encoding="utf-8")
    if INDEX_START not in text or INDEX_END not in text:
        raise RuntimeError(f"README 里找不到索引标记 {INDEX_START} / {INDEX_END}")
    head, _, rest = text.partition(INDEX_START)
    _, _, tail = rest.partition(INDEX_END)
    with README_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(f"{head}{INDEX_START}\n{build_index()}\n{INDEX_END}{tail}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="新建一条奇思妙想，或刷新 README 中的想法索引。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：python scripts/new_idea.py \"会自己长大的桌面植物\" --tags 桌面,养成",
    )
    parser.add_argument("title", nargs="?", help="想法标题")
    parser.add_argument("--tags", default="", help="标签，逗号或顿号分隔，例如：桌面,养成")
    parser.add_argument("--status", default="seed", choices=STATUSES, help="状态，默认 seed")
    parser.add_argument("--date", default="", help="记录日期，格式 YYYY-MM-DD，默认今天")
    parser.add_argument("--slug", default="", help="文件名后缀，默认由标题生成")
    parser.add_argument("--no-index", action="store_true", help="创建后不刷新 README 索引")
    parser.add_argument("--reindex", action="store_true", help="只刷新 README 索引")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    args = parse_args(argv)

    if args.reindex:
        try:
            update_readme()
        except RuntimeError as exc:
            print(f"✗ {exc}", file=sys.stderr)
            return 1
        print("✓ 已刷新 README 想法索引")
        return 0

    if not args.title or not args.title.strip():
        print(
            '请提供想法标题，例如：python scripts/new_idea.py "会自己长大的桌面植物"',
            file=sys.stderr,
        )
        return 2
    title = args.title.strip()

    if args.date:
        try:
            day = dt.date.fromisoformat(args.date.strip())
        except ValueError:
            print(f"✗ 日期格式不对：{args.date}，应为 YYYY-MM-DD", file=sys.stderr)
            return 2
    else:
        day = dt.date.today()

    tags = [tag.strip() for tag in re.split(r"[,，、]", args.tags) if tag.strip()]
    slug = args.slug.strip() if args.slug.strip() else slugify(title)
    if not re.fullmatch(r"[\w.-]+", slug, flags=re.UNICODE) or slug in (".", ".."):
        print("✗ slug 只能包含字母、数字、下划线、点和连字符", file=sys.stderr)
        return 2

    IDEAS_DIR.mkdir(parents=True, exist_ok=True)
    path = IDEAS_DIR / f"{day.isoformat()}-{slug}.md"
    if path.exists():
        print(f"✗ 文件已存在：{path.relative_to(ROOT).as_posix()}", file=sys.stderr)
        return 1

    content = render_template(
        load_template(), title=title, day=day.isoformat(), tags=tags, status=args.status
    )
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    print(f"✓ 已创建 {path.relative_to(ROOT).as_posix()}")

    if not args.no_index:
        try:
            update_readme()
            print("✓ 已刷新 README 想法索引")
        except RuntimeError as exc:
            print(f"! 索引未刷新：{exc}", file=sys.stderr)

    print("下一步：打开文件，补上「为什么心动」和「下一步」。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
