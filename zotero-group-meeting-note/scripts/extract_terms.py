#!/usr/bin/env python3
"""Extract recurring English term candidates from paper text or Markdown."""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path


TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-'][A-Za-z0-9]+)?")
ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9-]{1,}\b")

EDGE_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "their",
    "this",
    "to",
    "using",
    "via",
    "we",
    "with",
}

GENERIC_TERMS = {
    "abstract",
    "appendix",
    "baseline",
    "caption",
    "chapter",
    "conclusion",
    "dataset",
    "equation",
    "experiment",
    "figure",
    "introduction",
    "method",
    "paper",
    "result",
    "section",
    "setting",
    "table",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List recurring English technical-term candidates from text files."
    )
    parser.add_argument("paths", nargs="+", help="Text/Markdown files or folders to scan.")
    parser.add_argument("--top", type=int, default=80, help="Maximum rows per section.")
    parser.add_argument("--min-count", type=int, default=2, help="Minimum phrase count.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    return parser.parse_args()


def iter_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_dir():
            files.extend(
                child
                for child in sorted(path.rglob("*"))
                if child.is_file() and child.suffix.lower() in {".md", ".markdown", ".txt"}
            )
        elif path.is_file():
            files.append(path)
    return files


def normalize_phrase(tokens: tuple[str, ...]) -> str:
    return " ".join(token.strip() for token in tokens)


def is_candidate(tokens: tuple[str, ...]) -> bool:
    lowered = tuple(token.lower() for token in tokens)
    if lowered[0] in EDGE_STOPWORDS or lowered[-1] in EDGE_STOPWORDS:
        return False
    if all(token in EDGE_STOPWORDS or token in GENERIC_TERMS for token in lowered):
        return False
    if sum(token in GENERIC_TERMS for token in lowered) > len(lowered) // 2:
        return False
    if any(len(token) == 1 and token.lower() not in {"x", "y"} for token in tokens):
        return False
    return True


def extract(text: str) -> tuple[collections.Counter[str], collections.Counter[str]]:
    acronyms: collections.Counter[str] = collections.Counter(ACRONYM_RE.findall(text))
    phrase_counts: collections.Counter[str] = collections.Counter()
    canonical: dict[str, str] = {}

    for line in text.splitlines():
        if line.lstrip().startswith(("```", "|", "![", "#")):
            continue
        tokens = tuple(match.group(0) for match in TOKEN_RE.finditer(line))
        for size in range(2, 6):
            for index in range(0, max(0, len(tokens) - size + 1)):
                ngram = tokens[index : index + size]
                if not is_candidate(ngram):
                    continue
                key = normalize_phrase(tuple(token.lower() for token in ngram))
                canonical.setdefault(key, normalize_phrase(ngram))
                phrase_counts[canonical[key]] += 1

    return acronyms, phrase_counts


def top_items(counter: collections.Counter[str], limit: int, min_count: int) -> list[dict[str, int | str]]:
    return [
        {"term": term, "count": count}
        for term, count in counter.most_common()
        if count >= min_count
    ][:limit]


def markdown_table(title: str, rows: list[dict[str, int | str]]) -> str:
    lines = [f"## {title}", "", "| term | count |", "| ---- | ----- |"]
    if rows:
        lines.extend(f"| {row['term']} | {row['count']} |" for row in rows)
    else:
        lines.append("| <none> | 0 |")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    files = iter_files(args.paths)
    all_acronyms: collections.Counter[str] = collections.Counter()
    all_phrases: collections.Counter[str] = collections.Counter()

    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        acronyms, phrases = extract(text)
        all_acronyms.update(acronyms)
        all_phrases.update(phrases)

    result = {
        "files": [str(path) for path in files],
        "acronyms": top_items(all_acronyms, args.top, args.min_count),
        "phrases": top_items(all_phrases, args.top, args.min_count),
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("# Candidate Technical Terms")
        print()
        print(f"Scanned files: {len(files)}")
        print()
        print(markdown_table("Acronyms", result["acronyms"]))
        print()
        print(markdown_table("Multi-word Phrases", result["phrases"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
