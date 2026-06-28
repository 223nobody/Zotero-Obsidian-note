#!/usr/bin/env python3
"""Audit final-note content depth and return a repair decision."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(?P<title>.+?)\s*$", re.MULTILINE)
EVIDENCE_LABEL_RE = re.compile(
    r"\b(Figure|Fig\.|Table|Equation|Eq\.|Algorithm|Objective|Loss|Score|Constraint|Prompt|Case Study)\s*[A-Za-z]?\d*",
    re.IGNORECASE,
)
PLACEHOLDER_RE = re.compile(
    r"(<[^>\n]+>|TODO|TBD|待补充|待完善|无法确认|解析文本不稳定|可复核数字包括)",
    re.IGNORECASE,
)
INTERNAL_RE = re.compile(
    r"(source pack|evidence manifest|quality gate|asset dump|MinerU asset|MinerU extra crop|copy-map)",
    re.IGNORECASE,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit whether a group-meeting note is ready for final delivery."
    )
    parser.add_argument("--note", required=True, help="Markdown note path.")
    parser.add_argument("--source-pack", help="Optional source_pack.json path.")
    parser.add_argument("--evidence-manifest", help="Optional evidence manifest JSON path.")
    parser.add_argument("--blueprint", help="Optional references/blueprint.md path.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig", errors="ignore"))


def headings(text: str) -> list[dict[str, Any]]:
    return [
        {
            "level": len(match.group(1)),
            "title": match.group("title").strip(),
            "line": text.count("\n", 0, match.start()) + 1,
            "start": match.start(),
            "end": 0,
        }
        for match in HEADING_RE.finditer(text)
    ]


def sections(text: str) -> list[dict[str, Any]]:
    rows = headings(text)
    for index, row in enumerate(rows):
        row["end"] = rows[index + 1]["start"] if index + 1 < len(rows) else len(text)
        row["body"] = text[row["start"] : row["end"]]
    return rows


def section_by_keywords(rows: list[dict[str, Any]], *keywords: str) -> dict[str, Any] | None:
    lowered = [keyword.lower() for keyword in keywords]
    for row in rows:
        title = str(row["title"]).lower()
        if any(keyword in title for keyword in lowered):
            return row
    return None


def score_length(body: str, minimum: int) -> float:
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", body)
    compact = re.sub(r"\s+", "", text)
    return min(1.0, len(compact) / minimum) if minimum else 1.0


def iter_manifest_items(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if "items" in manifest:
        return list(manifest.get("items", []))
    return list(manifest.get("main_items", [])) + list(manifest.get("post_reference_items", []))


def manifest_stats(path_text: str | None) -> dict[str, int]:
    if not path_text:
        return {}
    path = Path(path_text).expanduser().resolve()
    if not path.is_file():
        return {}
    items = iter_manifest_items(read_json(path))
    required = [item for item in items if item.get("required_in_final")]
    labels = [str(item.get("label", "")) for item in required if item.get("label")]
    return {
        "manifest_items": len(items),
        "required_items": len(required),
        "required_labels": len(labels),
    }


def coverage_score(text: str, manifest_path: str | None) -> tuple[float, list[str]]:
    if not manifest_path:
        labels = set(match.group(0).strip() for match in EVIDENCE_LABEL_RE.finditer(text))
        return (1.0 if labels else 0.45), []
    path = Path(manifest_path).expanduser().resolve()
    if not path.is_file():
        return 0.0, [f"Evidence manifest not found: {path}"]
    items = iter_manifest_items(read_json(path))
    required = [item for item in items if item.get("required_in_final")]
    if not required:
        return 0.7, []
    missing = [
        str(item.get("label", ""))
        for item in required
        if item.get("label") and str(item.get("label")) not in text
    ]
    return (len(required) - len(missing)) / len(required), missing


def determine_status(scores: dict[str, float], repair_plan: list[dict[str, str]]) -> str:
    if any(item["repair_level"] == "regeneration" for item in repair_plan):
        return "needs_regeneration"
    if any(score < 0.45 for score in scores.values()):
        return "needs_major_repair"
    if any(item["repair_level"] == "major" for item in repair_plan):
        return "needs_major_repair"
    if any(score < 0.7 for score in scores.values()) or repair_plan:
        return "needs_minor_repair"
    return "pass"


def add_repair(
    repair_plan: list[dict[str, str]],
    section: str,
    problem: str,
    repair_level: str = "minor",
) -> None:
    repair_plan.append(
        {
            "section": section,
            "problem": problem,
            "repair_level": repair_level,
        }
    )


def audit(note_path: Path, source_pack: str | None, manifest_path: str | None, blueprint: str | None) -> dict[str, Any]:
    text = note_path.read_text(encoding="utf-8", errors="ignore")
    rows = sections(text)
    repair_plan: list[dict[str, str]] = []

    conclusion = section_by_keywords(rows, "核心", "conclusion")
    problem = section_by_keywords(rows, "问题", "背景", "定位", "problem")
    innovation = section_by_keywords(rows, "创新", "contribution")
    method = section_by_keywords(rows, "方法", "系统", "机制", "method", "system")
    evidence = section_by_keywords(rows, "图", "表", "公式", "evidence", "figure")
    related = section_by_keywords(rows, "相关", "related")
    limitation = section_by_keywords(rows, "局限", "讨论", "limitation", "discussion")

    scores = {
        "blueprint_structure": 1.0 if len([row for row in rows if row["level"] <= 2]) >= 6 else 0.35,
        "core_conclusion": score_length(conclusion.get("body", "") if conclusion else "", 220),
        "problem_positioning": score_length(problem.get("body", "") if problem else "", 260),
        "innovation_analysis": score_length(innovation.get("body", "") if innovation else "", 300),
        "method_explanation": score_length(method.get("body", "") if method else "", 320),
        "evidence_depth": score_length(evidence.get("body", "") if evidence else "", 420),
        "related_work": score_length(related.get("body", "") if related else "", 220),
        "limitations_discussion": score_length(limitation.get("body", "") if limitation else "", 260),
        "terminology": 0.75 if re.search(r"[A-Za-z][A-Za-z -]{3,}\s*[（(]", text) else 0.5,
    }

    coverage, missing = coverage_score(text, manifest_path)
    scores["evidence_coverage"] = coverage
    if missing:
        add_repair(
            repair_plan,
            "evidence coverage",
            "Missing required evidence labels: " + ", ".join(missing[:20]),
            "major",
        )

    if not conclusion:
        add_repair(repair_plan, "core conclusion", "No recognizable core-conclusion section.", "major")
    if not evidence:
        add_repair(repair_plan, "evidence timeline", "No recognizable figure/table/formula section.", "major")
    if not related:
        add_repair(repair_plan, "related work", "No recognizable related-work comparison section.", "minor")
    if not limitation:
        add_repair(repair_plan, "limitations/discussion", "No recognizable limitations/discussion section.", "minor")

    evidence_body = evidence.get("body", "") if evidence else ""
    label_count = len(EVIDENCE_LABEL_RE.findall(evidence_body))
    if evidence and label_count < max(1, min(3, manifest_stats(manifest_path).get("required_items", 1))):
        add_repair(
            repair_plan,
            "evidence timeline",
            "Evidence section contains too few explicit Figure/Table/Equation labels.",
            "major",
        )
    if PLACEHOLDER_RE.search(text):
        add_repair(repair_plan, "whole note", "Placeholder or unresolved drafting text remains.", "major")
    if INTERNAL_RE.search(text):
        add_repair(repair_plan, "whole note", "Internal pipeline/audit wording leaked into final note.", "minor")
    if source_pack and not Path(source_pack).expanduser().is_file():
        add_repair(repair_plan, "source pack", f"Source pack not found: {source_pack}", "minor")
    if blueprint and not Path(blueprint).expanduser().is_file():
        add_repair(repair_plan, "blueprint", f"Blueprint not found: {blueprint}", "minor")

    status = determine_status(scores, repair_plan)
    return {
        "schema_version": 1,
        "note": str(note_path),
        "source_pack": source_pack or "",
        "evidence_manifest": manifest_path or "",
        "blueprint": blueprint or "",
        "status": status,
        "scores": scores,
        "repair_plan": repair_plan,
        "manifest_stats": manifest_stats(manifest_path),
        "summary": {
            "top_heading_count": len([row for row in rows if row["level"] <= 2]),
            "evidence_label_count": label_count,
            "placeholder_count": len(PLACEHOLDER_RE.findall(text)),
        },
    }


def markdown_report(result: dict[str, Any]) -> str:
    lines = [
        "# Note Quality Audit",
        "",
        f"Note: {result['note']}",
        f"Status: {result['status']}",
        "",
        "## Scores",
    ]
    for key, value in result["scores"].items():
        lines.append(f"- {key}: {value:.2f}")
    lines.append("")
    lines.append("## Repair Plan")
    if not result["repair_plan"]:
        lines.append("- <none>")
    for item in result["repair_plan"]:
        lines.append(f"- [{item['repair_level']}] {item['section']}: {item['problem']}")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    result = audit(
        Path(args.note).expanduser().resolve(),
        args.source_pack,
        args.evidence_manifest,
        args.blueprint,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(markdown_report(result))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
