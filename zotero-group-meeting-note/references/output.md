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

The note content should follow `references/blueprint.md`: emphasize innovation, evidence, figure/table/formula interpretation, conclusion data, related-work comparison, limitations, and discussion questions.
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
figure-1.png
figure-2-method-overview.png
table-3-results.png
formula-4-loss.png
```

When assets are already available as files, copy them through:

```powershell
python scripts/prepare_output.py --article-filename "<论文标题>" --asset ".\figure1.png" --asset-dir ".\paper-assets"
```

Use relative paths in the Obsidian note:

```markdown
![Figure 2 方法总体框架图](assets/figure-2-method-overview.png)
```

If an image cannot be extracted, keep an explicit placeholder rather than silently dropping it.

## Failure Patterns To Avoid

Before final delivery, fix these mistakes if they appear:

- The note is saved directly under `组会分享/` without a date folder.
- The filename is a lowercase slug rather than the readable paper title.
- The filename includes `group-meeting` or a date suffix without user request.
- The note starts with YAML frontmatter when the user did not ask for it.
- The note ends with model/plugin signatures.
- The body ignores the blueprint and becomes only an abstract summary.

## Final Verification Report

After writing, verify:

- The note has completed the post-draft review pass, including terminology normalization.
- Figure, table, and formula explanation sections follow original-paper order.
- The Obsidian note exists at `~/Documents/Obsidian Vault/组会分享/<yy-M-d>/<论文标题>.md` or the user-specified path.
- The `assets/` folder exists beside the note.
- The Zotero-compatible copy or Zotero note exists when requested.
- The visible H1 and filename match the user request.
- All referenced local images exist, or missing images are listed as placeholders.

Report the final paths and unresolved placeholders to the user.
