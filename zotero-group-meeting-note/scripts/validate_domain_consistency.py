#!/usr/bin/env python3
"""Validate domain consistency for agent-skill group-meeting notes."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Domain detection signals (ordered by priority)
DOMAIN_SIGNALS: dict[str, list[str]] = {
    "agent-skill": [
        r"\bskill\b", r"\bSKILL\.md\b", r"\bskill library\b", r"\bskill ecosystem\b",
        r"\bskill retrieval\b", r"\bskill composition\b", r"\bskill graph\b",
        r"\bskill compilation\b", r"\bskill distillation\b", r"\bskill evolution\b",
        r"\bskill governance\b", r"\bprogressive disclosure\b",
        r"\bSkillRet\b", r"\bSkCC\b", r"\bSkillOps\b", r"\bClawTrace\b",
        r"\bOpenSkillEval\b", r"\bGraph-of-Skills\b",
    ],
    "security": [
        r"\bsecurity\b", r"\battack\b", r"\badversarial\b", r"\bprivacy\b",
        r"\btrust\b", r"\bvulnerability\b", r"\bthreat model\b", r"\bmalicious\b",
    ],
    "systems": [
        r"\bsystem\b", r"\barchitecture\b", r"\bdeployment\b", r"\bdistributed\b",
        r"\binfrastructure\b", r"\bcloud\b",
    ],
    "benchmark": [
        r"\bbenchmark\b", r"\bdataset\b", r"\bevaluation\b", r"\bmetric\b",
        r"\btest suite\b",
    ],
}

PAPER_TYPE_SIGNALS: dict[str, list[str]] = {
    "method": [r"\bpropose\b", r"\bnovel\b", r"\bapproach\b", r"\bour method\b", r"\bwe present\b"],
    "system": [r"\bsystem\b", r"\barchitecture\b", r"\bpipeline\b", r"\bimplementation\b",
               r"\bcompiler\b", r"\bplatform\b"],
    "benchmark": [r"\bbenchmark\b", r"\bdataset\b", r"\btask suite\b", r"\bevaluation protocol\b"],
    "survey": [r"\bsurvey\b", r"\bSoK\b", r"\bsystematic review\b", r"\btaxonomy\b",
               r"\bcomprehensive\b.*\breview\b"],
    "analysis": [r"\banalysis\b", r"\bempirical\b", r"\bobservation\b", r"\bstudy\b",
                 r"\bcharacterization\b"],
    "theory": [r"\btheorem\b", r"\bproof\b", r"\blemma\b", r"\bproposition\b", r"\bcorollary\b"],
}

# Agent-skill specific check dimensions
SKILL_CHECKS = {
    "skill_lifecycle_identified": {
        "description": "是否明确了 skill 生命周期阶段（acquisition/retrieval/composition/execution/evolution/governance）",
        "critical": True,
    },
    "skill_object_defined": {
        "description": "是否定义了 skill 的具体形态（SKILL.md / structured package / prompt snippet / tool library / latent adapter）",
        "critical": True,
    },
    "paper_type_correct": {
        "description": "论文类型分类是否正确（method/system/benchmark/survey/analysis）",
        "critical": True,
    },
    "innovation_scoped": {
        "description": "创新点是否正确定位到具体的 lifecycle 阶段",
        "critical": False,
    },
    "evidence_mapped": {
        "description": "主要主张是否绑定了合适的证据类型（pass rate/trace analysis/ablation/retrieval metrics/human audit）",
        "critical": False,
    },
    "security_considered": {
        "description": "如果论文涉及安全/权限/治理，是否讨论了威胁模型或安全边界",
        "critical": False,
    },
    "framework_dependency_analyzed": {
        "description": "是否分析了方法对特定 Agent 框架的依赖程度",
        "critical": False,
    },
    "boundary_conditions": {
        "description": "是否讨论了 skill 边界条件（什么被加载/什么留在文件/什么转化为权重）",
        "critical": False,
    },
}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate domain consistency for group-meeting notes."
    )
    parser.add_argument("--note", required=True, help="Markdown note path.")
    parser.add_argument("--source-pack", help="Optional source_pack.json path (for full.md reading).")
    parser.add_argument("--domain-template", help="Optional domain-*.md reference path.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig", errors="ignore"))


def detect_domain(text: str) -> tuple[str, float]:
    """Detect the most likely domain from paper text."""
    scores: dict[str, int] = {}
    for domain, patterns in DOMAIN_SIGNALS.items():
        count = sum(len(re.findall(pattern, text, re.IGNORECASE)) for pattern in patterns)
        if count > 0:
            scores[domain] = count
    if not scores:
        return "unknown", 0.0
    best = max(scores, key=lambda k: scores[k])
    total = sum(scores.values())
    confidence = scores[best] / total if total > 0 else 0.0
    return best, min(confidence, 1.0)


def detect_paper_type(text: str) -> tuple[str, float]:
    """Detect the paper type from text content."""
    scores: dict[str, int] = {}
    for ptype, patterns in PAPER_TYPE_SIGNALS.items():
        count = sum(len(re.findall(pattern, text, re.IGNORECASE)) for pattern in patterns)
        if count > 0:
            scores[ptype] = count
    if not scores:
        return "method", 0.3  # default assumption
    best = max(scores, key=lambda k: scores[k])
    total = sum(scores.values())
    confidence = scores[best] / total if total > 0 else 0.0
    return best, min(confidence, 1.0)


def check_skill_note(text: str) -> dict[str, Any]:
    """Run agent-skill specific checks on the note."""
    checks: dict[str, dict[str, Any]] = {}

    # Check 1: skill lifecycle identified
    lifecycle_terms = [
        r"\bacquisition\b", r"\bsynthesis\b", r"\bgeneration\b",
        r"\bretrieval\b", r"\bselection\b", r"\brouting\b",
        r"\bcomposition\b", r"\bgraph\b",
        r"\bexecution\b", r"\bloading\b",
        r"\bevolution\b", r"\boptimization\b", r"\bdistillation\b",
        r"\bgovernance\b", r"\bmaintenance\b", r"\baudit\b",
        r"\binternalization\b", r"\blatent\b",
        r"\b安全\b", r"\b治理\b",
        r"\b编译\b", r"\bcompil",
        r"\b生命周期\b", r"\blifecycle\b",
        r"\b阶段\b", r"\bstage\b", r"\bphase\b",
    ]
    lifecycle_count = sum(len(re.findall(term, text, re.IGNORECASE)) for term in lifecycle_terms)
    checks["skill_lifecycle_identified"] = {
        "pass": lifecycle_count >= 3,
        "evidence": f"在笔记中发现 {lifecycle_count} 个生命周期相关术语引用",
    }

    # Check 2: skill object defined
    object_terms = [
        r"\bSKILL\.md\b", r"\bskill package\b", r"\bskill artifact\b",
        r"\bprompt snippet\b", r"\btool library\b", r"\bfunction library\b",
        r"\bgraph node\b", r"\blatent adapter\b", r"\bpolicy module\b",
        r"\bskill 定义\b", r"\bskill 形态\b", r"\bskill 对象\b",
        r"\b中间表示\b", r"\bintermediate representation\b", r"\bIR\b",
    ]
    object_count = sum(len(re.findall(term, text, re.IGNORECASE)) for term in object_terms)
    checks["skill_object_defined"] = {
        "pass": object_count >= 2,
        "evidence": f"在笔记中发现 {object_count} 个 skill 对象相关引用",
    }

    # Check 3: paper type correct
    type_terms = [
        r"\b(?:method|system|benchmark|survey|analysis|theory)\b",
        r"\b(?:方法|系统|基准|综述|分析|理论)\b",
    ]
    type_count = sum(len(re.findall(term, text, re.IGNORECASE)) for term in type_terms)
    checks["paper_type_correct"] = {
        "pass": type_count >= 1,
        "evidence": f"在笔记中发现 {type_count} 个论文类型相关引用",
    }

    # Check 4: innovation scoped to lifecycle stage
    innovation_section = ""
    for match in re.finditer(
        r"(?:^#{2,3}\s*(?:三|四|[34]\.|[IVX]+\.)\s*(?:创新|方法|机制|系统|设计).*$)",
        text, re.MULTILINE
    ):
        start = match.start()
        next_h2 = re.search(r"^#{2}\s", text[start + 1:], re.MULTILINE)
        end = start + 1 + next_h2.start() if next_h2 else len(text)
        innovation_section += text[start:end]

    checks["innovation_scoped"] = {
        "pass": len(innovation_section) > 100,
        "evidence": f"创新/方法章节内容长度: {len(innovation_section)} 字符",
    }

    # Check 5: evidence mapped
    evidence_terms = [
        r"\bpass rate\b", r"\breward\b", r"\bablation\b", r"\bstatistical\b",
        r"\btrace\b", r"\bcoverage\b", r"\bMRR\b", r"\bRecall@K\b",
        r"\bhuman.audit\b", r"\b实证\b", r"\b实验\b", r"\b验证\b",
        r"\bTable \d+\b", r"\bFigure \d+\b", r"\b图\s*\d+\b", r"\b表\s*\d+\b",
    ]
    evidence_count = sum(len(re.findall(term, text, re.IGNORECASE)) for term in evidence_terms)
    checks["evidence_mapped"] = {
        "pass": evidence_count >= 5,
        "evidence": f"在笔记中发现 {evidence_count} 个证据绑定相关引用",
    }

    # Check 6: security considered (when applicable)
    security_terms = [
        r"\bsecurity\b", r"\bsafety\b", r"\bthreat\b", r"\battack\b",
        r"\bmalicious\b", r"\bvulnerability\b", r"\binjection\b",
        r"\b安全\b", r"\b威胁\b", r"\b攻击\b", r"\b漏洞\b", r"\b注入\b",
    ]
    security_count = sum(len(re.findall(term, text, re.IGNORECASE)) for term in security_terms)
    checks["security_considered"] = {
        "pass": security_count >= 1 if "security" in text.lower() or "安全" in text else True,
        "evidence": f"在笔记中发现 {security_count} 个安全相关引用",
    }

    # Check 7: framework dependency analyzed
    framework_terms = [
        r"\bClaude\b", r"\bCodex\b", r"\bGemini\b", r"\bKimi\b",
        r"\bframework\b", r"\b跨框架\b", r"\bcross.framework\b",
        r"\bportab\b", r"\b可移植\b",
    ]
    framework_count = sum(len(re.findall(term, text, re.IGNORECASE)) for term in framework_terms)
    checks["framework_dependency_analyzed"] = {
        "pass": framework_count >= 2,
        "evidence": f"在笔记中发现 {framework_count} 个框架依赖相关引用",
    }

    # Check 8: boundary conditions
    boundary_terms = [
        r"\b局限\b", r"\blimitation\b", r"\b边界\b", r"\bboundary\b",
        r"\b失败\b", r"\bfailure\b", r"\b假设\b", r"\bassumption\b",
        r"\b不适用\b", r"\bnot applicable\b",
    ]
    boundary_count = sum(len(re.findall(term, text, re.IGNORECASE)) for term in boundary_terms)
    checks["boundary_conditions"] = {
        "pass": boundary_count >= 2,
        "evidence": f"在笔记中发现 {boundary_count} 个边界条件相关引用",
    }

    return checks


def determine_status(checks: dict[str, dict[str, Any]]) -> tuple[str, list[dict[str, str]]]:
    """Determine domain consistency status from checks."""
    repair_plan: list[dict[str, str]] = []
    failed = 0
    critical_failed = 0

    for check_name, result in checks.items():
        if not result["pass"]:
            failed += 1
            is_critical = SKILL_CHECKS.get(check_name, {}).get("critical", False)
            if is_critical:
                critical_failed += 1
            repair_plan.append({
                "check": check_name,
                "problem": SKILL_CHECKS.get(check_name, {}).get("description", check_name),
                "repair_level": "major" if is_critical else "minor",
            })

    if critical_failed >= 2:
        return "needs_regeneration", repair_plan
    if critical_failed >= 1 or failed >= 4:
        return "needs_major_repair", repair_plan
    if failed >= 1:
        return "needs_minor_repair", repair_plan
    return "pass", repair_plan


def validate(note_path: str, source_pack: str | None, domain_template: str | None) -> dict[str, Any]:
    note = Path(note_path).expanduser().resolve()
    if not note.is_file():
        return {
            "schema_version": 1,
            "note": str(note),
            "error": f"Note not found: {note}",
            "status": "needs_major_repair",
        }

    text = note.read_text(encoding="utf-8", errors="ignore")

    # If source pack available, also read full.md for domain detection
    detection_text = text
    if source_pack:
        sp_path = Path(source_pack).expanduser().resolve()
        if sp_path.is_file():
            sp = read_json(sp_path)
            full_md = sp.get("full_md_path") or sp.get("source_md") or ""
            if full_md and Path(full_md).expanduser().is_file():
                detection_text += "\n" + Path(full_md).expanduser().read_text(encoding="utf-8", errors="ignore")[:5000]

    domain, domain_conf = detect_domain(detection_text)
    paper_type, type_conf = detect_paper_type(detection_text)

    checks: dict[str, dict[str, Any]] = {}
    if domain == "agent-skill":
        checks = check_skill_note(text)
    else:
        # Generic check for non-skill domains
        checks["domain_recognized"] = {
            "pass": domain != "unknown",
            "evidence": f"检测到领域: {domain} (置信度: {domain_conf:.2f})",
        }

    status, repair_plan = determine_status(checks)

    passed = sum(1 for c in checks.values() if c["pass"])
    total = len(checks)

    return {
        "schema_version": 1,
        "note": str(note),
        "detected_domain": domain,
        "detected_paper_type": paper_type,
        "domain_confidence": round(domain_conf, 2),
        "paper_type_confidence": round(type_conf, 2),
        "domain_template": domain_template or "",
        "checks": checks,
        "status": status,
        "repair_plan": repair_plan,
        "summary": {
            "passed_checks": passed,
            "failed_checks": total - passed,
            "total_checks": total,
        },
    }


def main() -> int:
    args = parse_args()
    result = validate(args.note, args.source_pack, args.domain_template)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Domain: {result.get('detected_domain', '?')}")
        print(f"Paper type: {result.get('detected_paper_type', '?')}")
        print(f"Status: {result.get('status', '?')}")
        for check_name, check_result in result.get("checks", {}).items():
            status_mark = "✓" if check_result["pass"] else "✗"
            print(f"  [{status_mark}] {check_name}: {check_result.get('evidence', '')}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
