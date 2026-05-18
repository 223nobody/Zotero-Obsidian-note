# Domain Template: Computer Vision

Use this reference for papers about image/video recognition, object detection, segmentation, generation, 3D vision, multimodal vision, diffusion, vision-language models, medical imaging, or remote sensing.

## What To Identify

- Task type: classification, detection, segmentation, tracking, pose, retrieval, reconstruction, generation, restoration, captioning, or vision-language reasoning.
- Data setting: supervised, self-supervised, weakly supervised, few-shot, zero-shot, domain adaptation, open-vocabulary, synthetic data, or multimodal pretraining.
- Core intervention: backbone, feature fusion, attention, loss function, data augmentation, pretraining objective, decoder head, diffusion process, promptable interface, or evaluation benchmark.
- Evaluation setting: dataset split, metric, resolution, model size, training compute, inference speed, and annotation cost.

## Innovation Questions

- Does the paper improve representation, localization, robustness, efficiency, generation quality, cross-domain generalization, or annotation efficiency?
- Is the novelty architectural, objective-level, data-level, training-level, or evaluation-level?
- Are gains consistent across datasets, object sizes, classes, resolutions, and domains?
- Does the method depend on stronger backbones, extra data, longer training, or test-time augmentation?

## Figures / Tables / Formulas To Explain

- Architecture figure: explain feature maps, multi-scale fusion, attention paths, decoder heads, skip connections, and where the new module sits.
- Qualitative visualization: explain success/failure cases, segmentation boundaries, detection errors, generated artifacts, or attention maps.
- Main result table: compare strongest baselines under same backbone and training data.
- Ablation table: separate gains from backbone, data, loss, module, and inference tricks.
- Efficiency table: explain FLOPs, parameters, FPS, memory, resolution, and deployment tradeoffs.
- Loss formula: explain classification, localization, contrastive, reconstruction, diffusion, perceptual, or regularization terms.

## Related Work Angles

- CNN vs Transformer vs hybrid architectures.
- Fully supervised vs self-supervised vs weakly supervised learning.
- Closed-set vs open-vocabulary / open-world settings.
- Task-specific models vs foundation/promptable vision models.
- Discriminative vision methods vs generative/diffusion-based methods.
- Single-image methods vs video/temporal methods.

## Common Limitations

- Improvements come from larger backbones or extra pretraining data.
- Qualitative examples are cherry-picked.
- Small-object, rare-class, occlusion, long-tail, or cross-domain performance remains weak.
- Metric improvement is small relative to compute increase.
- Real-time or edge deployment claims lack latency and memory evidence.
- Medical/remote-sensing claims lack external validation or annotation-quality discussion.
