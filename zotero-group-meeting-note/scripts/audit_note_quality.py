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
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
EVIDENCE_LABEL_RE = re.compile(
    r"(?:Figure|Fig\.?|Table|Equation|Eq\.?|Algorithm|Alg\.?|Objective|Loss|Score|"
    r"Constraint|Prompt|Proposition|Prop\.?|Case Study|Checklist|图|表|公式|方程|算法|命题)\s*[A-Za-z]?\d*",
    re.IGNORECASE,
)
LABEL_SCAN_RE = re.compile(
    r"(?P<kind>Figure|Fig\.?|Table|Equation|Eq\.?|Algorithm|Alg\.?|Objective|Loss|"
    r"Score|Constraint|Prompt|Proposition|Prop\.?|Case Study|Checklist|图|表|公式|方程|算法|命题)"
    r"\s*(?P<tail>\(?[A-Za-z]?\d+(?:\.\d+)?\)?"
    r"(?:\s*(?:[-–—~至到,，、/]|和|and)\s*\(?[A-Za-z]?\d+(?:\.\d+)?\)?){0,12})?",
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
FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
CODE_SPAN_RE = re.compile(r"`(?P<code>[^`\n]+)`")
PATHLIKE_CODE_RE = re.compile(
    r"^(?:[A-Za-z]:[\\/]|\\\\|\.{0,2}[\\/]|--|[A-Za-z0-9_.-]+\.(?:py|json|md|yaml|yml|txt|pdf|png|jpg|jpeg|zip)|assets[\\/])",
    re.IGNORECASE,
)
LATEX_COMMAND_RE = re.compile(
    r"\\(?:alpha|beta|gamma|delta|epsilon|lambda|mu|pi|phi|Phi|sigma|theta|"
    r"mathcal|mathbf|mathrm|operatorname|frac|sum|prod|bigsqcup|sqsubseteq|"
    r"subseteq|leq|geq|emptyset|infty)\b"
)
MATH_SYMBOL_RE = re.compile(r"[∑∏√∞≤≥≠≈∈∉⊂⊆⊑⊔⊗∅∧∨×·]|[α-ωΑ-Ω]")
MATH_SUBSCRIPT_RE = re.compile(
    r"^(?:[A-Za-z]|[A-Z][A-Za-z]{1,5}|Cap|Viol|Phi|Score|Loss|Objective|T|D|C)"
    r"(?:_[A-Za-z0-9{}]+|\^\{?[-A-Za-z0-9+]+\}?)(?:\([^)]*\))?$"
)
MATH_FUNCTION_RE = re.compile(
    r"^(?:Cap|Viol|req|ops|trans|lfp|rank|score|loss|Phi|D|C|T|T_eff)"
    r"(?:_[A-Za-z0-9{}]+)?\([^)]*\)$",
    re.IGNORECASE,
)
INLINE_MATH_RE = re.compile(r"(?<!\$)\$[^$\n]{1,240}\$(?!\$)")

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
        row["children"] = []
    # Build immediate parent-child relationships so nested sub-sections are not double-counted.
    stack: list[dict[str, Any]] = []
    for row in rows:
        while stack and stack[-1]["level"] >= row["level"]:
            stack.pop()
        if stack:
            stack[-1]["children"].append(row)
        stack.append(row)
    return rows


def section_body_with_children(row: dict[str, Any]) -> str:
    """Return a section's body including all child sub-sections."""
    body = row.get("body", "")
    for child in row.get("children", []):
        body += child.get("body", "")
    return body


def section_by_keywords(rows: list[dict[str, Any]], *keywords: str) -> dict[str, Any] | None:
    lowered = [keyword.lower() for keyword in keywords]
    # Prefer H2 matches over deeper levels
    best: dict[str, Any] | None = None
    for row in rows:
        title = str(row["title"]).lower()
        if any(keyword in title for keyword in lowered):
            if best is None or row["level"] < best["level"]:
                best = row
    return best


SECTION_ALIASES = {
    "conclusion": ["核心", "结论", "摘要", "conclusion", "takeaway"],
    "problem": ["问题", "背景", "定位", "动机", "研究定位", "problem", "background", "motivation"],
    "innovation": ["创新", "贡献", "主要贡献", "contribution", "innovation", "novelty"],
    "method": ["方法", "系统", "机制", "架构", "流程", "设计", "method", "system", "mechanism", "architecture", "pipeline"],
    "evidence": ["图", "表", "公式", "证据", "实验", "结果", "evidence", "figure", "table", "result"],
    "related": ["相关", "对比", "联系", "related", "comparison"],
    "limitation": ["局限", "讨论", "限制", "不足", "优点", "边界", "limitation", "discussion", "boundary"],
}


KIND_ALIASES = {
    "fig": "figure",
    "figure": "figure",
    "图": "figure",
    "table": "table",
    "表": "table",
    "equation": "equation",
    "eq": "equation",
    "公式": "equation",
    "方程": "equation",
    "algorithm": "algorithm",
    "alg": "algorithm",
    "算法": "algorithm",
    "objective": "objective",
    "loss": "loss",
    "score": "score",
    "constraint": "constraint",
    "prompt": "prompt",
    "case study": "case-study",
    "checklist": "checklist",
}


def normalize_kind(kind: str) -> str:
    cleaned = kind.lower().strip().rstrip(".")
    return KIND_ALIASES.get(cleaned, cleaned.replace(" ", "-"))


def normalize_label_number(value: str) -> str:
    cleaned = value.strip().strip("()")
    cleaned = re.sub(r"[\s.]+$", "", cleaned)
    return cleaned.lower()


def expand_label_tail(tail: str | None) -> list[str]:
    if not tail:
        return [""]
    cleaned = tail.strip()
    expanded: set[str] = set()
    for match in re.finditer(r"\b([A-Za-z]?)(\d+)\s*[-–—~至到]\s*([A-Za-z]?)(\d+)\b", cleaned):
        prefix_left, start_text, prefix_right, end_text = match.groups()
        start = int(start_text)
        end = int(end_text)
        prefix = prefix_left or prefix_right
        if start < end and end - start <= 50:
            for value in range(start, end + 1):
                expanded.add(f"{prefix}{value}".lower())
    stripped_ranges = re.sub(r"\b([A-Za-z]?)(\d+)\s*[-–—~至到]\s*([A-Za-z]?)(\d+)\b", " ", cleaned)
    for raw in re.findall(r"\b[A-Za-z]?\d+(?:\.\d+)?\b", stripped_ranges):
        expanded.add(normalize_label_number(raw))
    return sorted(expanded) if expanded else [""]


def canonical_label_ids(value: str) -> set[str]:
    ids: set[str] = set()
    for match in LABEL_SCAN_RE.finditer(value):
        kind = normalize_kind(match.group("kind"))
        for number in expand_label_tail(match.group("tail")):
            ids.add(f"{kind}:{number}" if number else kind)
    return ids


def labels_overlap(required_label: str, text_ids: set[str]) -> bool:
    required_ids = canonical_label_ids(required_label)
    if required_ids & text_ids:
        return True
    for label_id in required_ids:
        if ":" not in label_id and any(candidate.startswith(label_id + ":") for candidate in text_ids):
            return True
    return False


def append_gate(failed_gates: list[str], gate: str) -> None:
    if gate and gate not in failed_gates:
        failed_gates.append(gate)


def without_fenced_code(text: str) -> str:
    """Remove fenced code while preserving line offsets for diagnostics."""
    return FENCED_CODE_RE.sub(lambda match: "\n" * match.group(0).count("\n"), text)


def is_pathlike_or_code_identifier(value: str) -> bool:
    cleaned = value.strip()
    if cleaned.startswith("\\") and not cleaned.startswith("\\\\"):
        return False
    if PATHLIKE_CODE_RE.search(cleaned):
        return True
    if "/" in cleaned or "://" in cleaned:
        return True
    if re.search(r"\b(?:json|yaml|toml|python|powershell|cmd|bash|git|pytest)\b", cleaned, re.IGNORECASE):
        return True
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+", cleaned):
        return True
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{5,}", cleaned) and not re.search(r"[(){}^\\]", cleaned):
        return True
    return False


def math_code_reason(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or is_pathlike_or_code_identifier(cleaned):
        return ""
    if LATEX_COMMAND_RE.search(cleaned):
        return "LaTeX command in code span should be inline/display math"
    if MATH_SYMBOL_RE.search(cleaned):
        return "math relation/operator symbol in code span should be math"
    if re.search(r"(?:_\{[^}]+\}|\^\{[^}]+\})", cleaned):
        return "subscript/superscript expression in code span should be math"
    if MATH_SUBSCRIPT_RE.search(cleaned):
        return "math variable with subscript/superscript is formatted as code"
    if MATH_FUNCTION_RE.search(cleaned):
        return "math function-like symbol is formatted as code"
    if re.search(r"\\[A-Za-z]+", cleaned):
        return "backslash math command in code span should be math"
    return ""


def math_format_issues(text: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    searchable = without_fenced_code(text)
    for match in CODE_SPAN_RE.finditer(searchable):
        code = match.group("code")
        reason = math_code_reason(code)
        if not reason:
            continue
        issues.append(
            {
                "line": searchable.count("\n", 0, match.start()) + 1,
                "code": code,
                "reason": reason,
                "suggestion": f"${code}$",
            }
        )
    return issues


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
        labels = canonical_label_ids(text)
        return (1.0 if labels else 0.45), []
    path = Path(manifest_path).expanduser().resolve()
    if not path.is_file():
        return 0.0, [f"Evidence manifest not found: {path}"]
    items = iter_manifest_items(read_json(path))
    required = [item for item in items if item.get("required_in_final")]
    if not required:
        return 0.7, []
    text_ids = canonical_label_ids(text)
    missing = [
        str(item.get("label", ""))
        for item in required
        if item.get("label") and not labels_overlap(str(item.get("label")), text_ids)
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


SCORE_REPAIR_RULES: dict[str, tuple[str, str, int]] = {
    "core_conclusion": (
        "core conclusion",
        "Core conclusion is too thin; add the paper's claim, method idea, key evidence, boundary, and discussion hook.",
        220,
    ),
    "problem_positioning": (
        "problem positioning",
        "Problem/background section is too thin; explain the old route, the bottleneck, and the exact layer this paper changes.",
        260,
    ),
    "innovation_analysis": (
        "innovation analysis",
        "Innovation section is too thin; connect each claimed contribution to prior limitations, supporting evidence, and validity boundary.",
        300,
    ),
    "method_explanation": (
        "method/system mechanism",
        "Method or system section is too thin; explain input/output, pipeline, key modules, design rationale, and what carries the contribution.",
        320,
    ),
    "evidence_depth": (
        "evidence timeline",
        "Figure/table/formula section is too thin; explain what each key item shows, what claim it supports, and what it cannot prove.",
        420,
    ),
    "related_work": (
        "related work",
        "Related-work section is too thin; compare research routes rather than listing citations.",
        220,
    ),
    "limitations_discussion": (
        "limitations/discussion",
        "Limitations/discussion section is too thin; name concrete data, model, experiment, deployment, reproduction, or threat boundaries.",
        260,
    ),
    "terminology": (
        "terminology",
        "Key technical English terms need stable inline Chinese explanations on first important mention.",
        0,
    ),
    "blueprint_structure": (
        "blueprint structure",
        "Top-level structure is incomplete for the blueprint contract.",
        0,
    ),
}


FORMULA_TYPES = {"Equation", "Loss", "Objective", "Score", "Constraint"}
FORMULA_DETAIL_RE = re.compile(
    r"(变量|符号|含义|目标|优化|损失|目标函数|为什么|直觉|机制|消融|边界|限制|"
    r"Table|Figure|表|图|objective|loss|variable|intuition|ablation|boundary|"
    r"ranking|score|gradient|positive|negative)",
    re.IGNORECASE,
)
TEMPLATE_MARKER_RE = re.compile(
    r"\*\*(图意概述|图中关键元素|图中元素说明|作者想证明什么|我对这张图的解读|"
    r"表在比较什么|主要结果|结果意味着什么|需要警惕的地方|我对结论强度的判断|"
    r"公式所在位置|符号解释|公式本质在做什么|为什么这样设计|和结果的关系|"
    r"可能的问题或边界|证据边界|组会讲法|补充什么|是否影响主结论)\*\*"
)
NARRATIVE_DETAIL_RE = re.compile(
    r"(支撑|证明|说明|对应|结论|创新|机制|流程|模块|边界|限制|风险|代价|"
    r"基线|指标|消融|泛化|公平|失败|提升|对照|假设|威胁|攻击|防御|"
    r"claim|mechanism|baseline|metric|ablation|boundary|limitation|trade[- ]off|evidence)",
    re.IGNORECASE,
)
TABLE_DETAIL_RE = re.compile(
    r"(基线|baseline|指标|metric|数据集|setting|对比|比较|提升|下降|代价|公平|"
    r"显著|结果|结论|鲁棒|泛化|消融|ablation|dataset|result)",
    re.IGNORECASE,
)
FIGURE_DETAIL_RE = re.compile(
    r"(流程|模块|元素|架构|机制|输入|输出|支撑|证明|说明|结论|创新|边界|不能|风险|"
    r"pipeline|module|architecture|mechanism|claim|boundary)",
    re.IGNORECASE,
)


def load_manifest_items(path_text: str | None) -> list[dict[str, Any]]:
    if not path_text:
        return []
    path = Path(path_text).expanduser().resolve()
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig", errors="ignore"))
    if "items" in data:
        return list(data.get("items", []))
    return list(data.get("main_items", [])) + list(data.get("post_reference_items", []))


def label_text_pattern(label: str) -> re.Pattern[str]:
    escaped = re.escape(label).replace(r"\ ", r"\s+")
    return re.compile(rf"{escaped}(?![A-Za-z0-9_.-])", re.IGNORECASE)


def line_bounds_for_position(text: str, position: int) -> tuple[int, int, str]:
    start = text.rfind("\n", 0, position) + 1
    end = text.find("\n", position)
    if end == -1:
        end = len(text)
    return start, end, text[start:end]


def markdown_heading_level(line: str) -> int:
    match = re.match(r"^\s{0,3}(#{1,6})\s+", line)
    return len(match.group(1)) if match else 0


def next_section_boundary(text: str, start: int, current_level: int) -> int:
    for match in HEADING_RE.finditer(text, start):
        if len(match.group(1)) <= current_level:
            return match.start()
    return len(text)


def local_window_for_label(
    text: str,
    label: str,
    item: dict[str, Any] | None = None,
    size: int = 1400,
) -> tuple[str, dict[str, Any]]:
    pattern = label_text_pattern(label)
    candidates: list[dict[str, Any]] = []
    item = item or {}
    item_region = str(item.get("region") or item.get("paper_region") or "").lower()
    final_section = str(item.get("final_section") or "").lower()
    prefer_supplementary = item_region in {"appendix", "post_reference", "supplement"} or bool(
        re.search(r"appendix|supplement|闄勫綍|琛ュ厖", final_section, re.IGNORECASE)
    )
    for match in pattern.finditer(text):
        line_start, line_end, line = line_bounds_for_position(text, match.start())
        level = markdown_heading_level(line)
        stripped = line.strip()
        heading_title = re.sub(r"^\s{0,3}#{1,6}\s+", "", stripped)
        is_supplementary = bool(
            re.search(r"\bSupplementary\b|补充|Appendix|附录", heading_title, re.IGNORECASE)
        )
        heading_starts_with_label = bool(level and pattern.match(heading_title))
        score = 10
        if heading_starts_with_label and not is_supplementary:
            score = 160 - level
        elif level:
            score = 120 - level
        elif re.match(r"^\s*(?:[-*+]\s*)?(?:\*\*)?\s*(?:Figure|Fig\.?|Table|Equation|Eq\.?|Algorithm|Objective|Loss|Score|Constraint|Prompt|Case Study|图|表|公式|方程)", stripped, re.IGNORECASE):
            score = 85
        elif IMAGE_RE.search(line):
            score = 45
        if prefer_supplementary and is_supplementary:
            score += 60
        elif prefer_supplementary and not is_supplementary:
            score -= 25
        elif is_supplementary:
            score -= 50
        candidates.append(
            {
                "match": match,
                "line_start": line_start,
                "line_end": line_end,
                "line": line,
                "level": level,
                "score": score,
                "is_supplementary": is_supplementary,
            }
        )
    if not candidates:
        return "", {
            "label": label,
            "match_count": 0,
            "item_region": item_region,
            "final_section": final_section,
        }
    candidates.sort(key=lambda item: (-int(item["score"]), int(item["match"].start())))
    best = candidates[0]
    match = best["match"]
    start = max(0, int(best["line_start"]) - 80)
    if best["level"]:
        end = next_section_boundary(text, int(best["line_end"]), int(best["level"]))
    else:
        end = min(len(text), match.end() + size)
    return text[start:end], {
        "label": label,
        "match_count": len(candidates),
        "selected_line": text.count("\n", 0, int(best["line_start"])) + 1,
        "selected_score": int(best["score"]),
        "selected_is_heading": bool(best["level"]),
        "selected_is_supplementary": bool(best["is_supplementary"]),
        "item_region": item_region,
        "final_section": final_section,
    }


def local_text_for_label(text: str, label: str, size: int = 1400) -> str:
    window, _ = local_window_for_label(text, label, size=size)
    return window


def compact_excerpt(value: str, limit: int = 900) -> str:
    return re.sub(r"\s+", " ", value).strip()[:limit]


def source_context_for_item(item: dict[str, Any]) -> str:
    candidates = [
        str(item.get("source_text", "")),
        str(item.get("caption_or_nearby_text", "")),
    ]
    for block in item.get("source_blocks", []) or []:
        if isinstance(block, dict):
            candidates.append(str(block.get("text", "")))
    return compact_excerpt("\n".join(part for part in candidates if part), 1200)


def item_label(item: dict[str, Any]) -> str:
    return str(item.get("display_label") or item.get("label") or item.get("item_key") or "")


def formula_missing_slots(window: str) -> list[str]:
    slots: list[str] = []
    has_latex_or_image = bool(
        re.search(r"!\[[^\]]*\]\([^)]+\)|\$\$|\\[A-Za-z]+", window)
        or INLINE_MATH_RE.search(window)
    )
    if not has_latex_or_image:
        slots.append("formula_visual_or_latex")
    if not re.search(r"(符号|变量|其中|表示|记为|denote|where|variable|symbol)", window, re.IGNORECASE):
        slots.append("symbols")
    if not re.search(r"(目标|约束|优化|最小化|最大化|loss|objective|constraint|optimi|minimi|maximi)", window, re.IGNORECASE):
        slots.append("objective_or_constraint")
    if not re.search(r"(方法|模块|阶段|训练|推理|检索|排序|pipeline|method|module|stage|training|inference|retrieval|ranking)", window, re.IGNORECASE):
        slots.append("method_position")
    if not re.search(r"(实验|结果|表|图|提升|指标|消融|结论|claim|result|table|figure|metric|ablation|performance)", window, re.IGNORECASE):
        slots.append("claim_or_result_connection")
    if not re.search(r"(边界|局限|假设|不能|风险|代价|只|但|limitation|boundary|assumption|risk|cost|however|only)", window, re.IGNORECASE):
        slots.append("failure_boundary")
    if len(re.sub(r"\s+", "", window)) < 260:
        slots.append("depth_budget")
    return slots


def narrative_missing_slots(window: str, item: dict[str, Any]) -> list[str]:
    slots: list[str] = []
    normalized = normalize_kind(str(item.get("type", "")))
    if not re.search(r"(展示|给出|统计|比较|说明|show|illustrate|report|compare|present)", window, re.IGNORECASE):
        slots.append("what_it_is")
    if normalized == "table" and not re.search(r"(列|行|指标|数据集|设置|基线|metric|column|row|baseline|setting|dataset)", window, re.IGNORECASE):
        slots.append("setting_or_columns")
    if normalized == "figure" and not re.search(r"(流程|模块|面板|架构|机制|panel|pipeline|module|architecture|mechanism)", window, re.IGNORECASE):
        slots.append("mechanism_or_panels")
    if not re.search(r"(支撑|证明|对应|说明|反映|创新|贡献|结论|claim|support|prove|evidence|conclusion|contribution)", window, re.IGNORECASE):
        slots.append("claim_supported")
    if not re.search(r"(边界|局限|不能|风险|代价|只|但|however|only|limitation|boundary|risk|cost)", window, re.IGNORECASE):
        slots.append("result_boundary")
    if not re.search(r"(组会|讲法|一句话|可以这样讲|takeaway|talk)", window, re.IGNORECASE):
        slots.append("meeting_talk_line")
    return slots


def failed_item(
    *,
    gate: str,
    item: dict[str, Any],
    repair_level: str,
    missing_slots: list[str],
    current_excerpt: str,
    required_action: str,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    label = item_label(item)
    return {
        "gate": gate,
        "item_key": item.get("item_key", ""),
        "display_label": label,
        "item_type": item.get("type", item.get("item_type", "")),
        "repair_level": repair_level,
        "missing_slots": missing_slots,
        "current_excerpt": compact_excerpt(current_excerpt),
        "source_context": source_context_for_item(item),
        "required_action": required_action,
        "repair_hint": item.get("repair_hint", ""),
        "diagnostics": diagnostics or {},
    }


def formula_items_requiring_depth(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        item_type = str(item.get("type", ""))
        if item_type not in FORMULA_TYPES:
            continue
        if item.get("required_in_final") or item.get("core_level") == "core_candidate":
            result.append(item)
            continue
        if item.get("asset_match_status") in {"orphan_formula_matched", "orphan_formula_candidate"}:
            result.append(item)
            continue
        if item.get("match_confidence") == "high" and item.get("asset_paths"):
            result.append(item)
    return result


def formula_depth_failures(text: str, manifest_path: str | None) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for item in formula_items_requiring_depth(load_manifest_items(manifest_path)):
        label = item_label(item)
        if not label:
            continue
        window, label_lookup = local_window_for_label(text, label, item)
        if not window:
            failures.append(
                failed_item(
                    gate="formula_depth",
                    item=item,
                    repair_level="major",
                    missing_slots=["presence"],
                    current_excerpt="",
                    required_action=f"Add the missing {label} entry to the evidence timeline and explain it from the source context.",
                    diagnostics={"label_lookup": label_lookup},
                )
            )
            continue
        compact_len = len(re.sub(r"\s+", "", window))
        detail_hits = len(FORMULA_DETAIL_RE.findall(window))
        has_latex_or_image = bool(
            re.search(r"!\[[^\]]*\]\([^)]+\)|\$\$|\\[A-Za-z]+", window)
            or INLINE_MATH_RE.search(window)
        )
        missing_slots = formula_missing_slots(window)
        if compact_len < 260 or detail_hits < 3 or not has_latex_or_image:
            failures.append(
                failed_item(
                    gate="formula_depth",
                    item=item,
                    repair_level="major",
                    missing_slots=missing_slots,
                    current_excerpt=window,
                    required_action=(
                        f"Rewrite only the {label} formula entry with LaTeX/image, symbols, "
                        "objective or constraint intuition, method position, result/claim connection, and boundary."
                    ),
                    diagnostics={
                        "label_lookup": label_lookup,
                        "compact_len": compact_len,
                        "minimum_len": 260,
                        "detail_hits": detail_hits,
                        "minimum_hits": 3,
                        "has_latex_or_image": has_latex_or_image,
                        "detail_gate": "formula_depth",
                    },
                )
            )
    return failures


def evidence_items_requiring_narrative(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        item_type = str(item.get("type", ""))
        normalized = normalize_kind(item_type)
        if normalized in {"equation", "loss", "objective", "score", "constraint"}:
            continue
        if normalized not in {"figure", "table", "algorithm", "prompt", "case-study", "checklist"}:
            continue
        if item.get("required_in_final") or item.get("core_level") == "core_candidate":
            result.append(item)
            continue
        if item.get("match_confidence") == "high" and item.get("asset_paths"):
            result.append(item)
    return result


def narrative_requirements_for_item(item: dict[str, Any]) -> tuple[int, re.Pattern[str], int]:
    normalized = normalize_kind(str(item.get("type", "")))
    if normalized == "table":
        return 230, TABLE_DETAIL_RE, 3
    if normalized == "figure":
        return 220, FIGURE_DETAIL_RE, 3
    return 180, NARRATIVE_DETAIL_RE, 2


def evidence_narrative_failures(text: str, manifest_path: str | None) -> list[dict[str, Any]]:
    if not manifest_path:
        return []
    failures: list[dict[str, Any]] = []
    for item in evidence_items_requiring_narrative(load_manifest_items(manifest_path)):
        label = item_label(item)
        if not label:
            continue
        window, label_lookup = local_window_for_label(text, label, item)
        if not window:
            continue
        minimum_len, detail_re, minimum_hits = narrative_requirements_for_item(item)
        compact_len = len(re.sub(r"\s+", "", re.sub(r"!\[[^\]]*\]\([^)]+\)", "", window)))
        detail_hits = len(detail_re.findall(window))
        missing_slots = narrative_missing_slots(window, item)
        if compact_len < minimum_len or detail_hits < minimum_hits:
            failures.append(
                failed_item(
                    gate="evidence_narrative",
                    item=item,
                    repair_level="major",
                    missing_slots=missing_slots,
                    current_excerpt=window,
                    required_action=(
                        f"Rewrite only the {label} evidence entry as an item-specific narrative with "
                        "mechanism/metric interpretation, claim support, result boundary, and a meeting talk line."
                    ),
                    diagnostics={
                        "label_lookup": label_lookup,
                        "compact_len": compact_len,
                        "minimum_len": minimum_len,
                        "detail_hits": detail_hits,
                        "minimum_hits": minimum_hits,
                        "detail_gate": "evidence_narrative",
                    },
                )
            )
    return failures


def template_repetition_problem(evidence_body: str, label_count: int) -> bool:
    if label_count < 6:
        return False
    marker_count = len(TEMPLATE_MARKER_RE.findall(evidence_body))
    compact_len = len(re.sub(r"\s+", "", evidence_body))
    avg_per_label = compact_len / max(1, label_count)
    detail_hits = len(NARRATIVE_DETAIL_RE.findall(evidence_body))
    if marker_count >= max(18, label_count * 4) and avg_per_label < 520:
        return True
    return marker_count >= max(12, label_count * 3) and detail_hits < label_count * 3


def add_score_repairs(scores: dict[str, float], repair_plan: list[dict[str, str]]) -> list[str]:
    failed_gates: list[str] = []
    existing = {(item.get("section", ""), item.get("problem", "")) for item in repair_plan}
    for key, score in scores.items():
        if key == "evidence_coverage":
            continue
        if score >= 0.7:
            continue
        rule = SCORE_REPAIR_RULES.get(key)
        if not rule:
            continue
        section, problem, minimum = rule
        level = "major" if score < 0.45 or key in {"blueprint_structure"} else "minor"
        if minimum:
            problem = f"{problem} Current score {score:.2f}; target minimum content budget is about {minimum} compact characters."
        else:
            problem = f"{problem} Current score {score:.2f}."
        if (section, problem) not in existing:
            add_repair(repair_plan, section, problem, level)
        failed_gates.append(key)
    return failed_gates


def repair_scope_for(
    failed_items: list[dict[str, Any]],
    repair_plan: list[dict[str, str]],
) -> str:
    if any(item.get("repair_level") == "regeneration" for item in repair_plan):
        return "regeneration"
    if any(item.get("repair_level") == "regeneration" for item in failed_items):
        return "regeneration"
    gates = {str(item.get("gate", "")) for item in failed_items}
    if failed_items and len(failed_items) <= 3 and gates <= {"formula_depth", "evidence_narrative"}:
        return "item_patch"
    if failed_items:
        return "section_patch"
    if len(repair_plan) <= 2:
        return "item_patch"
    return "section_patch"


def audit(note_path: Path, source_pack: str | None, manifest_path: str | None, blueprint: str | None) -> dict[str, Any]:
    text = note_path.read_text(encoding="utf-8", errors="ignore")
    rows = sections(text)
    repair_plan: list[dict[str, str]] = []

    conclusion = section_by_keywords(rows, *SECTION_ALIASES["conclusion"])
    problem = section_by_keywords(rows, *SECTION_ALIASES["problem"])
    innovation = section_by_keywords(rows, *SECTION_ALIASES["innovation"])
    method = section_by_keywords(rows, *SECTION_ALIASES["method"])
    evidence = section_by_keywords(rows, *SECTION_ALIASES["evidence"])
    related = section_by_keywords(rows, *SECTION_ALIASES["related"])
    limitation = section_by_keywords(rows, *SECTION_ALIASES["limitation"])

    scores = {
        "blueprint_structure": 1.0 if len([row for row in rows if row["level"] <= 2]) >= 6 else 0.35,
        "core_conclusion": score_length(section_body_with_children(conclusion) if conclusion else "", 220),
        "problem_positioning": score_length(section_body_with_children(problem) if problem else "", 260),
        "innovation_analysis": score_length(section_body_with_children(innovation) if innovation else "", 300),
        "method_explanation": score_length(section_body_with_children(method) if method else "", 320),
        "evidence_depth": score_length(section_body_with_children(evidence) if evidence else "", 420),
        "related_work": score_length(section_body_with_children(related) if related else "", 220),
        "limitations_discussion": score_length(section_body_with_children(limitation) if limitation else "", 260),
        "terminology": 0.75 if re.search(r"[A-Za-z][A-Za-z -]{3,}\s*[（(]", text) else 0.5,
    }

    coverage, missing = coverage_score(text, manifest_path)
    scores["evidence_coverage"] = coverage
    failed_gates: list[str] = []
    failed_items: list[dict[str, Any]] = []
    if missing:
        append_gate(failed_gates, "evidence_coverage")
        for label in missing[:20]:
            failed_items.append(
                {
                    "gate": "evidence_coverage",
                    "item_key": "",
                    "display_label": label,
                    "item_type": "",
                    "repair_level": "major",
                    "missing_slots": ["presence"],
                    "current_excerpt": "",
                    "source_context": "",
                    "required_action": f"Add required evidence item {label} to the correct final section in source order.",
                    "repair_hint": "Use the evidence manifest and source pack to insert the missing item, not a generic summary.",
                }
            )
        add_repair(
            repair_plan,
            "evidence coverage",
            "Missing required evidence labels: " + ", ".join(missing[:20]),
            "major",
        )

    if not conclusion:
        append_gate(failed_gates, "blueprint_structure")
        add_repair(repair_plan, "core conclusion", "No recognizable core-conclusion section.", "major")
    if not evidence:
        append_gate(failed_gates, "blueprint_structure")
        add_repair(repair_plan, "evidence timeline", "No recognizable figure/table/formula section.", "major")
    if not related:
        append_gate(failed_gates, "blueprint_structure")
        add_repair(repair_plan, "related work", "No recognizable related-work comparison section.", "minor")
    if not limitation:
        append_gate(failed_gates, "blueprint_structure")
        add_repair(repair_plan, "limitations/discussion", "No recognizable limitations/discussion section.", "minor")

    evidence_body = section_body_with_children(evidence) if evidence else ""
    label_count = len(EVIDENCE_LABEL_RE.findall(evidence_body))
    if evidence and label_count < max(1, min(3, manifest_stats(manifest_path).get("required_items", 1))):
        append_gate(failed_gates, "evidence_depth")
        add_repair(
            repair_plan,
            "evidence timeline",
            "Evidence section contains too few explicit Figure/Table/Equation labels.",
            "major",
        )
    math_issues = math_format_issues(text)
    if math_issues:
        append_gate(failed_gates, "math_format")
        examples = "; ".join(
            f"line {issue['line']}: `{issue['code']}` -> {issue['suggestion']}"
            for issue in math_issues[:10]
        )
        add_repair(
            repair_plan,
            "math formatting",
            "Math-like code spans must be LaTeX math, while backticks stay reserved for code/path/API names: "
            + examples
            + ("; ..." if len(math_issues) > 10 else ""),
            "minor",
        )
    formula_failures = formula_depth_failures(text, manifest_path)
    if formula_failures:
        append_gate(failed_gates, "formula_depth")
        failed_items.extend(formula_failures)
        add_repair(
            repair_plan,
            "formula/equation evidence",
            "Formula explanations are missing or too shallow: "
            + "; ".join(
                f"{item.get('display_label', '')}: {','.join(item.get('missing_slots', []))}"
                for item in formula_failures[:8]
            )
            + ("; ..." if len(formula_failures) > 8 else ""),
            "major",
        )
    narrative_failures = evidence_narrative_failures(text, manifest_path)
    if narrative_failures:
        append_gate(failed_gates, "evidence_narrative")
        failed_items.extend(narrative_failures)
        add_repair(
            repair_plan,
            "evidence timeline",
            "Core evidence explanations are too shallow or caption-like: "
            + "; ".join(
                f"{item.get('display_label', '')}: {','.join(item.get('missing_slots', []))}"
                for item in narrative_failures[:8]
            )
            + ("; ..." if len(narrative_failures) > 8 else ""),
            "major",
        )
    if evidence and template_repetition_problem(evidence_body, label_count):
        append_gate(failed_gates, "evidence_depth")
        add_repair(
            repair_plan,
            "evidence timeline",
            "Evidence entries appear overly template-driven; rewrite core figure/table/formula items with item-specific mechanisms, metric interpretation, evidence limits, and cross-links to claims.",
            "major",
        )
    if PLACEHOLDER_RE.search(text):
        append_gate(failed_gates, "draft_artifacts")
        add_repair(repair_plan, "whole note", "Placeholder or unresolved drafting text remains.", "major")
    if INTERNAL_RE.search(text):
        append_gate(failed_gates, "draft_artifacts")
        add_repair(repair_plan, "whole note", "Internal pipeline/audit wording leaked into final note.", "minor")
    if source_pack and not Path(source_pack).expanduser().is_file():
        add_repair(repair_plan, "source pack", f"Source pack not found: {source_pack}", "minor")
    if blueprint and not Path(blueprint).expanduser().is_file():
        add_repair(repair_plan, "blueprint", f"Blueprint not found: {blueprint}", "minor")

    for gate in add_score_repairs(scores, repair_plan):
        append_gate(failed_gates, gate)

    status = determine_status(scores, repair_plan)
    repair_scope = repair_scope_for(failed_items, repair_plan)
    return {
        "schema_version": 2,
        "note": str(note_path),
        "source_pack": source_pack or "",
        "evidence_manifest": manifest_path or "",
        "blueprint": blueprint or "",
        "status": status,
        "scores": scores,
        "failed_gates": failed_gates,
        "failed_items": failed_items,
        "repair_scope": repair_scope,
        "repair_plan": repair_plan,
        "manifest_stats": manifest_stats(manifest_path),
        "summary": {
            "top_heading_count": len([row for row in rows if row["level"] <= 2]),
            "evidence_label_count": label_count,
            "placeholder_count": len(PLACEHOLDER_RE.findall(text)),
            "math_format_issue_count": len(math_issues),
            "evidence_narrative_failure_count": len(narrative_failures),
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
