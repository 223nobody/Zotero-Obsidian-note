#!/usr/bin/env python3
"""Smoke-test deterministic helpers for the group-meeting note skill."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
BUILD_MANIFEST = SCRIPT_DIR / "build_evidence_manifest.py"
PREPARE_OUTPUT = SCRIPT_DIR / "prepare_output.py"
VALIDATE_NOTE = SCRIPT_DIR / "validate_note.py"
VALIDATE_EVIDENCE = SCRIPT_DIR / "validate_evidence_coverage.py"
AUDIT_QUALITY = SCRIPT_DIR / "audit_note_quality.py"
COLLECT_ASSETS = SCRIPT_DIR / "collect_assets.py"
AUDIT_ASSETS = SCRIPT_DIR / "audit_note_assets.py"
UPDATE_SIDECAR = SCRIPT_DIR / "update_pipeline_sidecar.py"
CONFLICT_PATTERNS = (r"^<<<<<<< ",)


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, encoding="utf-8")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_no_conflict_markers() -> None:
    import re
    checked_suffixes = {".md", ".py", ".yaml", ".yml", ".json"}
    offenders: list[str] = []
    for path in sorted(SKILL_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in checked_suffixes:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(re.search(pattern, text, re.MULTILINE) for pattern in CONFLICT_PATTERNS):
            offenders.append(str(path.relative_to(SKILL_DIR)))
    assert_true(not offenders, "Conflict markers remain: " + ", ".join(offenders))


def main() -> int:
    assert_no_conflict_markers()
    with tempfile.TemporaryDirectory(prefix="zotero_skill_smoke_") as tmp:
        root = Path(tmp)
        assets = root / "assets"
        assets.mkdir()
        (assets / "figure-1.png").write_bytes(b"fake")
        (assets / "figure-2.png").write_bytes(b"fake")
        (assets / "table-1.png").write_bytes(b"fake")
        (assets / "supp-figure-1.png").write_bytes(b"fake")
        content_list = root / "content_list.json"
        content_list.write_text(
            json.dumps(
                [
                    {"type": "title", "text": "1 Introduction", "page_idx": 1},
                    {
                        "type": "image",
                        "text": "Figure 1: Method overview and pipeline.",
                        "img_path": "figure-1.png",
                        "page_idx": 2,
                    },
                    {
                        "type": "image",
                        "img_path": "figure-2.png",
                        "page_idx": 3,
                    },
                    {
                        "type": "text",
                        "text": "Figure 2: Distillation dynamics.",
                        "page_idx": 3,
                    },
                    {
                        "type": "table",
                        "text": "Table 1: Main result comparison.",
                        "table_path": "table-1.png",
                        "page_idx": 5,
                    },
                    {"type": "title", "text": "Appendix A Additional Results", "page_idx": 8},
                    {
                        "type": "image",
                        "text": "Figure A1: Appendix diagnostic plot.",
                        "img_path": "figure-1.png",
                        "page_idx": 8,
                    },
                    {"type": "title", "text": "References", "page_idx": 9},
                    {
                        "type": "text",
                        "text": "[1] A citation mentioning Figure 9.",
                        "page_idx": 9,
                    },
                    {
                        "type": "image",
                        "text": "Supplementary Figure 1: Extra failure case.",
                        "img_path": "supp-figure-1.png",
                        "page_idx": 10,
                    },
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        manifest_path = root / "manifest.json"
        manifest_result = run(
            [
                sys.executable,
                str(BUILD_MANIFEST),
                str(content_list),
                "--assets-dir",
                str(assets),
                "--output",
                str(manifest_path),
            ]
        )
        assert_true(manifest_result.returncode == 0, manifest_result.stderr)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        items = manifest["items"]
        labels = [item["label"] for item in items]
        regions = {(item["label"], item["block_index"]): item["region"] for item in items}
        assert_true("Figure 1" in labels, "Figure 1 missing from manifest")
        assert_true("Figure 2" in labels, "Figure 2 missing from manifest")
        assert_true("Figure 2.png" not in labels, "Image-only block leaked filename label")
        assert_true("Table 1" in labels, "Table 1 missing from manifest")
        assert_true("Figure 9" not in labels, "Bibliography mention leaked into manifest")
        assert_true(regions.get(("Figure 1", 2)) == "main", "Figure 1 should be main region")
        assert_true(regions.get(("Table 1", 5)) == "main", "Table 1 should be main region")
        appendix_item = next(item for item in items if item["label"] == "Figure A1")
        assert_true(appendix_item["region"] == "appendix", "Appendix evidence should be appendix region")
        assert_true(
            appendix_item["final_section"] == "## 八、参考文献后内容与补充材料",
            "Appendix evidence should route to supplementary section",
        )
        assert_true(
            any(
                item["label"] == "Supplementary Figure 1"
                and item["region"] == "post_reference"
                for item in items
            ),
            "Post-reference evidence missing",
        )
        assert_true(
            any(item["matched_asset"].endswith("figure-1.png") for item in items),
            "Matched figure asset missing",
        )
        figure_item = next(item for item in items if item["label"] == "Figure 1")
        assert_true("asset_paths" in figure_item, "asset_paths missing from manifest item")
        assert_true(figure_item["asset_paths"], "asset_paths should include matched assets")
        figure_two = next(item for item in items if item["label"] == "Figure 2")
        assert_true(
            any(path.endswith("figure-2.png") for path in figure_two["asset_paths"]),
            "Adjacent image block should be merged into Figure 2",
        )
        assert_true("source_blocks" in figure_two, "source_blocks missing from merged item")
        assert_true("item_key" in figure_two, "item_key missing from merged item")
        assert_true("asset_hashes" in figure_two, "asset_hashes missing from merged item")
        assert_true("source_text" in figure_item, "source_text missing from manifest item")
        assert_true("final_section" in figure_item, "final_section missing from manifest item")
        assert_true("target_section" in figure_item, "target_section missing from manifest item")
        assert_true("required_in_final" in figure_item, "required_in_final missing from manifest item")
        assert_true("page" in figure_item, "page missing from manifest item")
        assert_true("block_index" in figure_item, "block_index missing from manifest item")

        split_manifest = root / "split-manifest.json"
        split_result = run(
            [
                sys.executable,
                str(BUILD_MANIFEST),
                str(content_list),
                "--assets-dir",
                str(assets),
                "--output",
                str(split_manifest),
                "--split-regions",
            ]
        )
        assert_true(split_result.returncode == 0, split_result.stderr)
        split_data = json.loads(split_manifest.read_text(encoding="utf-8"))
        assert_true(
            all(item["region"] == "main" for item in split_data["main_items"]),
            "split manifest main_items should contain only main region",
        )
        assert_true(
            any(item["region"] == "appendix" for item in split_data["post_reference_items"]),
            "split manifest should route appendix items into post_reference_items",
        )

        run_content = root / "run_content_list.json"
        (assets / "figure-3.png").write_bytes(b"fake3")
        (assets / "figure-4.png").write_bytes(b"fake4")
        run_content.write_text(
            json.dumps(
                [
                    {"type": "image", "img_path": "figure-3.png", "page_idx": 6},
                    {"type": "image", "img_path": "figure-4.png", "page_idx": 6},
                    {"type": "text", "text": "Figure 3: First run caption.", "page_idx": 6},
                    {"type": "text", "text": "Figure 4: Second run caption.", "page_idx": 6},
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        run_manifest = root / "run-manifest.json"
        run_result = run(
            [
                sys.executable,
                str(BUILD_MANIFEST),
                str(run_content),
                "--assets-dir",
                str(assets),
                "--output",
                str(run_manifest),
            ]
        )
        assert_true(run_result.returncode == 0, run_result.stderr)
        run_items = json.loads(run_manifest.read_text(encoding="utf-8"))["items"]
        run_map = {item["label"]: [Path(path).name for path in item["asset_paths"]] for item in run_items}
        assert_true(run_map.get("Figure 3") == ["figure-3.png"], "Figure 3 should get only first run asset")
        assert_true(run_map.get("Figure 4") == ["figure-4.png"], "Figure 4 should get only second run asset")

        multi_panel_content = root / "multi-panel-content.json"
        (assets / "figure-5-left.png").write_bytes(b"left")
        (assets / "figure-5-right.png").write_bytes(b"right")
        multi_panel_content.write_text(
            json.dumps(
                [
                    {"type": "image", "img_path": "figure-5-left.png", "page_idx": 7},
                    {"type": "image", "img_path": "figure-5-right.png", "page_idx": 7},
                    {"type": "text", "text": "Figure 5: Left and right panel comparison.", "page_idx": 7},
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        multi_panel_manifest = root / "multi-panel-manifest.json"
        multi_panel_result = run(
            [
                sys.executable,
                str(BUILD_MANIFEST),
                str(multi_panel_content),
                "--assets-dir",
                str(assets),
                "--output",
                str(multi_panel_manifest),
            ]
        )
        assert_true(multi_panel_result.returncode == 0, multi_panel_result.stderr)
        multi_panel_item = json.loads(multi_panel_manifest.read_text(encoding="utf-8"))["items"][0]
        assert_true(
            [Path(path).name for path in multi_panel_item["asset_paths"]]
            == ["figure-5-left.png", "figure-5-right.png"],
            "Single multi-panel caption should keep all adjacent assets",
        )
        assert_true(len(multi_panel_item["panel_roles"]) == 2, "multi-panel item should expose panel roles")

        multi_label_content = root / "multi-label-content.json"
        (assets / "figure-6.png").write_bytes(b"six")
        (assets / "figure-7.png").write_bytes(b"seven")
        multi_label_content.write_text(
            json.dumps(
                [
                    {"type": "image", "img_path": "figure-6.png", "page_idx": 8},
                    {"type": "image", "img_path": "figure-7.png", "page_idx": 8},
                    {
                        "type": "text",
                        "text": "Figure 6: First result. Figure 7: Second result.",
                        "page_idx": 8,
                    },
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        multi_label_manifest = root / "multi-label-manifest.json"
        multi_label_result = run(
            [
                sys.executable,
                str(BUILD_MANIFEST),
                str(multi_label_content),
                "--assets-dir",
                str(assets),
                "--output",
                str(multi_label_manifest),
            ]
        )
        assert_true(multi_label_result.returncode == 0, multi_label_result.stderr)
        multi_label_items = json.loads(multi_label_manifest.read_text(encoding="utf-8"))["items"]
        multi_label_map = {
            item["label"]: [Path(path).name for path in item["asset_paths"]]
            for item in multi_label_items
        }
        assert_true(
            multi_label_map.get("Figure 6") == ["figure-6.png"],
            "First label in a multi-label caption should get first adjacent asset",
        )
        assert_true(
            multi_label_map.get("Figure 7") == ["figure-7.png"],
            "Second label in a multi-label caption should get second adjacent asset",
        )

        bom_content = root / "bom_content_list.json"
        bom_content.write_text(
            json.dumps(
                [
                    {"type": "title", "text": "1 Method", "page_idx": 1},
                    {
                        "type": "table",
                        "text": "Table 9: Main result comparison.",
                        "table_body": "<table><tr><td>not a path</td></tr></table>",
                        "page_idx": 2,
                    },
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8-sig",
        )
        bom_manifest = root / "bom-manifest.json"
        bom_result = run(
            [
                sys.executable,
                str(BUILD_MANIFEST),
                str(bom_content),
                "--assets-dir",
                str(assets),
                "--min-confidence",
                "low",
                "--output",
                str(bom_manifest),
            ]
        )
        assert_true(bom_result.returncode == 0, bom_result.stderr)
        table_item = json.loads(bom_manifest.read_text(encoding="utf-8"))["items"][0]
        assert_true(
            not table_item["asset_paths"],
            "table_body/html content should not be treated as an asset path",
        )

        object_content = root / "object-content-list.json"
        object_content.write_text(
            json.dumps(
                {"type": "image", "text": "Figure 8: Object-shaped content list.", "img_path": "figure-1.png"},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        object_manifest = root / "object-manifest.json"
        object_result = run(
            [
                sys.executable,
                str(BUILD_MANIFEST),
                str(object_content),
                "--assets-dir",
                str(assets),
                "--output",
                str(object_manifest),
            ]
        )
        assert_true(object_result.returncode == 0, object_result.stderr)
        object_items = json.loads(object_manifest.read_text(encoding="utf-8"))["items"]
        assert_true(
            object_items and object_items[0]["label"] == "Figure 8",
            "object-shaped content_list should be treated as a single block",
        )

        note = root / "note.md"
        note.write_text(
            "# Group Meeting Note: Smoke\n\n"
            "## Paper Basic Information\n\nSmoke paper.\n\n"
            "## Core Conclusion\n\n"
            "This note explains the method, evidence, boundary, and discussion.\n\n"
            "## Problem Background And Research Positioning\n\n"
            "The old route lacks a controlled skill gate and source-order evidence binding.\n\n"
            "## Innovation Analysis\n\n"
            "The innovation is a controlled evidence timeline with validation gates.\n\n"
            "## Method Or System Mechanism\n\n"
            "The pipeline builds a manifest, copies assets, writes a note, and validates gates.\n\n"
            "## Figure Table Formula Explanation\n\n"
            "#### Figure 1: Method overview\n\n"
            "![Figure 1](assets/figure-1.png)\n\n"
            "Figure 1 explains the pipeline mechanism and supports the main design claim.\n\n"
            "## Related Work Comparison And Connection\n\n"
            "Compared with loose batch prompting, this route separates drafting and validation.\n\n"
            "## Strengths Limitations And Discussion Questions\n\n"
            "The advantage is traceability. The limitation is that semantic quality still needs review.\n\n"
            "# 组会分享笔记：Smoke\n\n"
            "## 五、图表公式解释\n\n"
            "#### Figure 1：Method overview\n\n"
            "![Figure 1](assets/figure-1.png)\n",
            encoding="utf-8",
        )
        validate_result = run([sys.executable, str(VALIDATE_NOTE), str(note), "--json"])
        assert_true(validate_result.returncode == 0, validate_result.stdout + validate_result.stderr)

        quality_result = run(
            [
                sys.executable,
                str(AUDIT_QUALITY),
                "--note",
                str(note),
                "--evidence-manifest",
                str(manifest_path),
                "--blueprint",
                str(SKILL_DIR / "references" / "blueprint.md"),
                "--json",
            ]
        )
        assert_true(quality_result.returncode != 0, "short smoke note should not pass quality gate")
        quality_data = json.loads(quality_result.stdout)
        assert_true(
            quality_data["status"] in {"needs_minor_repair", "needs_major_repair", "needs_regeneration"},
            "quality audit should return a repair status",
        )

        note.write_text(
            "# 组会分享笔记：Smoke\n\n"
            "## 论文基本信息\n\n"
            "这是一篇用于验证批量受控终稿流水线的 smoke paper，论文类型视为系统/方法类。\n\n"
            "## 一、核心结论\n\n"
            "这篇论文的核心结论是：如果组会笔记要批量生成，就必须把 source pack、evidence manifest、资产迁移、结构校验和质量审稿拆成独立 gate。"
            "Figure 1 给出整体流程，Figure 2 展示蒸馏动态，Table 1 说明主结果比较，Figure A1 和 Supplementary Figure 1 用来验证补充材料路由。"
            "结论成立的边界是：自动 gate 能发现结构和证据问题，但语义深度仍需要 review pass 进行补强。\n\n"
            "## 二、问题背景与研究定位\n\n"
            "旧路线的问题不是单篇写作能力完全失效，而是批量上下文会让多篇论文共享同一套浅层表达。"
            "本文把问题定位在批量生成的控制面：每篇论文都需要独立 source pack，避免跨论文污染；每个图表公式都需要 evidence manifest，避免只靠记忆补写。"
            "因此它属于组会笔记生产流水线的工程化控制问题，而不是重新发明笔记结构模板。\n\n"
            "## 三、创新点分析\n\n"
            "第一，流水线把 evidence manifest 作为写作前的硬约束，确保 Figure/Table/Equation 不会被批量摘要吞掉。"
            "第二，blueprint structure gate 复用现有 blueprint，而不是新建并行结构文件。"
            "第三，quality gate 把章节存在和内容达标分开，能识别只有标题、没有机制解释和结果分析的空心稿。"
            "这些创新点分别由 Figure 1、Table 1 和补充材料路由测试支撑。\n\n"
            "## 四、方法或系统机制\n\n"
            "系统流程是：先检查输入 PDF、full.md、content_list.json 和 assets，再为单篇论文写入 source pack。"
            "随后 build_evidence_manifest.py 生成 Figure/Table/Equation 的顺序化清单，prepare_output.py 复制匹配资产，validate_note.py 和 audit_note_quality.py 分别执行结构/证据/资产和内容深度检查。"
            "这个机制的关键是每篇论文独立运行，主 agent 只汇总 gate 报告和最终交付状态。\n\n"
            "## 五、图表公式解释\n\n"
            "#### Figure 1：Method overview\n\n"
            "![Figure 1](assets/figure-1.png)\n\n"
            "Figure 1 展示主流程：输入材料先被整理为 source pack，再生成 evidence manifest，最后经过结构、证据、资产和质量 gate。"
            "它证明的不是某个模型能力提升，而是批量生产过程可以被拆成可验证的状态机。\n\n"
            "#### Figure 2：Distillation dynamics\n\n"
            "![Figure 2](assets/figure-2.png)\n\n"
            "Figure 2 用来验证相邻图片块与 caption 的绑定逻辑。它说明 manifest 不只记录 label，还要把附近图片合并到同一个证据条目，避免图片被丢到文末资源索引。\n\n"
            "#### Table 1：Main result comparison\n\n"
            "![Table 1](assets/table-1.png)\n\n"
            "Table 1 是主结果比较，重点不是表格本身，而是验证 evidence gate 会要求表格条目出现在终稿中，并在对应位置解释比较对象、指标和结论边界。\n\n"
            "## 六、与相关工作的对比与联系\n\n"
            "相比只依赖 prompt 的批量写作，这条路线更接近可审计的数据处理流水线。"
            "它和普通 Markdown 校验不同，因为它不仅检查链接是否存在，还检查证据是否按原文顺序进入 blueprint 指定章节。"
            "它和人工逐篇修稿也不同，因为它先用 gate 缩小问题范围，再让人工或模型集中修复高风险章节。\n\n"
            "## 七、优点、局限与讨论问题\n\n"
            "优点是可追踪、可复跑、可区分生成成功和质量通过。局限是质量 gate 仍然是启发式，不能替代完整论文阅读。"
            "可以讨论的问题包括：required evidence 的粒度如何设定、低置信度图片是否需要人工核对、以及质量分数是否应该按论文类型调整。\n\n"
            "## 八、参考文献后内容与补充材料\n\n"
            "### Figure A1：Appendix diagnostic plot\n\n"
            "![Figure A1](assets/figure-1.png)\n\n"
            "Figure A1 属于 appendix 证据，不应混入主文证据时间线。它用于验证补充材料必须进入单独章节。\n\n"
            "### Supplementary Figure 1：Extra failure case\n\n"
            "![Supplementary Figure 1](assets/supp-figure-1.png)\n\n"
            "Supplementary Figure 1 属于参考文献后的补充内容，用于说明 post-reference evidence 也要覆盖，但位置应在补充材料章节。\n",
            encoding="utf-8",
        )

        collect_source = root / "collect-source.md"
        collect_source.write_text(
            "# Collect\n\n![first](assets/figure-1.png)\n\n![second](assets/figure-1.png)\n",
            encoding="utf-8",
        )
        collected_assets_dir = root / "collected-assets"
        collect_result = run(
            [
                sys.executable,
                str(COLLECT_ASSETS),
                str(collect_source),
                "--assets-dir",
                str(collected_assets_dir),
                "--json",
            ]
        )
        assert_true(collect_result.returncode == 0, collect_result.stderr)
        collect_data = json.loads(collect_result.stdout)
        assert_true(len(collect_data["copied"]) == 1, "collect_assets should not duplicate same target")
        assert_true(
            len(list(collected_assets_dir.iterdir())) == 1,
            "collect_assets should reuse same-hash assets in destination",
        )

        copy_map = root / "copy-map.json"
        prepared_dir = root / "prepared"
        prepare_result = run(
            [
                sys.executable,
                str(PREPARE_OUTPUT),
                "--article-filename",
                "Smoke Paper",
                "--obsidian-dir",
                str(prepared_dir),
                "--no-zotero-file",
                "--sync-from-manifest",
                str(manifest_path),
                "--copy-map",
                str(copy_map),
            ]
        )
        assert_true(prepare_result.returncode == 0, prepare_result.stderr)
        prepare_data = json.loads(prepare_result.stdout)
        assert_true(prepare_data["copy_map_path"] == str(copy_map.resolve()), "copy map path missing")
        copy_map_data = json.loads(copy_map.read_text(encoding="utf-8"))
        assert_true(copy_map_data["copied_assets"], "copy map should contain copied assets")
        copied_markdown = {item.get("markdown", "") for item in copy_map_data["copied_assets"]}
        assert_true(
            "assets/figure-01-smoke-paper-method-overview-pipeline.png" in copied_markdown,
            "manifest sync should use figure-number-paper-topic asset names",
        )
        assert_true(
            "assets/table-01-smoke-paper-main-result-comparison.png" in copied_markdown,
            "manifest sync should use table-number-paper-topic asset names",
        )
        assert_true(
            "assets/figure-01-smoke-paper-supp-extra-failure-case.png" in copied_markdown,
            "post-reference manifest assets should include supp in the asset name",
        )
        assert_true(
            any(item.get("item_key") == figure_two["item_key"] for item in copy_map_data["copied_assets"]),
            "copy map should preserve manifest item_key",
        )
        rerun_prepare_result = run(
            [
                sys.executable,
                str(PREPARE_OUTPUT),
                "--article-filename",
                "Smoke Paper",
                "--obsidian-dir",
                str(prepared_dir),
                "--no-zotero-file",
                "--sync-from-manifest",
                str(manifest_path),
                "--copy-map",
                str(root / "copy-map-rerun.json"),
            ]
        )
        assert_true(rerun_prepare_result.returncode == 0, rerun_prepare_result.stderr)
        rerun_data = json.loads(rerun_prepare_result.stdout)
        assert_true(
            any(item.get("copy_action") == "reused" for item in rerun_data["copied_assets"]),
            "prepare_output should reuse existing same-hash manifest assets on rerun",
        )

        nested_assets = assets / "images"
        nested_assets.mkdir()
        (nested_assets / "nested-figure.png").write_bytes(b"nested")
        nested_manifest = root / "nested-manifest.json"
        nested_manifest.write_text(
            json.dumps(
                {
                    "source": {"assets_dir": str(assets)},
                    "items": [
                        {
                            "item_key": "main-figure-figure-10",
                            "label": "Figure 10",
                            "type": "Figure",
                            "region": "main",
                            "match_confidence": "high",
                            "matched_asset": "images/nested-figure.png",
                            "asset_paths": ["images/nested-figure.png"],
                            "source_text": "Figure 10: Nested asset routing.",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        nested_copy_map = root / "nested-copy-map.json"
        nested_prepare_result = run(
            [
                sys.executable,
                str(PREPARE_OUTPUT),
                "--article-filename",
                "Nested Paper",
                "--obsidian-dir",
                str(root / "nested-prepared"),
                "--no-zotero-file",
                "--sync-from-manifest",
                str(nested_manifest),
                "--copy-map",
                str(nested_copy_map),
            ]
        )
        assert_true(nested_prepare_result.returncode == 0, nested_prepare_result.stderr)
        nested_map = json.loads(nested_copy_map.read_text(encoding="utf-8"))
        assert_true(
            nested_map["copied_assets"][0]["source"].endswith("images\\nested-figure.png")
            or nested_map["copied_assets"][0]["source"].endswith("images/nested-figure.png"),
            "manifest sync should preserve nested relative asset paths",
        )

        missing_asset_note = root / "missing-asset-note.md"
        missing_asset_note.write_text("# Test\n\n#### Figure 1\n\nText only.\n", encoding="utf-8")
        coverage_manifest = root / "coverage-manifest.json"
        coverage_manifest.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "label": "Figure 1",
                            "region": "main",
                            "section": "Method",
                            "match_confidence": "high",
                            "matched_asset": str(assets / "figure-1.png"),
                            "asset_paths": [str(assets / "figure-1.png")],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8-sig",
        )
        coverage_result = run(
            [
                sys.executable,
                str(VALIDATE_NOTE),
                str(missing_asset_note),
                "--evidence-manifest",
                str(coverage_manifest),
                "--json",
            ]
        )
        assert_true(coverage_result.returncode == 0, coverage_result.stdout + coverage_result.stderr)
        coverage = json.loads(coverage_result.stdout)
        assert_true(
            any(w["kind"] == "missing_evidence_asset_link" for w in coverage["warnings"]),
            "validate_note should warn when a high-confidence manifest asset is not linked",
        )

        evidence_gate_result = run(
            [
                sys.executable,
                str(VALIDATE_EVIDENCE),
                "--note",
                str(missing_asset_note),
                "--evidence-manifest",
                str(coverage_manifest),
                "--strict",
                "--json",
            ]
        )
        assert_true(evidence_gate_result.returncode != 0, "strict evidence gate should fail missing assets")

        wrong_placement_note = root / "wrong-placement-note.md"
        wrong_placement_note.write_text(
            "# Test\n\n"
            "## Figure 1\n\nText only.\n\n"
            "## Figure 2\n\n![Figure 1 misplaced](assets/figure-1.png)\n",
            encoding="utf-8",
        )
        wrong_placement_result = run(
            [
                sys.executable,
                str(VALIDATE_NOTE),
                str(wrong_placement_note),
                "--evidence-manifest",
                str(coverage_manifest),
                "--strict-evidence",
                "--json",
            ]
        )
        assert_true(
            wrong_placement_result.returncode != 0,
            "Strict evidence validation should fail misplaced assets",
        )
        wrong_placement = json.loads(wrong_placement_result.stdout)
        assert_true(
            any(e["kind"] == "misplaced_evidence_asset_link" for e in wrong_placement["errors"]),
            "Strict evidence validation should report misplaced evidence asset",
        )

        early_mention_note = root / "early-mention-note.md"
        early_mention_note.write_text(
            "# Test\n\n"
            "## 一、核心结论\n\nFigure 1 summarizes the method.\n\n"
            "## 五、图表公式解释\n\n"
            "### Figure 1 方法总览\n\n"
            "![Figure 1](assets/figure-1.png)\n",
            encoding="utf-8",
        )
        early_result = run(
            [
                sys.executable,
                str(VALIDATE_NOTE),
                str(early_mention_note),
                "--evidence-manifest",
                str(coverage_manifest),
                "--strict-evidence",
                "--json",
            ]
        )
        assert_true(early_result.returncode == 0, early_result.stdout + early_result.stderr)

        authoritative_note = root / "authoritative-note.md"
        authoritative_note.write_text(
            "# Test\n\n## Figure 1\n\n![Old link](assets/figure-1.png)\n",
            encoding="utf-8",
        )
        authoritative_map = root / "authoritative-copy-map.json"
        authoritative_map.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "copied_assets": [
                        {
                            "item_key": "main-figure-figure-1",
                            "label": "Figure 1",
                            "markdown": "assets/copied-figure-1.png",
                            "source": str(assets / "figure-1.png"),
                            "destination": str(root / "assets" / "copied-figure-1.png"),
                            "source_sha256": "",
                            "destination_sha256": "",
                        }
                    ],
                    "items": {
                        "main-figure-figure-1": [
                            {
                                "item_key": "main-figure-figure-1",
                                "label": "Figure 1",
                                "markdown": "assets/copied-figure-1.png",
                                "source": str(assets / "figure-1.png"),
                                "destination": str(root / "assets" / "copied-figure-1.png"),
                                "source_sha256": "",
                                "destination_sha256": "",
                            }
                        ]
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        authoritative_manifest = root / "authoritative-manifest.json"
        authoritative_manifest.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "item_key": "main-figure-figure-1",
                            "label": "Figure 1",
                            "region": "main",
                            "section": "Method",
                            "match_confidence": "high",
                            "matched_asset": str(assets / "figure-1.png"),
                            "asset_paths": [str(assets / "figure-1.png")],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        authoritative_result = run(
            [
                sys.executable,
                str(VALIDATE_NOTE),
                str(authoritative_note),
                "--evidence-manifest",
                str(authoritative_manifest),
                "--copy-map",
                str(authoritative_map),
                "--copy-map-authoritative",
                "--strict-evidence",
                "--json",
            ]
        )
        assert_true(
            authoritative_result.returncode != 0,
            "Authoritative copy-map validation should reject old non-copy-map links",
        )

        copied_asset = root / "assets" / "copied-figure-1.png"
        copied_asset.write_bytes((assets / "figure-1.png").read_bytes())
        authoritative_ok_note = root / "authoritative-ok-note.md"
        authoritative_ok_note.write_text(
            "# Test\n\n## Figure 1\n\n![Copied link](assets/copied-figure-1.png)\n",
            encoding="utf-8",
        )
        authoritative_ok_result = run(
            [
                sys.executable,
                str(VALIDATE_NOTE),
                str(authoritative_ok_note),
                "--evidence-manifest",
                str(authoritative_manifest),
                "--copy-map",
                str(authoritative_map),
                "--copy-map-authoritative",
                "--strict-evidence",
                "--json",
            ]
        )
        assert_true(
            authoritative_ok_result.returncode == 0,
            authoritative_ok_result.stdout + authoritative_ok_result.stderr,
        )
        authoritative_missing_map_result = run(
            [
                sys.executable,
                str(VALIDATE_NOTE),
                str(authoritative_ok_note),
                "--evidence-manifest",
                str(authoritative_manifest),
                "--copy-map-authoritative",
                "--strict-evidence",
                "--json",
            ]
        )
        assert_true(
            authoritative_missing_map_result.returncode != 0,
            "Authoritative copy-map validation should require --copy-map",
        )
        authoritative_missing_map = json.loads(authoritative_missing_map_result.stdout)
        assert_true(
            any(e["kind"] == "copy_map_required" for e in authoritative_missing_map["errors"]),
            "Authoritative copy-map validation should report missing --copy-map",
        )

        duplicate = assets / "figure-1-copy.png"
        duplicate.write_bytes((assets / "figure-1.png").read_bytes())
        asset_report = root / "asset-report.json"
        audit_result = run(
            [
                sys.executable,
                str(AUDIT_ASSETS),
                str(note),
                "--output",
                str(asset_report),
            ]
        )
        assert_true(audit_result.returncode == 0, audit_result.stderr)
        audit = json.loads(asset_report.read_text(encoding="utf-8"))
        assert_true(audit["image_link_count"] >= 1, "asset audit image count mismatch")
        assert_true(audit["assets_total"] >= 5, "asset audit total asset count mismatch")
        assert_true(audit["unused_assets_count"] >= 4, "asset audit unused count mismatch")
        assert_true(audit["duplicate_hash_count"] >= 1, "asset audit duplicate hash missing")
        cleanup_report = root / "asset-cleanup-report.json"
        cleanup_result = run(
            [
                sys.executable,
                str(AUDIT_ASSETS),
                str(note),
                "--output",
                str(cleanup_report),
                "--delete-duplicate-unused",
            ]
        )
        assert_true(cleanup_result.returncode == 0, cleanup_result.stderr)
        cleanup = json.loads(cleanup_report.read_text(encoding="utf-8"))
        assert_true(cleanup["deleted_assets"], "asset cleanup should delete unused duplicate assets")
        assert_true("skipped_delete_paths" in cleanup, "asset cleanup should report skipped delete paths")

        wiki_note = root / "wiki-note.md"
        wiki_note.write_text("# Wiki\n\nNo local image.\n", encoding="utf-8")
        wiki_sibling = root / "wiki-sibling.md"
        wiki_sibling.write_text("# Sibling\n\n![[assets/figure-1.png]]\n", encoding="utf-8")
        wiki_report = root / "wiki-asset-report.json"
        wiki_result = run(
            [
                sys.executable,
                str(AUDIT_ASSETS),
                str(wiki_note),
                "--output",
                str(wiki_report),
                "--scan-sibling-notes",
                "--vault-root",
                str(root),
            ]
        )
        assert_true(wiki_result.returncode == 0, wiki_result.stderr)
        wiki_audit = json.loads(wiki_report.read_text(encoding="utf-8"))
        assert_true(
            wiki_audit["sibling_referenced_assets_count"] >= 1,
            "asset audit should detect sibling wiki embeds",
        )

        sidecar = root / "sidecar.json"
        sidecar_result = run(
            [
                sys.executable,
                str(UPDATE_SIDECAR),
                "--sidecar",
                str(sidecar),
                "--paper-key",
                "smoke-paper",
                "--pdf-path",
                str(root / "paper.pdf"),
                "--source-md",
                str(root / "full.md"),
                "--content-list",
                str(content_list),
                "--manifest-path",
                str(manifest_path),
                "--note-path",
                str(note),
                "--asset-report-path",
                str(asset_report),
                "--stage",
                "validate",
                "--status",
                "complete",
                "--set",
                "counts.image_link_count=1",
            ]
        )
        assert_true(sidecar_result.returncode == 0, sidecar_result.stderr)
        sidecar_data = json.loads(sidecar.read_text(encoding="utf-8"))
        assert_true(sidecar_data["paper_key"] == "smoke-paper", "sidecar paper_key missing")
        assert_true(
            sidecar_data["stages"]["validate"]["status"] == "complete",
            "sidecar validate stage missing",
        )
        assert_true(
            sidecar_data["counts"]["image_link_count"] == 1,
            "sidecar dotted count update missing",
        )

        empty_batch = root / "empty-batch.json"
        empty_batch.write_text('{"papers":[{}]}', encoding="utf-8-sig")
        batch_result = run(
            [
                sys.executable,
                str(SCRIPT_DIR / "batch_note_pipeline.py"),
                str(empty_batch),
                "--work-dir",
                str(root / "batch-work"),
                "--stages",
                "preflight",
            ]
        )
        assert_true(batch_result.returncode != 0, "Empty batch record should fail preflight")

        full_batch = root / "full-batch.json"
        full_work = root / "full-batch-work"
        full_batch.write_text(
            json.dumps(
                {
                    "papers": [
                        {
                            "paper_key": "full-smoke",
                            "content_list": str(content_list),
                            "assets_dir": str(assets),
                            "note_path": str(note),
                            "note_assets_dir": str(assets),
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        full_batch_result = run(
            [
                sys.executable,
                str(SCRIPT_DIR / "batch_note_pipeline.py"),
                str(full_batch),
                "--work-dir",
                str(full_work),
                "--stages",
                "preflight,parse_cache,evidence_manifest,draft,review,quality,validate,cleanup_report",
                "--continue-on-error",
                "--final-report",
                str(root / "batch-final-report.md"),
            ]
        )
        assert_true(full_batch_result.returncode == 0, full_batch_result.stdout + full_batch_result.stderr)
        full_sidecar = json.loads((full_work / "sidecars" / "full-smoke.json").read_text(encoding="utf-8"))
        assert_true(
            full_sidecar["stages"]["parse_cache"]["status"] == "complete",
            "batch sidecar parse_cache stage missing",
        )
        assert_true(
            full_sidecar["stages"]["draft"]["status"] == "complete",
            "batch sidecar draft checkpoint missing",
        )
        assert_true(
            full_sidecar["stages"]["review"]["status"] == "skipped",
            "batch sidecar review checkpoint should be explicit when not automated",
        )
        assert_true(
            full_sidecar["stages"]["quality"]["status"] == "failed",
            "batch sidecar quality gate should record short-note failure",
        )
        assert_true(
            "quality_report_path" in full_sidecar["paths"],
            "batch sidecar should record quality report path",
        )
        assert_true(
            full_sidecar["counts"]["image_link_count"] >= 1,
            "batch sidecar cleanup counts missing",
        )
        assert_true(
            full_sidecar["counts"]["appendix_items"] >= 1,
            "batch sidecar should count appendix evidence separately",
        )
        assert_true(
            full_sidecar["counts"]["supplementary_items"] >= 2,
            "batch sidecar should count appendix and post-reference evidence as supplementary",
        )

        bad_note = root / "bad.md"
        bad_note.write_text(
            "# Bad\n\n## 附录：MinerU 图片资源完整性索引\n\n"
            "- ![missing](assets/missing.png)\n",
            encoding="utf-8",
        )
        bad_result = run([sys.executable, str(VALIDATE_NOTE), str(bad_note), "--json"])
        assert_true(bad_result.returncode != 0, "Bad note unexpectedly passed validation")

    print("smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
