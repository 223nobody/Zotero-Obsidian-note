# Domain Template: NLP

Use this reference for papers about text classification, named entity recognition, information extraction, question answering, summarization, machine translation, dialogue, parsing, generation, multilingual NLP, low-resource learning, or robustness.

## What To Identify

- Task type: classification, sequence labeling, extraction, retrieval, generation, reasoning, translation, dialogue, or evaluation.
- Data setting: supervised, weakly supervised, distant supervision, few-shot, zero-shot, low-resource, cross-domain, multilingual, noisy-label, or adversarial.
- Core intervention: representation, encoder/decoder architecture, prompt, data augmentation, schema design, training loss, decoding constraint, retrieval, reranking, or post-processing.
- Evaluation setting: dataset, split, metric, language/domain, label schema, baseline model, and statistical significance if available.

## Innovation Questions

- Does the paper improve generalization, robustness, label efficiency, factuality, controllability, multilingual transfer, or interpretability?
- Is the contribution task formulation, model design, data construction, loss function, inference procedure, or benchmark analysis?
- Is improvement due to better modeling or due to data leakage, stronger pretrained encoders, extra annotation, or easier evaluation?
- Does the method handle out-of-domain, long text, rare labels, noisy inputs, or label-schema changes?

## Figures / Tables / Formulas To Explain

- Pipeline figure: explain input text, tokenizer/schema, encoder, intermediate representation, decoder/classifier, and post-processing.
- Label/schema figure: explain entity types, relations, slots, prompts, constraints, or templates.
- Main result table: compare strongest baselines under same pretrained backbone and data budget.
- Low-resource/cross-domain table: explain where transfer or robustness is strongest.
- Error analysis/case study: identify which linguistic phenomena are fixed or still hard.
- Loss or decoding formula: explain token-level, span-level, contrastive, marginal likelihood, CRF, ranking, or constrained decoding logic.

## Related Work Angles

- Feature/statistical methods vs pretrained language models vs LLM prompting.
- Pipeline extraction vs joint modeling.
- Sequence labeling vs span classification vs generative formulation.
- Supervised learning vs data augmentation vs distant supervision vs retrieval-assisted methods.
- Monolingual vs multilingual / cross-lingual transfer.
- Accuracy-focused methods vs robustness/factuality/faithfulness evaluation.

## Common Limitations

- Results depend heavily on a specific pretrained backbone.
- Dataset split or prompt design may leak label information.
- Baselines are not tuned equally or use older encoders.
- Long-tail labels, nested entities, long documents, or cross-domain inputs remain difficult.
- Generation metrics do not fully capture factuality or faithfulness.
- Human evaluation or error analysis is too small to support broad claims.
