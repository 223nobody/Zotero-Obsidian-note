# paper-search-mcp Intake

Use this reference when `paper-search-mcp` is available or when the user provides a paper title, search query, DOI, PDF path, or parsed paper key. The goal is to turn MCP search/parse output into a stable source pack for the group-meeting note.

## Preferred Intake Order

1. Existing parsed cache: use `list_parsed_papers`, then `get_parsed_paths(paper_key)` and `get_parsed_paper(paper_key, output_format="markdown")`.
2. Local PDF: use `parse_pdf_with_mineru(pdf_path, mode="auto")`, then read the returned `paper_key` and artifact paths.
3. Search request: use `search_papers_with_elicitation` when the client supports it; otherwise use `search_papers_for_parsing`, ask for numbered selections, then `parse_selected_papers`.
4. Direct downloaded paper: use the MCP download/parse flow, then consume the parsed cache rather than re-reading the PDF.
5. Fallback only when MCP is unavailable: use local Markdown/PDF extraction paths and the normal skill scripts.

## Source Pack Contract

Before drafting, record the available source pack fields:

```text
paper_key:
pdf_path:
full_md_path:
content_list_path:
manifest_path:
copy_map_path:
assets_dir:
result_zip_path:
parser / mode / backend:
```

Use `get_parsed_paths(paper_key)` to recover paths when only `paper_key` is known. Use `get_parsed_paper(paper_key, output_format="paths")` or `"manifest"` when path or parser provenance is unclear.

## Reading Strategy

- Use `full.md` as the main readable text.
- Use `content_list.json` as the source of block order, page hints, block types, and any parser-provided asset links.
- Use `assets_dir` as the authoritative input asset root for candidate figures, tables, formulas, and layout crops. It is not a checklist of images that must all appear in the final note, and it does not define the note's evidence coverage by itself.
- Use `search_parsed_papers(query, paper_key=..., max_results=...)` for targeted reading before loading large files into context.

Useful targeted queries:

```text
abstract introduction contribution
method framework architecture pipeline algorithm
objective loss equation
experiment result baseline ablation
robustness generalization efficiency
limitation discussion future work
appendix supplementary ethics checklist
```

## Asset Matching Priority

**Hard rule — evidence images must trace to `content_list.json`:** Every image included in the final note (`assets/...` links) must be traceable to a `content_list.json` structured block that carries an `img_path`, `table_body`, or `chart_caption`/`table_caption`/`image_caption` field. Images that appear only as inline `<img>` tags in `full.md` (page headers, formula renderings, bibliography text crops, duplicate panel crops, layout fragments) are NOT paper evidence items and must stay out of the final note. This rule is checked by `scripts/validate_note.py --evidence-manifest <manifest>`.

When `content_list_path` is available, first build a deterministic evidence manifest:

```powershell
python scripts/build_evidence_manifest.py "<content_list_path>" `
  --assets-dir "<assets_dir>" `
  --full-md "<full_md_path>" `
  --output "<working-evidence-manifest.json>"
```

Use this manifest as the first-pass source of item order, region, matched assets, source blocks, page, block index, source text, confidence, final note section, and rationale. Manifest rows expose `item_key`, `asset_paths: []`, `asset_hashes`, `content_payload`, and `panel_roles` for multi-panel figures or multiple crops, while `matched_asset` remains the first/best asset for backward compatibility. Fields such as `table_body`, HTML, captions, and plain text are content payload, not asset paths. Then verify low-confidence or candidate rows against `full.md`, `content_list.json`, and the PDF text. Do not paste the manifest into the final note.

When matching images, tables, and formulas to evidence entries, use this order:

1. `build_evidence_manifest.py` rows with high or medium confidence.
2. Parser-provided `content_list.json` asset fields such as `asset_paths`, image paths, table paths, or formula paths.
3. Markdown image links in `full.md` near the same Figure/Table/Equation heading or caption.
4. Same-page or adjacent-block evidence from `content_list.json`.
5. Filename, alt text, caption number, and nearby paragraph clues.
6. If still uncertain, mark the asset as `未匹配图片` / `待核对图片` instead of inventing a label.

Place matched assets directly under their corresponding Figure/Table/Equation/Prompt/Case Study entry in the final note. Do not leave matched evidence images only in a generic asset appendix. Unmatched assets stay out of the final note unless the user explicitly asks for an asset audit. If an audit is requested, write it as a separate manifest/checklist artifact rather than as part of the seminar note.

The final note must not contain `## 附录：MinerU 图片资源完整性索引`, `MinerU asset`, `MinerU extra crop`, or a filename-only dump of images from `assets_dir`.

## References Boundary

Treat `References`, `Bibliography`, `参考文献`, and `参考资料` as a boundary. Do not summarize bibliography entries as paper evidence. If `content_list.json` or `full.md` contains Appendix, Supplementary Material, prompts, case studies, implementation details, ethics statements, checklists, or extra figures/tables/equations after the bibliography, place them in `## 八、参考文献后内容与补充材料`. If appendix/supplementary material appears before the bibliography but is clearly outside the main-paper argument, also place it in that supplementary section.

## Verification

Before delivery:

- Confirm `full_md_path`, `content_list_path`, and `assets_dir` exist when provided.
- If `content_list_path` exists, confirm `build_evidence_manifest.py` was run or explain why it was skipped.
- For batch generation, update the per-paper sidecar after manifest creation with `scripts/update_pipeline_sidecar.py --stage evidence_manifest --status complete --manifest-path <manifest.json>`.
- Use `prepare_output.py --sync-from-manifest <evidence-manifest.json> --copy-map <copy-map.json>` to auto-copy all high/medium-confidence matched assets into the note `assets/` folder before drafting. Draft image links from the copy map's `markdown` fields so copied filenames and hashes stay stable.
- Rebuild or query the parsed index if targeted searches return no hits despite readable content.
- Check that every final note image link points to an existing file copied into the note `assets/` folder. When using `validate_note.py --evidence-manifest <manifest.json> --copy-map <copy-map.json> --strict-evidence`, missing or misplaced evidence assets fail validation instead of becoming ignorable warnings.
- Compare the source-order inventory against `content_list.json` / `full.md` order.
- Confirm unmatched `assets_dir` files were not written into the final note as a resource-completeness index.
- Run `scripts/audit_note_assets.py <note-path> --output <asset-report.json>` and keep the report outside the note body.
- Report the `paper_key` and any unresolved asset or extraction gaps.
