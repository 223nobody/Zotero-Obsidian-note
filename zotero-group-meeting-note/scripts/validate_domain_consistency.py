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
        r"\bskill file\b", r"\bskill document\b", r"\bskill extension\b",
        r"\bskill benchmark\b", r"\bskill-enabled\b",
        r"技能", r"技能文件", r"技能库", r"技能包", r"技能生态", r"技能检索",
        r"技能路由", r"技能组合", r"技能图", r"技能注入", r"技能安全",
        r"\bSkillRet\b", r"\bSkCC\b", r"\bSkillOps\b", r"\bClawTrace\b",
        r"\bOpenSkillEval\b", r"\bGraph-of-Skills\b", r"\bSKILL-INJECT\b",
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
    "benchmark": [r"\bbenchmark\b", r"\bdataset\b", r"\btask suite\b", r"\bevaluation protocol\b",
                  r"基准", r"评测", r"数据集"],
    "survey": [r"\bsurvey\b", r"\bSoK\b", r"\bsystematic review\b", r"\btaxonomy\b",
               r"\bcomprehensive\b.*\breview\b", r"综述", r"路线图", r"分类框架"],
    "analysis": [r"\banalysis\b", r"\bempirical\b", r"\bobservation\b", r"\bstudy\b",
                 r"\bcharacterization\b", r"分析", r"实证", r"审计"],
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
    "paper_type_alignment": {
        "description": "笔记中的论文类型字段是否与源论文标题/摘要的主类型一致",
        "critical": True,
        "repair_level": "regeneration",
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
    parser.add_argument("--note", help="Markdown note path.")
    parser.add_argument("--source-pack", help="Optional source_pack.json path (for full.md reading).")
    parser.add_argument("--domain-template", help="Optional domain-*.md reference path.")
    parser.add_argument(
        "--precheck",
        action="store_true",
        help="Run source-only domain/paper-type precheck before drafting. Implied when --note is omitted.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig", errors="ignore"))


def source_pack_value(source_pack: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = source_pack.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    paths = source_pack.get("paths")
    if isinstance(paths, dict):
        for key in keys:
            value = paths.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def read_source_pack_text(source_pack: str | None) -> tuple[dict[str, Any], str, str, str]:
    if not source_pack:
        return {}, "", "", ""
    sp_path = Path(source_pack).expanduser().resolve()
    if not sp_path.is_file():
        return {}, "", "", ""
    sp = read_json(sp_path)
    title = source_pack_value(sp, "title")
    full_md = source_pack_value(sp, "full_md_path", "source_md", "full_md")
    source_text = ""
    if full_md and Path(full_md).expanduser().is_file():
        source_text = Path(full_md).expanduser().read_text(encoding="utf-8", errors="ignore")
    if title and not source_text.startswith(title):
        source_text = title + "\n\n" + source_text
    return sp, title, source_text, full_md


def source_cues_for_type(source_text: str, candidate: str) -> dict[str, Any]:
    title = extract_title_line(source_text)
    head = source_text[:12000]
    keywords = TYPE_KEYWORDS.get(candidate, [])
    title_cues = [keyword for keyword in keywords if keyword_count(title, keyword) > 0]
    abstract_cues = [keyword for keyword in keywords if keyword_count(head, keyword) > 0 and keyword not in title_cues]
    negative_cues: list[str] = []
    if candidate != "survey" and re.search(r"\b(survey|review|taxonomy|综述|分类框架)\b", head, re.IGNORECASE):
        negative_cues.append("source contains survey/review wording; verify this is not a survey paper")
    if candidate != "benchmark" and re.search(r"\b(benchmark|evaluation protocol|基准|评测)\b", head, re.IGNORECASE):
        negative_cues.append("source contains benchmark/evaluation wording; verify paper_type is not benchmark")
    return {
        "title": title,
        "title_cues": title_cues,
        "abstract_cues": abstract_cues[:12],
        "negative_cues": negative_cues,
    }


def draft_instruction_for_type(paper_type: str) -> str:
    instructions = {
        "method": "Treat this as a method paper: foreground the proposed mechanism, objective, evidence chain, and limitations.",
        "system": "Treat this as a system paper: foreground architecture, runtime workflow, implementation tradeoffs, and system evidence.",
        "benchmark": "Treat this as a benchmark/dataset paper: foreground task design, metrics, baselines, coverage, and evaluation limits.",
        "survey": "Treat this as a survey/review paper: foreground taxonomy, scope boundaries, comparison axes, and synthesis value.",
        "security": "Treat this as a security paper: foreground threat model, attack/defense surface, empirical evidence, and safety boundary.",
        "analysis": "Treat this as an analysis paper: foreground measurement setup, observations, causal limits, and evidence boundary.",
        "theory": "Treat this as a theory paper: foreground definitions, propositions/theorems, proof intuition, assumptions, and applicability.",
    }
    return instructions.get(
        paper_type,
        "Treat this paper according to its title/abstract cues and verify the explicit 论文类型 before drafting.",
    )


def precheck(source_pack: str | None, domain_template: str | None = None) -> dict[str, Any]:
    sp, title, source_text, full_md = read_source_pack_text(source_pack)
    if not source_text:
        return {
            "schema_version": 2,
            "mode": "precheck",
            "status": "fail",
            "source_pack": source_pack or "",
            "error": "source_pack or readable full_md/source text is required for domain precheck",
        }
    domain, domain_conf = detect_domain(source_text[:16000])
    paper_type, type_conf = detect_source_paper_type(source_text)
    cues = source_cues_for_type(source_text, paper_type)
    status = "pass" if type_conf >= 0.75 else "warning" if type_conf >= 0.45 else "fail"
    return {
        "schema_version": 2,
        "mode": "precheck",
        "status": status,
        "source_pack": source_pack or "",
        "full_md_path": full_md,
        "title": title or cues.get("title", ""),
        "detected_domain": domain,
        "domain_confidence": round(domain_conf, 2),
        "paper_type_candidate": paper_type,
        "paper_type_confidence": round(type_conf, 2),
        "confidence": "high" if type_conf >= 0.75 else "medium" if type_conf >= 0.45 else "low",
        "evidence": cues,
        "draft_instruction": draft_instruction_for_type(paper_type),
        "domain_template": domain_template or source_pack_value(sp, "domain_template", "domain_template_path"),
    }


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


def heading_sections(text: str, max_level: int = 3) -> list[dict[str, Any]]:
    """Return Markdown heading sections with body ranges."""
    pattern = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    rows: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        level = len(match.group(1))
        if level > max_level:
            continue
        end = len(text)
        for next_match in matches[index + 1 :]:
            if len(next_match.group(1)) <= level:
                end = next_match.start()
                break
        rows.append(
            {
                "level": level,
                "title": match.group(2).strip(),
                "body": text[match.start() : end],
            }
        )
    return rows


def section_text_by_keywords(text: str, keywords: list[str]) -> tuple[str, int]:
    selected: list[str] = []
    lowered_keywords = [keyword.lower() for keyword in keywords]
    for section in heading_sections(text):
        title = str(section["title"]).lower()
        if any(keyword in title for keyword in lowered_keywords):
            selected.append(str(section["body"]))
    return "\n".join(selected), len(selected)


def pattern_count(text: str, patterns: list[str]) -> int:
    return sum(len(re.findall(pattern, text, re.IGNORECASE)) for pattern in patterns)


def check_result(
    passed: bool,
    evidence: str,
    *,
    applicable: bool = True,
    rationale: str = "",
) -> dict[str, Any]:
    return {
        "pass": passed,
        "applicable": applicable,
        "evidence": evidence,
        "rationale": rationale,
    }


TYPE_KEYWORDS: dict[str, list[str]] = {
    "benchmark": [
        "benchmark", "dataset", "evaluation framework", "evaluation protocol",
        "基准", "评测", "数据集",
    ],
    "survey": [
        "survey", "review", "systematic review", "sok", "taxonomy", "roadmap",
        "综述", "分类框架", "路线图",
    ],
    "system": [
        "system", "architecture", "pipeline", "compiler", "platform", "framework",
        "系统", "架构", "平台", "编译器",
    ],
    "method": [
        "method", "approach", "algorithm", "model", "optimization",
        "方法", "算法", "模型",
    ],
    "security": [
        "security", "attack", "vulnerability", "threat", "stealing", "injection",
        "安全", "攻击", "漏洞", "威胁", "注入", "窃取", "治理",
    ],
    "analysis": [
        "analysis", "empirical", "study", "audit", "measurement",
        "分析", "实证", "审计", "测量",
    ],
    "theory": [
        "theory", "theorem", "proof", "lemma",
        "理论", "定理", "证明",
    ],
}
TYPE_PRIORITY = ["security", "benchmark", "survey", "analysis", "theory", "method", "system"]


TYPE_COMPATIBLE: dict[str, set[str]] = {
    "benchmark": {"benchmark", "dataset", "evaluation"},
    "survey": {"survey", "analysis"},
    "system": {"system", "method"},
    "method": {"method", "system"},
    "security": {"security", "analysis", "benchmark", "system"},
    "analysis": {"analysis", "security", "survey"},
    "theory": {"theory", "method"},
}


def keyword_count(text: str, keyword: str) -> int:
    lowered = text.lower()
    key = keyword.lower()
    if key == "理论":
        return len(re.findall(r"(?<!治)理论", text))
    if re.search(r"[a-z]", key):
        if " " in key or "-" in key:
            return lowered.count(key)
        return len(re.findall(rf"\b{re.escape(key)}\b", lowered))
    return text.count(keyword)


def type_hits(text: str) -> dict[str, int]:
    lowered = text.lower()
    hits: dict[str, int] = {}
    for ptype, keywords in TYPE_KEYWORDS.items():
        count = 0
        for keyword in keywords:
            weight = 3 if keyword.lower() in {
                "benchmark",
                "evaluation framework",
                "evaluation protocol",
                "systematic review",
                "survey",
                "attack",
                "vulnerability",
                "security",
                "基准",
                "评测",
                "综述",
                "安全",
                "攻击",
            } else 1
            count += keyword_count(text, keyword) * weight
        if count:
            hits[ptype] = count
    return hits


def extract_title_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped
    return ""


def strong_source_type_from_contribution(head_lower: str) -> tuple[str, float] | None:
    """Prefer explicit contribution verbs over incidental evaluation wording."""
    benchmark_intro = (
        r"\b(?:we|this paper)\s+(?:introduce|present|propose|release|construct|build)\s+"
        r"(?:a|an|the|new)?\s*(?:benchmark|dataset|task suite|evaluation protocol)\b"
    )
    if re.search(benchmark_intro, head_lower):
        return "benchmark", 0.9

    contribution = r"\b(?:we|this paper)\s+(?:introduce|propose|present|develop|implement|build)\b"
    system_terms = (
        r"\b(runtime|system|architecture|platform|framework|implementation|event-driven|"
        r"capability registry|hook pipeline|plugin|sub-agent delegation)\b"
    )
    method_terms = r"\b(abstraction|approach|method|algorithm|objective|optimization)\b"
    if re.search(contribution, head_lower) and re.search(system_terms, head_lower):
        return "system", 0.9
    if re.search(contribution, head_lower) and re.search(method_terms, head_lower):
        return "method", 0.86
    return None


def detect_source_paper_type(source_text: str) -> tuple[str, float]:
    title = extract_title_line(source_text)
    title_lower = title.lower()
    head = source_text[:12000]
    head_lower = head.lower()
    if re.search(r"\b(this survey|survey provides|systematic review|comprehensive treatment)\b|本文综述|这篇综述", head_lower):
        return "survey", 0.9
    if re.search(r"\b(security|attack|vulnerability|injection|stealing)\b|安全|攻击|漏洞|注入|窃取", title, re.IGNORECASE):
        return "security", 0.95
    if re.search(r"\b(benchmark|evaluation|eval)\b|基准|评测", title, re.IGNORECASE):
        return "benchmark", 0.95
    strong_type = strong_source_type_from_contribution(head_lower)
    if strong_type:
        return strong_type
    if re.search(r"\b(evaluation framework|automatic evaluation|benchmark)\b|评测框架|基准", head_lower):
        return "benchmark", 0.88
    title_hits = type_hits(title)
    if title_hits:
        best = sorted(title_hits, key=lambda key: (-title_hits[key], TYPE_PRIORITY.index(key) if key in TYPE_PRIORITY else 99))[0]
        return best, 0.9
    hits = type_hits(head)
    if not hits:
        ptype, conf = detect_paper_type(head)
        return ptype, conf * 0.6
    # Prefer strong paper-type cues such as benchmark/survey/security over generic
    # "framework" or "architecture" wording, which often appears in titles/abstracts.
    priority_hits = {
        key: hits[key]
        for key in ("security", "benchmark", "survey", "analysis", "theory")
        if hits.get(key, 0) > 0
    }
    ranked = priority_hits or hits
    best = sorted(ranked, key=lambda key: (-ranked[key], TYPE_PRIORITY.index(key) if key in TYPE_PRIORITY else 99))[0]
    total = sum(hits.values())
    confidence = hits[best] / total if total else 0.0
    return best, min(max(confidence, 0.45), 0.85)


def extract_declared_paper_types(note_text: str) -> set[str]:
    candidates: list[str] = []
    for match in re.finditer(r"^\s*\|\s*论文类型\s*\|\s*([^|]+)\|", note_text, re.MULTILINE):
        candidates.append(match.group(1))
    for match in re.finditer(r"论文类型\s*[:：]\s*([^\n|]+)", note_text):
        candidates.append(match.group(1))
    declared: set[str] = set()
    for candidate in candidates:
        hits = type_hits(candidate)
        declared.update(hits)
    return declared


def declared_type_matches_source(declared: set[str], source_type: str) -> bool:
    if not declared or not source_type:
        return True
    compatible = TYPE_COMPATIBLE.get(source_type, {source_type})
    return bool(declared & compatible)


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
    lifecycle_count = pattern_count(text, lifecycle_terms)
    checks["skill_lifecycle_identified"] = check_result(
        lifecycle_count >= 3,
        f"在笔记中发现 {lifecycle_count} 个生命周期相关术语引用",
    )

    # Check 2: skill object defined
    object_terms = [
        r"\bSKILL\.md\b", r"\bskill package\b", r"\bskill artifact\b",
        r"\bprompt snippet\b", r"\btool library\b", r"\bfunction library\b",
        r"\bgraph node\b", r"\blatent adapter\b", r"\bpolicy module\b",
        r"\bskill file\b", r"\bskill files\b", r"\bskill document\b",
        r"\bskill documents\b", r"\bskill extension\b", r"\bskill library\b",
        r"\bskill-enabled\b", r"\bthird.?party code\b",
        r"\bskill 定义\b", r"\bskill 形态\b", r"\bskill 对象\b",
        r"技能文件", r"技能文档", r"技能包", r"技能库", r"技能市场",
        r"技能加载", r"技能扩展", r"技能条目", r"外部指令",
        r"\b中间表示\b", r"\bintermediate representation\b", r"\bIR\b",
    ]
    object_count = pattern_count(text, object_terms)
    checks["skill_object_defined"] = check_result(
        object_count >= 2,
        f"在笔记中发现 {object_count} 个 skill 对象相关引用",
    )

    # Check 3: paper type correct
    type_terms = [
        r"\b(?:method|system|benchmark|survey|analysis|theory)\b",
        r"\b(?:方法|系统|基准|综述|分析|理论)\b",
    ]
    type_count = pattern_count(text, type_terms)
    checks["paper_type_correct"] = check_result(
        type_count >= 1,
        f"在笔记中发现 {type_count} 个论文类型相关引用",
    )

    # Check 4: innovation scoped to lifecycle stage
    innovation_section, innovation_headings_found = section_text_by_keywords(
        text,
        [
            "创新", "贡献", "方法", "机制", "系统", "设计", "架构", "流程",
            "innovation", "contribution", "method", "system", "design",
            "mechanism", "architecture", "pipeline",
        ],
    )

    checks["innovation_scoped"] = check_result(
        innovation_headings_found >= 1 and len(innovation_section) > 100,
        f"发现 {innovation_headings_found} 个创新/方法相关标题，章节内容总长度: {len(innovation_section)} 字符",
    )

    # Check 5: evidence mapped
    evidence_terms = [
        r"\bpass rate\b", r"\breward\b", r"\bablation\b", r"\bstatistical\b",
        r"\btrace\b", r"\bcoverage\b", r"\bMRR\b", r"\bRecall@K\b",
        r"\bhuman.audit\b", r"\b实证\b", r"\b实验\b", r"\b验证\b",
        r"\bTable \d+\b", r"\bFigure \d+\b", r"\bEquation \d+\b",
        r"\b图\s*\d+\b", r"\b表\s*\d+\b", r"\b公式\s*\d+\b",
        r"主实验", r"消融", r"指标", r"基线", r"对比",
    ]
    evidence_count = pattern_count(text, evidence_terms)
    checks["evidence_mapped"] = check_result(
        evidence_count >= 5,
        f"在笔记中发现 {evidence_count} 个证据绑定相关引用",
    )

    # Check 6: security considered (when applicable)
    security_terms = [
        r"\bsecurity\b", r"\bsafety\b", r"\bthreat\b", r"\battack\b",
        r"\bmalicious\b", r"\bvulnerability\b", r"\binjection\b",
        r"\b安全\b", r"\b威胁\b", r"\b攻击\b", r"\b漏洞\b", r"\b注入\b",
        r"权限", r"供应链", r"恶意",
    ]
    security_count = pattern_count(text, security_terms)
    security_applicable = bool(
        re.search(
            r"(security|safety|attack|threat|vulnerab|malicious|injection|"
            r"安全|威胁|攻击|漏洞|注入|权限|供应链|恶意)",
            text,
            re.IGNORECASE,
        )
    )
    checks["security_considered"] = check_result(
        security_count >= 1 if security_applicable else True,
        f"在笔记中发现 {security_count} 个安全相关引用",
        applicable=security_applicable,
        rationale="Only required when the note/paper is security, governance, permission, or risk oriented.",
    )

    # Check 7: framework dependency analyzed
    framework_terms = [
        r"\bClaude\b", r"\bCodex\b", r"\bGemini\b", r"\bKimi\b",
        r"\bframework\b", r"\b跨框架\b", r"\bcross.framework\b",
        r"\bportab\b", r"\b可移植\b", r"框架", r"平台", r"运行时", r"执行环境",
    ]
    framework_count = pattern_count(text, framework_terms)
    framework_applicable = bool(
        re.search(
            r"(framework|cross.framework|portable|Claude|Codex|Gemini|Kimi|"
            r"跨框架|可移植|框架依赖|平台依赖|Claude|Codex|Gemini|Kimi)",
            text,
            re.IGNORECASE,
        )
    )
    checks["framework_dependency_analyzed"] = check_result(
        framework_count >= 2 if framework_applicable else True,
        f"在笔记中发现 {framework_count} 个框架依赖相关引用",
        applicable=framework_applicable,
        rationale="Only required when the paper compares or depends on agent frameworks/runtimes.",
    )

    # Check 8: boundary conditions
    boundary_terms = [
        r"\b局限\b", r"\blimitation\b", r"\b边界\b", r"\bboundary\b",
        r"\b失败\b", r"\bfailure\b", r"\b假设\b", r"\bassumption\b",
        r"\b不适用\b", r"\bnot applicable\b", r"前提", r"威胁", r"风险", r"代价",
    ]
    boundary_count = pattern_count(text, boundary_terms)
    checks["boundary_conditions"] = check_result(
        boundary_count >= 2,
        f"在笔记中发现 {boundary_count} 个边界条件相关引用",
    )

    return checks


def determine_status(checks: dict[str, dict[str, Any]]) -> tuple[str, list[dict[str, str]]]:
    """Determine domain consistency status from checks."""
    repair_plan: list[dict[str, str]] = []
    failed = 0
    critical_failed = 0

    for check_name, result in checks.items():
        if not result.get("applicable", True):
            continue
        if not result["pass"]:
            failed += 1
            is_critical = SKILL_CHECKS.get(check_name, {}).get("critical", False)
            if is_critical:
                critical_failed += 1
            repair_level = str(
                SKILL_CHECKS.get(check_name, {}).get(
                    "repair_level",
                    "major" if is_critical else "minor",
                )
            )
            repair_plan.append({
                "check": check_name,
                "problem": SKILL_CHECKS.get(check_name, {}).get("description", check_name),
                "repair_level": repair_level,
            })

    if any(item["repair_level"] == "regeneration" for item in repair_plan):
        return "needs_regeneration", repair_plan
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
    source_text = ""
    source_precheck: dict[str, Any] = {}
    if source_pack:
        source_precheck = precheck(source_pack, domain_template)
        _, _, source_text, _ = read_source_pack_text(source_pack)
        if source_text:
            detection_text += "\n" + source_text[:5000]

    domain, domain_conf = detect_domain(detection_text)
    paper_type, type_conf = detect_paper_type(detection_text)
    source_paper_type, source_type_conf = detect_source_paper_type(source_text) if source_text else ("", 0.0)
    declared_paper_types = extract_declared_paper_types(text)

    checks: dict[str, dict[str, Any]] = {}
    if domain == "agent-skill":
        checks = check_skill_note(text)
        type_alignment_applicable = bool(source_paper_type and source_type_conf >= 0.7 and declared_paper_types)
        checks["paper_type_alignment"] = check_result(
            declared_type_matches_source(declared_paper_types, source_paper_type)
            if type_alignment_applicable
            else True,
            (
                f"source={source_paper_type or 'unknown'}({source_type_conf:.2f}), "
                f"declared={','.join(sorted(declared_paper_types)) or 'unknown'}"
            ),
            applicable=type_alignment_applicable,
            rationale="Checks the note's explicit paper-type field against the source title/abstract when the source type is clear.",
        )
    else:
        # Generic check for non-skill domains
        checks["domain_recognized"] = check_result(
            True,
            f"检测到领域: {domain} (置信度: {domain_conf:.2f})",
            applicable=False,
            rationale="Generic domain detection is advisory; content quality is checked by the quality gate.",
        )

    status, repair_plan = determine_status(checks)

    applicable_checks = [c for c in checks.values() if c.get("applicable", True)]
    passed = sum(1 for c in applicable_checks if c["pass"])
    total = len(applicable_checks)

    conflict_fields: list[dict[str, Any]] = []
    if source_paper_type and declared_paper_types and not declared_type_matches_source(declared_paper_types, source_paper_type):
        conflict_fields.append(
            {
                "field": "论文类型",
                "source_value": source_paper_type,
                "note_value": sorted(declared_paper_types),
                "repair_scope": "domain_regeneration",
            }
        )

    return {
        "schema_version": 2,
        "note": str(note),
        "detected_domain": domain,
        "detected_paper_type": paper_type,
        "paper_type_candidate": source_precheck.get("paper_type_candidate", source_paper_type or paper_type),
        "source_precheck": source_precheck,
        "source_paper_type": source_paper_type,
        "source_paper_type_confidence": round(source_type_conf, 2),
        "declared_paper_types": sorted(declared_paper_types),
        "conflict_fields": conflict_fields,
        "domain_confidence": round(domain_conf, 2),
        "paper_type_confidence": round(type_conf, 2),
        "domain_template": domain_template or "",
        "checks": checks,
        "status": status,
        "failed_gates": [f"domain:{item['check']}" for item in repair_plan],
        "repair_plan": repair_plan,
        "summary": {
            "passed_checks": passed,
            "failed_checks": total - passed,
            "total_checks": total,
            "advisory_checks": len(checks) - total,
        },
    }


def main() -> int:
    args = parse_args()
    if args.precheck or not args.note:
        result = precheck(args.source_pack, args.domain_template)
        if not args.json:
            print(f"Domain: {result.get('detected_domain', '?')}")
            print(f"Paper type candidate: {result.get('paper_type_candidate', '?')}")
            print(f"Status: {result.get('status', '?')}")
            print(f"Instruction: {result.get('draft_instruction', '')}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status") in {"pass", "warning"} else 1

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
