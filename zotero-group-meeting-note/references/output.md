# Output Rules

Use this file whenever the skill writes or updates a Zotero-compatible note file, a Zotero note, an Obsidian note, or assets for a group-meeting paper note. These rules are part of the output contract, not optional formatting advice.

## Default Target

If the user does not specify an output location, write the Obsidian note to the default Obsidian vault:

```text
~/Documents/Obsidian Vault/组会分享/<yy-M-d>/<论文标题>.md
```

The default vault can be overridden with `--obsidian-vault` or the environment variable `ZOTERO_GROUP_MEETING_OBSIDIAN_VAULT`.

Portable example:

```text
~/Documents/Obsidian Vault/组会分享/26-4-20/Adversity-aware Few-shot Named Entity Recognition via Augmentation Learning.md
```

Create an `assets/` folder beside the note:

```text
~/Documents/Obsidian Vault/组会分享/<yy-M-d>/assets/
```

The date folder uses the request date in the user's local timezone unless the user explicitly specifies another date. The format is non-padded `yy-M-d`, for example `26-4-20`.

## Filename Contract

Default filesystem filename:

```text
<论文标题>.md
```

Use this priority for `<论文标题>`:

1. User-specified note filename or paper title.
2. Zotero item title.
3. PDF metadata title.
4. Attachment filename stem.

Do not auto-generate slug filenames such as:

```text
towards-expressive-spectral-temporal-graph-neural-networks-for-time-series-forecasting-group-meeting-2026-04-28.md
```

Do not append `group-meeting`, `组会分享`, or the date to the filename unless the user explicitly asks for that pattern.

Sanitize only characters that are invalid or risky for the target filesystem:

- Windows invalid characters: `< > : " / \ | ? *`
- Replace invalid characters inside the paper title with `-`.
- Trim leading/trailing spaces and trailing dots.
- Preserve normal spaces, capitalization, and readable English or Chinese titles.
- If the final filename is too long, keep the readable beginning and append a short hash.

## Note Title And Body

The Obsidian filename should normally be `<论文标题>.md`, but the H1 inside the file should be:

```markdown
# 组会分享笔记：<论文标题>
```

If the user asks for a custom visible title, use that title instead.

Do not add YAML frontmatter by default. Do not add trailing signatures such as `Written by LLM-for-Zotero`. Keep the body as clean Markdown that works in both Zotero and Obsidian.

The note content should follow `references/blueprint.md`: emphasize innovation, evidence, the unified source-ordered figure/table/formula evidence timeline, conclusion data, related-work comparison, limitations, and discussion questions.
Before final delivery, run the post-draft review in `references/review-pass.md` so evidence coverage, source ordering, terminology, and spoken readability are cleaned up.

## Deterministic Script

Prefer `scripts/prepare_output.py` before writing files. It creates the required folders, returns safe paths, and can copy assets.

Default call:

```powershell
python scripts/prepare_output.py --article-filename "<论文标题或PDF文件名>" --date "<YYYY-MM-DD>" --create-note-stubs
```

For the desired default Obsidian structure:

```powershell
python scripts/prepare_output.py `
  --article-filename "Adversity-aware Few-shot Named Entity Recognition via Augmentation Learning.pdf" `
  --date "2026-04-20" `
  --obsidian-vault "$env:USERPROFILE\Documents\Obsidian Vault" `
  --create-note-stubs
```

This returns an Obsidian path like:

```text
...\Documents\Obsidian Vault\组会分享\26-4-20\Adversity-aware Few-shot Named Entity Recognition via Augmentation Learning.md
```

If the user specifies an exact output folder, use:

```powershell
python scripts/prepare_output.py `
  --article-filename "<论文标题>" `
  --obsidian-dir "$env:USERPROFILE\Documents\Obsidian Vault\组会分享\26-4-20" `
  --note-filename "Adversity-aware Few-shot Named Entity Recognition via Augmentation Learning.md" `
  --create-note-stubs
```

If the user specifies a full Obsidian note path, use `--obsidian-note-path`; this overrides the vault, date folder, output folder, and filename:

```powershell
python scripts/prepare_output.py `
  --article-filename "<论文标题>" `
  --obsidian-note-path "$env:USERPROFILE\Documents\Obsidian Vault\组会分享\26-4-20\Adversity-aware Few-shot Named Entity Recognition via Augmentation Learning.md" `
  --create-note-stubs
```

If the user specifies a full Zotero-compatible Markdown path, use `--zotero-note-path`; this overrides `--current-dir` and `--note-filename` for the Zotero fallback copy.

## Customization Options

Respect explicit user customization:

- Custom Obsidian vault: `--obsidian-vault "<vault root>"`
- Custom Obsidian vault by environment: `$env:ZOTERO_GROUP_MEETING_OBSIDIAN_VAULT="<vault root>"`
- Custom exact folder: `--obsidian-dir "<folder>"`
- Custom exact Obsidian note path: `--obsidian-note-path "<file.md>"`
- Custom filename: `--note-filename "<filename.md>"`
- Custom Zotero-compatible fallback path: `--zotero-note-path "<file.md>"`
- Custom visible H1 title: `--note-title "<title>"`
- Custom date folder: `--date "2026-04-20"` or `--date "26-4-20"`
- Keep file extension from source paper: `--keep-extension`
- Do not create Zotero-compatible current-folder copy: `--no-zotero-file`
- Do not create Obsidian output: `--no-obsidian`

When a user gives both a full file path and a separate filename, the full file path wins. Use `--obsidian-note-path` for a full Obsidian file path and `--zotero-note-path` for a full Zotero-compatible fallback file path.

## Zotero-Compatible Copy

If direct Zotero note-writing tools are available, create or update the note attached to the active Zotero item. If direct Zotero writing is unavailable, a Markdown file may be written as a Zotero-compatible fallback.

Zotero-compatible note requirements:

- Use the same clean Markdown body as the Obsidian note unless the user asks otherwise.
- Start with `# 组会分享笔记：<论文标题>` or the user's custom title.
- Do not include Obsidian-only syntax such as wiki links, Dataview blocks, callouts, or transclusions.
- Do not include YAML frontmatter unless the user explicitly requests it.

## Asset Handling

Use the Obsidian `assets/` folder for images copied or exported during note creation. Prefer deterministic readable filenames:

```text
figure-01-skcc-workflow-complexity.jpg
figure-02-skcc-compilation-pipeline.jpg
table-03-skcc-pass-rate-improvement.jpg
formula-04-skcc-loss-objective.png
```

Put the asset type and original-paper number first, followed by a short paper token and topic slug:

```text
<figure|table|equation|formula>-<two-digit-number>-<paper-token>-<topic>.ext
```

For appendix, supplementary, or post-reference evidence, insert `supp` after the paper token, for example `table-06-skcc-supp-anti-skill-rules.jpg`. Avoid repeating the label inside the filename, such as `figure-figure-1.jpg` or `table-table-3.jpg`.

When assets are already available as files, copy only the matched evidence assets through:

```powershell
python scripts/prepare_output.py --article-filename "<论文标题>" --asset ".\figure1.png" --asset-dir ".\paper-assets"
```

When a MinerU or Markdown source already contains local image links, use `scripts/collect_assets.py` to copy candidate images into the note assets folder and optionally rewrite image links:

```powershell
python scripts/collect_assets.py ".\paper.md" `
  --assets-dir "$env:USERPROFILE\Documents\Obsidian Vault\组会分享\26-4-20\assets" `
  --rewrite-markdown ".\paper-assets-rewritten.md"
```

If the source or existing Obsidian note uses wiki embeds such as `![[Pasted image 20260610105318.png]]`, pass the vault root so the script can resolve and rewrite them:

```powershell
python scripts/collect_assets.py ".\paper.md" `
  --assets-dir "$env:USERPROFILE\Documents\Obsidian Vault\组会分享\26-4-20\assets" `
  --vault-root "$env:USERPROFILE\Documents\Obsidian Vault" `
  --rewrite-markdown ".\paper-assets-rewritten.md"
```

Use relative paths in the Obsidian note:

```markdown
![Figure 2 方法总体框架图](assets/figure-02-skcc-compilation-pipeline.jpg)
```

Place each matched image directly in the Figure / Table / Equation / Prompt / Case Study entry it belongs to. Do not leave matched evidence images only in a generic "MinerU 图片资源完整性索引" section. Unmatched, duplicate, page-header/footer, bibliography, or no-caption crops must be kept out of the final note and recorded only in an internal checklist or external manifest when needed.

When the source comes from `paper-search-mcp`, treat the parser `assets_dir` as an input asset root, not as the final note asset location or a list that must be fully represented. Copy matched images/table crops/formula crops into the note-local `assets/` folder, then use relative Markdown links such as `assets/<file>`. Keep the MCP `paper_key`, `full_md_path`, `content_list_path`, and `assets_dir` only as provenance or debugging information, not as absolute image links in the final Obsidian note.

When an evidence manifest exists, copy matched assets and write a copy map before drafting:

```powershell
python scripts/prepare_output.py `
  --article-filename "<论文标题>" `
  --obsidian-dir "$env:USERPROFILE\Documents\Obsidian Vault\组会分享\26-4-20" `
  --sync-from-manifest "<evidence-manifest.json>" `
  --copy-map "<copy-map.json>"
```

Draft from the copy map's `markdown` fields. The copy map records each manifest `item_key`, copied destination, and SHA256 hashes so validators can distinguish same-basename assets from different source folders.

If an image cannot be extracted, keep an explicit placeholder rather than silently dropping it.

## Asset Audit JSON

After drafting, write a machine-readable asset report instead of adding an audit section to the note:

```powershell
python scripts/audit_note_assets.py "<note-path>" `
  --output "<note-dir>\asset-report.json"
```

The report records image link count, resolved link count, total assets, referenced assets, unused assets, duplicate hash count, duplicate groups, and any deleted files. For cleanup, prefer a dry report first. If the user approves cleanup or the batch policy allows it:

```powershell
python scripts/audit_note_assets.py "<note-path>" `
  --output "<note-dir>\asset-report-after-cleanup.json" `
  --scan-sibling-notes `
  --delete-duplicate-unused
```

Use `--scan-sibling-notes` whenever multiple notes share the same date-level `assets/` directory. Use `--delete-unused` only when you are certain no unreferenced file in the note-local `assets/` directory is needed by another note. For batch runs, prefer per-paper asset subdirectories or sibling-note scanning before deleting anything.

## Batch Sidecar JSON

For multiple papers, create one sidecar JSON per paper. Keep it outside the note body, usually beside the note or under a batch working directory:

```powershell
python scripts/update_pipeline_sidecar.py `
  --sidecar "<work-dir>\sidecars\<paper-key>.json" `
  --paper-key "<paper-key>" `
  --pdf-path "<pdf-path>" `
  --source-md "<full-md-path>" `
  --content-list "<content-list-path>" `
  --assets-dir "<parser-assets-dir>" `
  --note-path "<note-path>" `
  --stage preflight --status complete
```

To run the deterministic stages for a batch file, prepare a JSON list or `{ "papers": [...] }` object with fields such as `paper_key`, `title`, `pdf_path`, `source_md`, `content_list`, `assets_dir`, and `note_path`, then run:

```powershell
python scripts/batch_note_pipeline.py "<batch.json>" `
  --work-dir "<batch-work-dir>" `
  --stages preflight,parse_cache,evidence_manifest,draft,review,validate,cleanup_report `
  --strict-evidence `
  --continue-on-error
```

This helper does not draft prose or replace the LLM/manual review pass. It creates sidecars, checks parse/cache artifacts, builds evidence manifests, records draft/review checkpoints, writes validation reports, and writes asset audit reports so Codex can resume paper-by-paper. Its cleanup report stage scans sibling Markdown files in the same folder before classifying assets as unused. Use `--strict-evidence` for batch delivery so missing or misplaced manifest assets fail the stage.

Update the sidecar after each stage: `preflight`, `parse_cache`, `evidence_manifest`, `draft`, `review`, `validate`, and `cleanup_report`. Store report paths and counts with `--set`, for example:

```powershell
python scripts/update_pipeline_sidecar.py `
  --sidecar "<sidecar.json>" `
  --copy-map-path "<copy-map.json>" `
  --asset-report-path "<asset-report.json>" `
  --validation-report-path "<validation-report.json>" `
  --stage validate --status complete `
  --set counts.image_link_count=15 `
  --set counts.unused_assets_count=0
```

## Failure Patterns To Avoid

Before final delivery, fix these mistakes if they appear:

- The note is saved directly under `组会分享/` without a date folder.
- The filename is a lowercase slug rather than the readable paper title.
- The filename includes `group-meeting` or a date suffix without user request.
- The note starts with YAML frontmatter when the user did not ask for it.
- The note ends with model/plugin signatures.
- The body ignores the blueprint and becomes only an abstract summary.
- Evidence images are left as `![[Pasted image ...]]` wiki embeds instead of copied relative `assets/...` links.
- Evidence images point to absolute `paper-search-mcp` cache or `<pdf>_mineru/assets` paths instead of note-local relative `assets/...` links.
- Matched Figure/Table/Equation images are only dumped into a final asset index instead of placed beside their corresponding explanations.
- The final note contains `## 附录：MinerU 图片资源完整性索引`, `MinerU asset`, `MinerU extra crop`, or a filename-only list of `assets/...` images. Delete that section; move only genuinely relevant images into their evidence entries.

## Final Verification Report

After writing, verify:

- The note has completed the post-draft review pass, including terminology normalization.
- The unified figure/table/formula evidence timeline follows original-paper order.
- The Obsidian note exists at `~/Documents/Obsidian Vault/组会分享/<yy-M-d>/<论文标题>.md` or the user-specified path.
- The `assets/` folder exists beside the note.
- The Zotero-compatible copy or Zotero note exists when requested.
- The visible H1 and filename match the user request.
- All referenced local images exist, or missing images are listed as placeholders.
- Images copied from MCP `assets_dir` resolve from the note-local `assets/` folder.
- Matched images appear beside the evidence entries they support; unmatched images are not confused with paper evidence.
- No MinerU asset-audit appendix or resource-completeness index remains in the final note.
- `scripts/validate_note.py "<note-path>"` passes, or remaining structural errors are reported explicitly.

Report the final paths and unresolved placeholders to the user.

## Post-Delivery Cleanup

After the note passes validation (`scripts/validate_note.py`), clean up intermediate artifacts that are no longer needed. The following must be **preserved**:

| 保留项 | 说明 |
| ------ | ---- |
| 论文源 PDF | 原始下载的 PDF 文件 |
| MinerU 解析目录 `<pdf>_mineru/` | 包含 `full.md`、`content_list.json`、`assets/figures/`，是后续查阅和更新笔记的可信源 |
| MCP parsed cache `.paper_search_cache/` | SQLite FTS 索引，用于全文搜索已解析论文。删除后需重新 `index_parsed_cache` |
| 最终 Obsidian 笔记 `<vault>/组会分享/<date>/<title>.md` | 交付物 |
| 笔记本地 `assets/` 目录 | 笔记引用的图片副本 |

The following intermediate artifacts may be safely deleted after verification:

| 可清理项 | 说明 |
| -------- | ---- |
| `evidence-manifest*.json` | `build_evidence_manifest.py` 生成的证据清单。仅在笔记验证阶段需要；验证通过后可删除 |
| MinerU `<pdf>.zip` | 解析结果打包快照。`<pdf>_mineru/` 目录和 MCP parsed cache 保留后无独立用途 |
| `prepare_output.py` 生成的 Zotero stub（项目目录下同名 `.md`） | 仅为 Zotero 兼容性的占位桩。如果未向 Zotero 写入实际内容，可删除 |
| `--sync-from-manifest` 测试残留（如 `Test Paper.md`） | 功能测试产生的临时文件 |

Do **not** delete:

- `<pdf>_mineru/` — it contains the canonical parsed source (`full.md`, `content_list.json`) used for drafting and verification
- `.paper_search_cache/` — deleting it breaks MCP full-text search for all previously parsed papers
- Any file inside the final Obsidian note directory

Cleanup is optional but recommended to avoid accumulating stale manifests and test stubs across multiple paper-note sessions.
