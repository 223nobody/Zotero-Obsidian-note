# zotero-group-meeting-note 本轮修改清单、优化情况与下一步方向

更新时间：2026-06-29

本文档用于记录本轮对 `zotero-group-meeting-note` skill 的实际优化内容、当前效果、验证结果、已知风险和下一步优化方向。它不是新的终稿结构规范，也不替代 `zotero-group-meeting-note/references/blueprint.md`。当前优化的核心原则是：继续复用 `blueprint.md` 作为唯一终稿结构契约，把重点放在批量生成时的隔离、判定门控、质量审稿、返工闭环和交付统计上。

## 一、优化目标

本轮优化解决的不是“单篇生成能力不足”，而是“批量调用时质量收束不够严格”的问题。根据前面对优秀单篇笔记和批量笔记的对比，当前 skill 在单篇深度分析时已经能产出较高质量内容；批量生成效果变差，主要来自以下原因：

- 多篇论文共享同一上下文时，模型容易把所有论文压缩为同质化的浅层七章稿。
- 批量流程缺少逐篇 source pack，导致每篇笔记没有稳定、隔离的论文材料边界。
- 图、表、公式、实验结果没有成为硬约束，导致正文看似完整但证据覆盖不足。
- 校验脚本过去更偏“文件是否存在、链接是否可用”，不足以判定“是否达到组会分享深度”。
- 批量完成统计容易把“生成了 md 文件”误当成“通过最终质量门控”。
- 返工状态没有分级，导致明显不合格的笔记仍可能进入完成列表。

因此，本轮重构目标被限定为：

- 保留并复用 `references/blueprint.md` 的固定终稿结构。
- 新增 `single-final` 与 `batch-final-controlled` 两种生产模式。
- 批量模式下每篇论文独立处理、独立校验、独立报告。
- 只有通过 source、blueprint、evidence、asset、quality、domain、delivery gates 的笔记，才能计入最终完成。
- 让后续 50 篇论文重跑时具备可追踪、可返工、可审计的交付基础。

## 二、整体修改清单

### 1. `zotero-group-meeting-note/SKILL.md`

已完成的修改：

- 新增 `Production Modes`：
  - `single-final`：单篇论文直接生成完整组会终稿。
  - `batch-final-controlled`：多篇论文批量生成，但每篇必须作为独立单元通过完整门控。
- 明确 `references/blueprint.md` 是终稿结构与章节职责的唯一来源，不再设计平行结构。
- 批量流程阶段从原来的 `preflight -> parse_cache -> evidence_manifest -> draft -> review -> validate -> cleanup_report` 扩展为：

```text
preflight -> parse_cache -> evidence_manifest -> draft -> review -> quality -> validate -> cleanup_report -> final_delivery
```

- 明确批量模式不得把一篇论文的正文草稿作为另一篇论文的上下文，只允许共享 batch manifest、sidecar 状态和 gate 报告。
- 新增最终质量报告要求：当存在 source pack 时，应运行 `scripts/audit_note_quality.py`，并把 `needs_minor_repair`、`needs_major_repair`、`needs_regeneration` 视为未完成状态。
- 新增最终交付要求：如果生成了质量报告，最终质量状态必须为 `pass`，否则不得把该笔记计为已完成终稿。

优化效果：

- skill 的主流程已经从“批量生成文件”转向“批量受控终稿交付”。
- 避免把章节数量合格误判为内容质量合格。
- 后续调用 skill 时，主 agent 和 subagent 都有更清楚的完成判定边界。

### 2. `zotero-group-meeting-note/references/review-pass.md`

已完成的修改：

- 新增 `Final Note Gate Review`。
- 引入统一判定状态：

```text
pass | needs_minor_repair | needs_major_repair | needs_regeneration
```

- 明确最终审稿需要检查：
  - `blueprint_structure`
  - `evidence_coverage`
  - `asset_status`
  - `content_depth`
  - `domain_consistency`
  - `terminology`
- 明确失败项必须给出问题位置、违反规则、缺失证据或源文线索、推荐返工级别。
- 明确批量模式下未通过 gate 的笔记不能计入完成终稿。

优化效果：

- review pass 不再只是“读一遍看看”，而是有明确状态机的质量判定。
- 后续可以依据质量报告决定局部修、章节重写还是整篇重生。

### 3. `zotero-group-meeting-note/references/validation.md`

已完成的修改：

- 新增最终笔记 gate sequence：
  1. `preflight gate`
  2. `source pack gate`
  3. `evidence manifest gate`
  4. `blueprint structure gate`
  5. `evidence coverage gate`
  6. `asset gate`
  7. `quality gate`
  8. `domain consistency gate`
  9. `final delivery gate`
- 更新 `validate_note.py` 示例命令，加入 `--blueprint references/blueprint.md`。
- 新增 `audit_note_quality.py` 示例命令，用于生成内容深度质量报告。
- 明确 `needs_minor_repair`、`needs_major_repair`、`needs_regeneration` 都不是完成状态。

优化效果：

- 验证流程从单一 Markdown 检查，升级为多 gate 判定。
- 后续批量生成可以输出逐篇 validation report 和 quality report。

### 4. `zotero-group-meeting-note/references/source-order.md`

已完成的修改：

- 新增 `Strict Evidence Gate Rules`。
- 明确 `required_in_final=true` 的 manifest 证据必须进入终稿，除非显式标记为待核对。
- 主文证据必须进入 `blueprint.md` 规定的主文图表公式解释章节。
- appendix / post-reference 证据不得混入主文证据时间线。
- strict mode 下，主文 Figure / Table / Equation / Algorithm / Prompt / Case 顺序错误会被视为 gate 失败。
- 匹配到资产的证据必须在该证据附近引用图片，不能只在文末资源索引中出现。
- 无法匹配的 parser 图片只能留在 manifest 或 audit report 中，不应为了凑齐图片数量写入终稿。

优化效果：

- 图表公式覆盖从“写作建议”变成了可校验约束。
- 可以更有效防止批量笔记只贴 caption、漏掉关键实验表格、或把图片堆到文末。

### 5. `zotero-group-meeting-note/references/domain-skill.md`

已完成的修改：

- 新增 `Domain Consistency Gate`。
- 对 agent-skill 相关论文按方向给出判定重点：
  - skill architecture
  - skill acquisition
  - skill retrieval / routing
  - skill composition / graph
  - skill security / governance
  - skill internalization / LoRA / latent-skill
  - HCI / user-comprehension skill papers
- 明确错判论文类型时的失败级别：
  - 漏掉生命周期阶段或证据类型：`needs_major_repair`
  - 方法、系统、安全、survey 等类型明显错判：`needs_regeneration`

优化效果：

- 避免 agent skill 论文全部被写成泛泛“技能提升 LLM agent”的摘要。
- 后续可依据论文类型调整分析重点，但不改变 `blueprint.md` 的固定结构。

## 三、脚本层修改清单

### 1. `scripts/build_evidence_manifest.py`

已完成的修改：

- `content_list` 参数从必填位置参数改为可选，允许通过 `--source-pack` 读取。
- 新增 `--source-pack`，可从逐篇 source pack 中读取：
  - `content_list`
  - `assets_dir`
  - `full_md`
  - `title`
  - `note_path`
  - `note_assets_dir`
- evidence manifest 新增或增强字段：
  - `paper_key`
  - `title`
  - `note_path`
  - `note_assets_dir`
  - `source_pack_path`
  - `target_section`
  - `required_in_final`
- 新增 `required_in_final_for(...)`，根据证据类型、区域和置信度判断是否必须进入终稿。

优化效果：

- 每篇论文可以形成独立 evidence manifest。
- 证据是否必须进入终稿不再完全依赖人工判断。
- 后续 `validate_note.py` 和 `audit_note_quality.py` 可以基于 manifest 做更强校验。

### 2. `scripts/validate_note.py`

已完成的修改：

- 新增 `--blueprint` 参数，用于执行 blueprint structure gate。
- 新增 `--strict-assets` 参数，可把远程图片、非 `assets/...` 相对图片等 warning 升级为 error。
- 新增 blueprint heading 提取与结构检查逻辑：
  - 从 `blueprint.md` 中读取结构契约。
  - 检查终稿 H1 和主要 H2 是否按顺序出现。
  - 对参考文献、附录、补充材料等可选章节做特殊处理。
- evidence coverage 检查增强：
  - 不再只检查 high-confidence 资产，也检查 `required_in_final` 条目。
  - 当 required evidence 未在正文出现时，生成 `missing_required_evidence`。
  - 当 high-confidence evidence 未引用时，生成 `missing_evidence_reference`。
  - 支持 copy-map authoritative 模式。
  - 检查证据窗口附近是否有对应本地图片。
  - 检查主文证据顺序，生成 `evidence_order_error`。

优化效果：

- 能发现“章节结构不遵守 blueprint”的问题。
- 能发现“关键图表公式在 manifest 中存在但终稿没有解释”的问题。
- 能发现“图片存在但没有放到对应证据附近”的问题。
- 能更严格区分可交付笔记和半成品笔记。

### 3. 新增 `scripts/validate_evidence_coverage.py`

已完成的能力：

- 作为 evidence coverage 专用包装脚本调用 `validate_note.py`。
- 支持参数：
  - `--note`
  - `--evidence-manifest`
  - `--copy-map`
  - `--qa-report`
  - `--strict`
  - `--json`
- 只提取 evidence 相关错误与警告：
  - `missing_copy_map_entry`
  - `missing_required_evidence`
  - `missing_evidence_reference`
  - `missing_evidence_asset_link`
  - `misplaced_evidence_asset_link`
  - `evidence_order_error`
- strict 模式下 evidence warnings 会导致失败。

优化效果：

- 可以把“证据覆盖是否合格”从综合 Markdown 校验中单独抽出来。
- 适合批量生成时快速定位图表公式缺失问题。

### 4. 新增 `scripts/audit_note_quality.py`

已完成的能力：

- 对最终笔记做内容深度审计。
- 输入：
  - `--note`
  - `--source-pack`
  - `--evidence-manifest`
  - `--blueprint`
  - `--json`
- 输出：
  - `status`
  - `scores`
  - `repair_plan`
  - `manifest_stats`
  - `summary`
- 目前检查维度包括：
  - `blueprint_structure`
  - `core_conclusion`
  - `problem_positioning`
  - `innovation_analysis`
  - `method_explanation`
  - `evidence_depth`
  - `related_work`
  - `limitations_discussion`
  - `terminology`
  - `evidence_coverage`
- 根据分数与 repair plan 输出：
  - `pass`
  - `needs_minor_repair`
  - `needs_major_repair`
  - `needs_regeneration`

优化效果：

- 第一次把“内容丰富程度与专业程度”纳入自动 gate。
- 可以识别短稿、空心章节、缺少相关工作、缺少局限讨论、证据标签缺失等问题。
- 为后续自动返工提供结构化 repair plan。

当前限制：

- 该脚本仍是启发式质量审计，不等价于真实语义阅读。
- 对中文标题、不同论文类型、不同领域的适配还需要用真实 50 篇笔记继续校准。
- 后续应把它从“长度和关键词启发式”升级为“blueprint 章节职责 + manifest 证据 + source pack 语义线索”的更强判定。

### 5. `scripts/batch_note_pipeline.py`

已完成的修改：

- 新增全局脚本引用 `AUDIT_QUALITY`。
- stages 新增：
  - `quality`
  - `final_delivery`
- 新增参数：
  - `--production-mode`
  - `--blueprint`
  - `--final-report`
  - `--fail-on-quality-gate`
- 新增 per-paper source pack 写入：
  - 默认写到 `work_dir/source-packs/<paper-key>.source-pack.json`
  - 记录 paper key、title、PDF、full.md、content_list、manifest、assets、note、copy-map 等路径。
- `run_manifest(...)` 支持把 source pack 传给 `build_evidence_manifest.py`。
- `run_validation(...)` 支持把 blueprint 传给 `validate_note.py`。
- 新增 `run_quality(...)`：
  - 调用 `audit_note_quality.py`
  - 写入 `<paper-key>.quality.json`
  - 把 status 和 repair_plan 写回 sidecar。
- 新增 `final_delivery_status(...)`：
  - 要求 validation report、quality report、asset report 都存在。
  - 要求 validation status 为 `pass`。
  - 要求 quality status 为 `pass`。
  - 对资产状态做基础一致性判断。
- 新增 `write_final_report(...)`：
  - 输出批量最终交付 Markdown 报告。
  - 统计 total、passed、failed_or_unfinished。
  - 逐篇列出 final、quality、validation、cleanup、source pack 和 issue。

优化效果：

- 批量流水线已经具备“生成文件”和“通过最终交付”分离的基础。
- 每篇论文的 source pack、quality report、validation report、asset report 可以被 sidecar 串起来。
- 适合后续用在 50 篇笔记全量重跑中，自动生成批量交付报告。

### 6. `scripts/update_pipeline_sidecar.py`

已完成的修改：

- stages 新增：
  - `quality`
  - `final_delivery`
- paths 新增：
  - `quality_report_path`
- sidecar schema 新增：
  - `quality`
- 支持命令行参数 `--quality-report-path`。

优化效果：

- sidecar 可以记录质量 gate 结果。
- 后续可以在批量报告中清楚区分“validate 通过但 quality 未通过”的笔记。

### 7. `scripts/smoke_test_skill.py`

已完成的修改：

- 覆盖新增脚本：
  - `validate_evidence_coverage.py`
  - `audit_note_quality.py`
- 检查 evidence manifest 新字段：
  - `target_section`
  - `required_in_final`
- 新增质量审计测试：
  - 短 smoke note 不应通过 quality gate。
  - quality audit 应返回 repair status。
- 新增 strict evidence gate 测试：
  - 缺失资产时 strict evidence gate 应失败。
- 扩展 batch pipeline smoke test：
  - stage 包含 `quality`。
  - 生成 `batch-final-report.md`。
  - sidecar 记录 quality gate 失败。
  - sidecar 记录 `quality_report_path`。

优化效果：

- 新增门控不是只写在文档里，而是进入 smoke test。
- 可以防止后续脚本改动破坏 evidence / quality / batch sidecar 的基本行为。

## 四、当前验证结果

已执行验证：

```powershell
python -m py_compile `
  "C:\code\Zotero-Obsidian-note\zotero-group-meeting-note\scripts\audit_note_quality.py" `
  "C:\code\Zotero-Obsidian-note\zotero-group-meeting-note\scripts\validate_evidence_coverage.py" `
  "C:\code\Zotero-Obsidian-note\zotero-group-meeting-note\scripts\batch_note_pipeline.py" `
  "C:\code\Zotero-Obsidian-note\zotero-group-meeting-note\scripts\validate_note.py" `
  "C:\code\Zotero-Obsidian-note\zotero-group-meeting-note\scripts\build_evidence_manifest.py"
```

结果：通过，未输出编译错误。

```powershell
python "C:\code\Zotero-Obsidian-note\zotero-group-meeting-note\scripts\smoke_test_skill.py"
```

结果：

```text
smoke tests passed
```

尚未执行的验证：

- 尚未用真实 50 篇论文重新跑完整 `batch-final-controlled` 流程。
- 尚未对真实 Obsidian 输出逐篇检查 `quality_report.status == pass`。
- 尚未验证自动返工闭环，因为当前实现更偏“发现问题并报告”，还没有完整自动重写失败章节。
- 尚未做 subagent 独立前向测试。下一步应让 subagent 在只看到 skill 与单篇 source pack 的情况下生成或修复笔记，验证 skill 是否能泛化。

## 五、当前优化情况评估

### 已明显改善的部分

- `blueprint.md` 继续作为唯一固定结构，不再引入不合适的 SkCC-grade 平行结构。
- 批量模式从宽松生成升级为受控生产模式。
- 每篇论文有 source pack 的概念，可减少跨论文上下文污染。
- 图表公式证据从人工提醒升级为 manifest + validation gate。
- 最终质量从人工主观判断升级为 quality report 状态。
- sidecar 能记录 quality 与 final delivery 状态。
- batch pipeline 可以输出最终交付报告，避免把失败笔记混入成功清单。

### 仍然不足的部分

- `audit_note_quality.py` 目前仍是启发式脚本，不能完全替代深度语义审稿。
- 当前 pipeline 已加入 `quality` 与 `final_delivery`，但自动返工还没有形成真正闭环。
- domain consistency 规则已写入 reference，但尚未被脚本强校验。
- quality gate 的阈值需要用真实样本校准，否则可能出现误杀或漏判。
- 真实 50 篇笔记中可能存在路径、标题长度、MinerU 资产匹配异常，这些还需要在全量试跑中暴露。
- 当前工作区显示 `scripts/__pycache__/*.cpython-314.pyc` 为删除状态，说明缓存文件可能被版本控制跟踪。建议后续清理版本控制策略，把 `__pycache__` 从源码交付中移除或恢复后加入 `.gitignore`。

## 六、建议的下一步优化方向

### P0：先把自动返工闭环补齐

下一步最重要的不是继续增加提示词，而是让失败 gate 自动进入返工流程。

建议实现：

- 在 `batch_note_pipeline.py` 中加入 `--repair-rounds`。
- 根据 quality report 的状态分级处理：
  - `needs_minor_repair`：局部 patch 对应章节。
  - `needs_major_repair`：重写相关章节，例如图表公式解释、创新点、方法机制、相关工作。
  - `needs_regeneration`：基于 source pack 重生整篇。
- 每轮返工后重新运行失败 gate。
- 两轮后仍未通过的笔记进入 unresolved list，不计入成功交付。

### P1：用真实样本校准 `audit_note_quality.py`

建议选 6 到 8 篇真实论文作为校准集：

- 2 篇当前效果较好的笔记。
- 2 篇只有七个章节但内容空心的笔记。
- 1 到 2 篇图表公式明显缺失的笔记。
- 1 到 2 篇 agent skill / security / system 类型较强的论文。

校准重点：

- 章节识别是否准确。
- quality score 是否能区分短稿、浅稿、合格稿。
- repair_plan 是否能指出真实可执行的返工位置。
- `pass` 阈值是否过松或过严。

### P1：把 domain consistency 从 reference 规则变成脚本 gate

建议新增或增强脚本逻辑：

- 读取 `source_pack` 或全文，初步判断论文类型。
- 对 agent skill 论文判断方向：
  - architecture
  - acquisition
  - retrieval/routing
  - security/governance
  - internalization
  - HCI/user study
- 检查对应章节是否解释了该类型必须解释的对象。
- 输出 `domain_status` 和 `domain_repair_plan`。

### P1：实现真实 50 篇全量试跑

建议流程：

```text
1. 为 50 篇论文建立 mapping.json
2. 每篇生成 source_pack.json
3. 每篇生成 evidence_manifest.json
4. 逐篇或小批量生成终稿
5. 运行 validate_note.py
6. 运行 validate_evidence_coverage.py
7. 运行 audit_note_quality.py
8. 不通过则进入 repair loop
9. 输出 batch-final-report.md
10. 人工抽查 pass 样本和 fail 样本
```

建议小批量并发，不要一次把 50 篇放入同一个上下文。每个 subagent 最多处理 1 到 2 篇，并且只拿到该论文的 source pack、evidence manifest、blueprint 与必要 reference。

### P2：把最终交付报告做成更强的审计面板

建议扩展 `batch-final-report.md`：

- 每篇 note path。
- 每篇 assets path。
- 每篇 source pack path。
- 每篇 evidence manifest path。
- validation status。
- quality status。
- domain status。
- evidence coverage 数量。
- image link 数量。
- repair rounds。
- unresolved issue。
- 是否计入最终成功。

这样后续可以直接从报告定位哪一篇需要人工复核。

### P2：处理版本控制与编码卫生

建议：

- 确认 `__pycache__` 是否应该被版本控制跟踪。
- 若不应该，删除缓存文件并加入 `.gitignore`。
- 若历史上已经跟踪，需要用一次专门提交清理。
- 检查中文文档在 PowerShell 输出中的编码显示问题，确保实际文件以 UTF-8 保存。
- 对新脚本中的中文关键词匹配做 UTF-8 语义级测试，避免终端 codepage 或历史文件编码影响质量 gate。

## 七、对当前 50 篇笔记的建议处理方式

不建议继续在当前不合格旧稿上零散修补所有 50 篇。更合理的路线是：

1. 先完成当前 skill 的 gate 与 repair loop。
2. 用 3 到 5 篇真实论文做小样本试跑。
3. 校准 `audit_note_quality.py` 和 evidence gate。
4. 再用 `batch-final-controlled` 逐篇或小批量重跑 50 篇。
5. 对未通过 gate 的笔记进入自动返工。
6. 最后只把 `final_status=pass` 的笔记计入 Obsidian 最终交付。

旧稿仍然有价值，但更适合作为问题定位材料，而不是作为唯一底稿继续硬修。尤其是以下类型应优先重生：

- 只有七个章节但每章内容很短。
- 缺少图表公式解释。
- 图表公式只复述 caption。
- 相关工作只是文献堆砌。
- 局限讨论是空泛套话。
- 写入 MinerU asset dump 或图片资源索引。
- 论文类型判断错误。

## 八、本轮结论

本轮优化已经把 `zotero-group-meeting-note` 从“依赖提示词自觉遵守质量要求”推进到“通过脚本和 sidecar 强制记录质量状态”的阶段。最关键的变化不是新增结构模板，而是把原有 `blueprint.md` 变成可验证的结构契约，并在批量流程中加入 evidence、asset、quality 和 final delivery gates。

当前项目已经具备继续向高质量批量终稿演进的基础，但还不能直接宣称 50 篇真实论文都会达到优秀单篇笔记水准。下一步应优先完成自动返工闭环和真实样本校准，然后再进行全量重跑。
