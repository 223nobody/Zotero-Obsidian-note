# zotero-group-meeting-note Skill 质量门控重构方案

## 1. 目标校准

当前优化目标不是重新设计组会笔记的固定终稿结构，也不是新增一套与现有蓝图并行的结构规范。固定终稿结构已经由 `zotero-group-meeting-note/references/blueprint.md` 规定，本方案将 `blueprint.md` 作为唯一结构契约复用。

因此，本轮重构只解决一个问题：在 `single-final` 和 `batch-final-controlled` 模式下，如何通过更严格的判定门控、自动返工和交付审计，让批量调用也能稳定产出高质量最终稿。

关键判断：

- 当前 skill 的单篇能力已经可用，主要问题出现在批量调用时的上下文稀释、逐篇隔离不足、检查不严和返工闭环不足。
- 不应把某一篇优秀样例的结构固化为新规范；应复用 `blueprint.md` 的通用结构和写法约束。
- 批量模式可以直接生成最终 `.md`，但每篇必须独立通过 source、structure、evidence、asset、quality、delivery 六类 gate。
- 不能把“文件存在”“章节数量正确”误判为“组会笔记质量达标”。

## 2. 结构契约复用原则

`references/blueprint.md` 是终稿结构与章节写法的单一来源。

本方案明确不做以下事情：

- 不新增 `references/final-note-structure.md`。
- 不在优化方案中复制一份固定终稿结构。
- 不把 `blueprint.md` 拆成多套并行结构规范。
- 不修改 `blueprint.md` 已有结构内容。
- 不把 SkCC 或任何单篇样例变成结构模板。

需要做的是：

- 在 `SKILL.md` 中明确：终稿结构以 `references/blueprint.md` 为准。
- 在验证脚本中读取或引用 `blueprint.md` 的结构约束。
- 在 `review-pass.md` 和 `validation.md` 中强化“是否遵守 blueprint”的判定标准。
- 在批量流水线中把 `blueprint.md` 检查作为硬 gate，而不是写作建议。

## 3. 最终能力目标

重构后的 skill 应支持两种正式生产模式：

| 模式 | 使用场景 | 输出 |
| --- | --- | --- |
| `single-final` | 单篇论文深度组会分享 | 1 篇高质量最终稿 + assets + 单篇验证报告 |
| `batch-final-controlled` | 多篇论文批量生成组会笔记 | N 篇高质量最终稿 + 每篇 assets + 每篇 gate 报告 + 全量交付报告 |

`batch-final-controlled` 不是“批量粗稿模式”，而是“批量受控终稿模式”。它允许批量执行，但每篇论文必须作为独立任务通过完整门控后才能标记完成。

## 4. 批量效果变差的主要原因

从当前失败表现看，问题更像是批量编排与判定门控不足，而不是 `blueprint.md` 结构本身失效。

主要原因：

- 批量上下文过大，模型容易把每篇论文都压缩成相同的七八章浅层摘要。
- 每篇论文没有独立 source pack，导致写作时依赖批量上下文记忆，而不是依赖该论文的证据。
- 证据清单没有成为硬约束，图、表、公式、实验数字容易遗漏或只做 caption 复述。
- 结构检查只看是否有章节，未检查章节是否符合 `blueprint.md` 的写法要求。
- 质量审稿没有强制输出状态，导致明显不合格的笔记也进入“已完成”集合。
- 返工缺少闭环：发现问题后没有按 `minor / major / regeneration` 分级修复。
- 批量报告不够严格，无法清楚区分“已生成文件”和“已通过最终质量门槛”。

## 5. 批量受控终稿流水线

推荐将 `batch-final-controlled` 固化为以下流水线：

```text
batch_preflight
-> build_source_pack
-> build_evidence_manifest
-> prepare_note_and_assets
-> draft_with_blueprint
-> structure_gate
-> evidence_gate
-> asset_gate
-> quality_gate
-> repair_if_needed
-> final_gate
-> batch_delivery_report
```

每篇论文都必须独立走完流水线。批量可以并行，但并行单位应是“单篇论文任务”，不能让多篇论文共用一个未隔离的写作上下文。

## 6. Gate 设计

### 6.1 Preflight Gate

目的：防止材料不完整时直接生成低质量笔记。

检查项：

- PDF 是否存在。
- MinerU zip 或解压目录是否存在。
- `full.md` 是否存在且非空。
- `content_list.json` 是否存在且可解析。
- `manifest.json` 是否存在。
- 输出路径是否符合 `<论文标题>/assets` + `<论文标题>.md`。
- Windows 路径是否过长，是否需要 hash-truncated title。
- 标题、PDF、MinerU 包、输出目录是否一一匹配。

失败处理：

- 缺 PDF、缺 `full.md`、缺 `content_list.json`：不得进入写作。
- 标题或 MinerU 包匹配不确定：进入人工问题清单。
- 路径过长：自动生成可追踪的短目录名，但 H1 保留完整论文标题。

### 6.2 Source Pack Gate

目的：让每篇笔记只依赖自己的论文材料。

每篇论文生成独立 `source_pack.json`，至少包含：

```json
{
  "paper_key": "",
  "title": "",
  "pdf_path": "",
  "mineru_zip": "",
  "full_md": "",
  "content_list_json": "",
  "manifest_json": "",
  "assets_source_dir": "",
  "note_path": "",
  "note_assets_dir": ""
}
```

判定规则：

- source pack 必须逐篇生成，不得让多篇共享一个临时材料清单。
- 草稿生成、证据抽取、资产迁移、验证报告都必须引用同一个 source pack。
- 如果 source pack 中关键路径变化，必须重新跑后续 gate。

### 6.3 Evidence Manifest Gate

目的：把“图表公式证据覆盖”从写作建议变成硬约束。

每篇论文必须生成 `evidence_manifest.json`，建议字段：

```json
{
  "paper_key": "",
  "title": "",
  "evidence_items": [
    {
      "order": 1,
      "type": "Figure | Table | Equation | Algorithm | Prompt | Case | Supplement",
      "label": "Figure 1",
      "region": "main | appendix | post_reference",
      "caption": "",
      "nearby_text": "",
      "asset_paths": [],
      "core_level": "core | secondary",
      "required_in_final": true,
      "target_section": "blueprint section name"
    }
  ]
}
```

判定规则：

- 主文中 `required_in_final=true` 的 Figure / Table / Equation / Algorithm / Prompt / Case 必须进入终稿。
- 证据条目必须保留原文编号或可追踪标签。
- 主文证据必须按原文首次出现顺序进入 `blueprint.md` 指定的图表公式解释章节。
- appendix / post-reference 证据只能进入 `blueprint.md` 规定的补充材料章节。
- 无 caption、无编号、无法与上下文绑定的 MinerU 裁图不得进入终稿，只能留在审计 JSON。

### 6.4 Blueprint Structure Gate

目的：确认最终稿遵守 `references/blueprint.md`，而不是只生成了若干泛化章节。

判定规则：

- 终稿 H1、一级章节和可选补充章节必须符合 `blueprint.md` 当前规定。
- 章节顺序必须符合 `blueprint.md`。
- 不能把图、表、公式拆成三个互不相干的章节；必须遵守 `blueprint.md` 中统一证据时间线的要求。
- 如果 `blueprint.md` 规定某章只在存在实质补充材料时出现，则 gate 需要区分“合理省略”和“遗漏章节”。
- 每个必需章节必须有实质内容，不能只有占位句、模板句或内部工作说明。
- 章节标题合格不等于通过；还要检查章节职责是否正确，例如相关工作不能写成参考文献罗列，局限不能写成空泛套话。

失败示例：

- 只有七个章节，缺少 `blueprint.md` 要求的关键分析主线。
- `图表公式解释` 章节只贴图或复述 caption。
- `相关工作` 章节只罗列论文名，没有路线级比较。
- `优点、局限与讨论问题` 只写“未来工作可以进一步研究”。
- 把 MinerU 图片资源完整性索引写进最终稿正文。

### 6.5 Evidence Coverage Gate

目的：确认终稿覆盖了核心证据，并且证据被解释到可用于组会讲解。

检查项：

- `evidence_manifest.json` 中 required 证据覆盖率是否为 100%，除非明确写有 `待核对原文`。
- 每个核心 Figure / Table / Equation 是否解释了“是什么、证明什么、不能证明什么、对应哪个创新点或结论”。
- 图表公式是否按原文首次出现顺序混排。
- 核心证据是否被连接到创新点、方法机制、实验结论或局限边界。
- 表格是否解释 baseline、指标、主要提升和比较公平性。
- 公式是否解释符号、位置、目标、直觉和边界。

失败处理：

- 漏掉 required 证据：`needs_major_repair`。
- 证据顺序错乱：`needs_minor_repair` 或 `needs_major_repair`，取决于影响范围。
- 只复述 caption：`needs_major_repair`。
- 核心实验数字无指标或 baseline：`needs_major_repair`。

### 6.6 Asset Gate

目的：防止 Obsidian 笔记出现断图、绝对路径、图片堆叠或无意义资源索引。

检查项：

- note 中所有图片链接都指向 note-local `assets/...`。
- note 中不存在绝对路径。
- note 中引用的每个图片文件都存在。
- 复制到 note `assets/` 的文件必须被正文引用，除非在审计报告中标为保留原因。
- 关键证据对应图片应放在对应证据条目附近。
- 最终稿正文不得出现 MinerU asset dump、未匹配裁图清单、资源完整性索引。

判定说明：

- 不要求把 MinerU 导出的每个图片都写进最终稿。
- 要求进入最终稿的图片必须能与论文证据条目绑定。
- 未匹配图片应保留在 manifest 或 audit 报告中，而不是进入 Obsidian 正文。

### 6.7 Quality Gate

目的：判断笔记是否达到“可直接用于组会分享”的内容深度。

输出状态：

```text
pass
needs_minor_repair
needs_major_repair
needs_regeneration
```

检查维度：

- 核心结论是否有判断，而不是摘要复述。
- 研究问题是否具体，能说明旧路线卡在哪里。
- 创新点是否绑定证据和边界。
- 方法或系统机制是否讲得清输入、输出、流程、关键模块和设计理由。
- 实验结果是否解释指标、baseline、提升、代价和泛化边界。
- 相关工作是否是路线级定位，而不是文献堆叠。
- 局限是否具体到数据、模型、实验、场景、成本、复现或威胁模型。
- 讨论问题是否有研究价值，且能引发组会讨论。
- 语言是否是自然中文，关键英文术语是否首次重要出现时有中文解释。
- 是否存在批量生成套话、内部脚手架话术、占位符和自我审计残留。

最低门槛：

- 不允许只生成摘要级笔记。
- 不允许所有论文写成同质化七章概述。
- 不允许“结构通过但内容空心”的笔记进入完成清单。

### 6.8 Domain Consistency Gate

目的：避免论文类型判断错误导致章节内容错位。

检查项：

- 论文类型是否正确识别为 method / system / benchmark / dataset / analysis / theory / application / survey 等。
- 是否读取了匹配领域参考文件，例如 `domain-skill.md`、`domain-llm.md`、`domain-systems.md`。
- 对 agent skill 类论文，是否区分 architecture、acquisition、retrieval/routing、security/governance、internalization、HCI 等方向。
- 章节重点是否随论文类型变化，而不是机械填充同一种说法。

失败处理：

- 领域明显错判：`needs_major_repair`。
- 方法论文写成 survey，或 survey 写成方法论文：`needs_regeneration`。

### 6.9 Final Delivery Gate

目的：把“已生成文件”和“已通过交付标准”分开。

每篇最终通过时必须具备：

- final note path。
- assets path。
- source pack path。
- evidence manifest path。
- validation report。
- quality report。
- repair history。
- final status: `pass`。

批量交付报告必须统计：

- 总论文数。
- 成功通过数。
- 未通过数。
- 每篇 note path。
- 每篇 gate 状态。
- 每篇 evidence coverage。
- 每篇 asset 状态。
- 每篇 repair 轮次。
- 未解决问题清单。

## 7. 需要调整的 skill 文件

### 7.1 `SKILL.md`

调整目标：让主 skill 明确区分单篇终稿与批量受控终稿。

建议新增或强化：

```markdown
## Production Modes

- `single-final`: generate one complete final seminar note for one paper.
- `batch-final-controlled`: generate multiple final seminar notes, but each paper must be isolated and pass source, blueprint-structure, evidence, asset, quality, and delivery gates before it is marked complete.
```

结构相关表述应改为：

```markdown
For final seminar notes, use `references/blueprint.md` as the single source of truth for the note structure and section responsibilities. Do not create or follow a parallel final-note structure. Batch mode must enforce the same blueprint through validation gates.
```

批量相关表述应改为：

```markdown
For batch-final-controlled runs, each paper must have its own source pack, evidence manifest, note path, assets directory, validation report, quality report, and repair status. Batch mode may directly produce final notes, but only notes that pass all gates may be counted as complete.
```

### 7.2 `references/review-pass.md`

调整目标：把 review pass 从“写完后看看”升级为可判定的质量 gate。

建议新增 `Final Note Gate Review`：

- blueprint structure status。
- evidence coverage status。
- asset status。
- content depth status。
- domain consistency status。
- terminology status。
- final decision: `pass | needs_minor_repair | needs_major_repair | needs_regeneration`。

每个失败项必须给出：

- 问题位置。
- 违反的规则。
- 需要补充的证据。
- 推荐返工级别。

### 7.3 `references/validation.md`

调整目标：把验证流程写成可执行 gate，而不是人工建议。

建议写入以下 gate 说明：

```text
preflight gate
source pack gate
evidence manifest gate
blueprint structure gate
evidence coverage gate
asset gate
quality gate
domain consistency gate
final delivery gate
```

建议命令形态：

```powershell
python scripts/validate_note.py "<note>" --assets-dir "<assets>" --json
python scripts/build_evidence_manifest.py --source-pack "<source-pack>" --out "<manifest>"
python scripts/validate_evidence_coverage.py --note "<note>" --evidence-manifest "<manifest>" --json
python scripts/audit_note_quality.py --note "<note>" --source-pack "<source-pack>" --evidence-manifest "<manifest>" --blueprint "references/blueprint.md" --json
```

### 7.4 `references/source-order.md`

调整目标：强化它与 evidence manifest / coverage gate 的关系。

建议补充：

- `required_in_final=true` 的证据不得遗漏。
- strict 模式下，主文证据顺序错误应判定失败。
- appendix / post-reference 证据不得混入主文证据时间线。
- 无法匹配的图片只能进入 manifest audit，不得进入最终正文。

### 7.5 `references/domain-skill.md`

调整目标：只增强领域质量判定，不新增结构。

建议补充 agent skill 论文的质量检查维度：

- skill architecture 类论文是否讲清框架、组件边界、调用流程。
- skill acquisition 类论文是否讲清 skill 来源、抽取、评估和泛化边界。
- skill retrieval / routing 类论文是否讲清索引、选择、上下文注入和失败模式。
- skill security / governance 类论文是否讲清威胁模型、攻击面、防御边界。
- skill internalization / LoRA 类论文是否讲清外部 skill 到模型行为的转化、蒸馏目标和保持/遗忘风险。
- HCI / user comprehension 类论文是否讲清用户研究设计、样本、任务和生态效度。

这些内容只作为领域 gate 的判定依据，不改变 `blueprint.md` 的结构。

## 8. 需要新增或增强的脚本

### 8.1 增强 `scripts/build_evidence_manifest.py`

当前已有该脚本，应优先增强而不是另起一套。

增强方向：

- 从 `full.md`、`content_list.json`、`manifest.json` 生成统一证据清单。
- 标注 `region`、`core_level`、`required_in_final`、`target_section`。
- 记录 asset 匹配置信度。
- 输出未匹配图片清单，但不要求进入最终稿。

### 8.2 新增 `scripts/validate_evidence_coverage.py`

职责：

- 对照 evidence manifest 检查终稿是否覆盖 required 证据。
- 检查核心证据是否出现在正确章节。
- 检查主文证据顺序是否正确。
- 检查 appendix / post-reference 证据是否进入补充材料章节。

输出示例：

```json
{
  "status": "pass",
  "required": 12,
  "covered": 12,
  "missing": [],
  "order_errors": [],
  "misplaced_items": []
}
```

### 8.3 增强 `scripts/validate_note.py`

职责：

- 继续负责图片链接、绝对路径、wiki embed、stale links、asset dump 等结构性检查。
- 增加 `--blueprint references/blueprint.md` 参数，执行 blueprint structure gate。
- 增加 JSON 输出中的 gate 分项。

建议参数：

```text
--blueprint <path>
--strict-assets
--fail-on-asset-dump
--json
```

### 8.4 新增 `scripts/audit_note_quality.py`

职责：

- 评估终稿是否达到组会可讲深度。
- 输出 repair status 和具体返工建议。
- 结合 source pack、evidence manifest、blueprint 进行判定。

输出示例：

```json
{
  "status": "needs_major_repair",
  "scores": {
    "blueprint_structure": 0.9,
    "evidence_depth": 0.55,
    "method_explanation": 0.7,
    "result_analysis": 0.45,
    "related_work": 0.4,
    "limitations": 0.35,
    "discussion": 0.5,
    "terminology": 0.8
  },
  "repair_plan": [
    {
      "section": "图表公式解释",
      "problem": "Table 2 only repeats caption and lacks baseline/metric interpretation",
      "repair_level": "major"
    }
  ]
}
```

### 8.5 增强 `scripts/batch_note_pipeline.py`

职责：把现有批量脚本升级为受控终稿流水线。

建议参数：

```powershell
python scripts/batch_note_pipeline.py `
  --mapping "<mapping.json>" `
  --output-root "<Obsidian target root>" `
  --production-mode batch-final-controlled `
  --blueprint "references/blueprint.md" `
  --max-parallel 3 `
  --repair-rounds 2 `
  --fail-on-quality-gate `
  --continue-on-fail `
  --final-report "<batch-delivery-report.md>"
```

脚本需要记录：

- 每篇当前 stage。
- 每篇 gate 输出。
- 每篇 repair 轮次。
- 每篇最终状态。
- 批量级成功/失败统计。

## 9. 自动返工策略

每篇论文最多默认 2 轮自动返工。

返工分级：

| 状态 | 含义 | 动作 |
| --- | --- | --- |
| `needs_minor_repair` | 局部格式、顺序、术语、少量解释不足 | 局部 patch 对应章节 |
| `needs_major_repair` | 证据遗漏、章节空心、实验解释不足 | 重写相关章节 |
| `needs_regeneration` | 论文类型错判、整体结构错位、严重浅摘要 | 从 source pack 重新生成整篇 |

返工规则：

- 每轮返工后必须重新跑失败 gate。
- 修复 evidence gate 失败时，不得只在文末补一段清单；必须回到 `blueprint.md` 对应章节。
- 修复 asset gate 失败时，不得把未匹配图片强行塞进正文。
- 修复 quality gate 失败时，应优先补证据解释和研究定位，而不是只润色语言。
- 两轮后仍未通过的笔记进入未完成清单，不得计入成功交付。

## 10. 批量并行策略

推荐小并行，而不是一次性让一个上下文连续生成 50 篇。

建议：

- 每批 2-3 篇并行。
- 每篇独立 source pack。
- 每篇独立 evidence manifest。
- 每篇独立 sidecar 状态文件。
- 主 agent 只负责汇总 gate 报告、触发返工、输出交付报告。
- subagent 只处理单篇或少量论文，不携带其他论文正文作为上下文。
- 每完成 5 篇生成阶段性质量报告，及时发现 gate 规则是否过松。

## 11. 对现有 50 篇笔记的处理建议

如果目标是重新获得高质量最终稿，建议在 skill 门控增强后使用 `batch-final-controlled` 重跑，而不是继续在旧稿上零散修补。

旧稿可以用于：

- 定位失败模式。
- 作为人工补充材料。
- 对照检查哪些论文最容易浅摘要化。
- 提供已有图片迁移结果参考。

旧稿不应作为唯一底稿，尤其是以下类型：

- 只有七个章节的浅层稿。
- 图表公式解释缺失的稿。
- wrong domain 的稿。
- 写入 MinerU asset dump 的稿。
- 只有结构没有证据分析的稿。

## 12. 实施阶段

### Phase 1: 门控规则落地

产物：

- 更新 `SKILL.md`，加入 `single-final` 与 `batch-final-controlled`。
- 更新 `review-pass.md`，加入终稿 gate 审稿状态。
- 更新 `validation.md`，写清 gate 顺序和命令。
- 更新 `source-order.md`，强化 evidence manifest 与 strict order 规则。

目标：

- 不改 `blueprint.md` 结构内容。
- 让 `blueprint.md` 从写作参考变成验证 gate 的依据。

### Phase 2: 验证脚本增强

产物：

- 增强 `build_evidence_manifest.py`。
- 增强 `validate_note.py`。
- 新增 `validate_evidence_coverage.py`。
- 新增 `audit_note_quality.py`。

目标：

- 自动区分“文件存在”“结构存在”“证据覆盖”“内容达标”。

### Phase 3: 批量流水线升级

产物：

- 增强 `batch_note_pipeline.py`。
- 增加 per-paper sidecar schema。
- 增加 batch delivery report 模板。

目标：

- 批量模式直接产出 Obsidian 终稿。
- 未通过 gate 的笔记不进入成功计数。

### Phase 4: 小样本试点

建议试点：

- 1 篇 survey / overview 类。
- 1 篇 method / system 类。
- 1 篇 agent skill / security / internalization 类。

验证目标：

- 是否严格复用 `blueprint.md`。
- 是否能识别章节空心。
- 是否能发现 evidence 漏项。
- 是否能自动触发返工。

### Phase 5: 50 篇全量重跑

目标：

- 全量保存到 Obsidian。
- 每篇保留 source pack、evidence manifest、validation report、quality report。
- 输出全量交付报告。
- 明确列出未通过笔记及原因。

## 13. 优先级

P0：

1. 更新 `SKILL.md` 的生产模式和 blueprint 单一结构契约。
2. 更新 `review-pass.md` 的 gate 审稿状态。
3. 更新 `validation.md` 的 gate 顺序。
4. 增强 `validate_note.py` 的 blueprint structure gate 与 asset gate。
5. 增强 `build_evidence_manifest.py`。

P1：

1. 新增 `validate_evidence_coverage.py`。
2. 新增 `audit_note_quality.py`。
3. 增强 `batch_note_pipeline.py` 的 repair loop 和 sidecar 状态。
4. 更新 `source-order.md` 的 strict evidence gate 规则。

P2：

1. 增强 `domain-skill.md` 的领域质量判定。
2. 增加 smoke tests。
3. 建立 50 篇批量交付报告模板。

## 14. 最终结论

新的优化方向应是：

```text
复用 references/blueprint.md 作为唯一终稿结构契约
+ 每篇独立 source pack
+ 每篇独立 evidence manifest
+ blueprint structure / evidence / asset / quality / domain / delivery gates
+ 自动返工
+ 全量交付报告
```

这比重新设计一个固定结构更符合当前需求。真正要加强的不是章节模板，而是批量生成时的判定门控：只有当每篇笔记在结构、证据、资产、深度和领域一致性上都通过 gate，才能算作高质量 Obsidian 组会分享最终稿。
