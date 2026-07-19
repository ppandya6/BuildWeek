# Input preparation

## Manifests and paths

Require distinct train and test CSV files. Keep original files unchanged and local. Inspect headers rather than full rows when planning. Preserve image paths locally and provide `--images` when image relationships should be checked or relative image references need a root.

Do not guess through normalized-header collisions: rename headers in a reviewed copy or supply an unambiguous schema map. Missing or unreadable images become disclosed input-quality findings rather than identity evidence.

## Manual schema map

Verify each proposed source name against actual headers before writing a map. A shape to adapt—not a claim about the user's headers—is:

```yaml
patient_id: case_ref
specimen_id: block_ref
slide_id: scan_ref
image_path: file_path
institution: site
label: target
```

Pass the reviewed file with `--schema-map`. Direct CLI column flags are also available; inspect `slide-of-life audit --help`. If deterministic mapping remains ambiguous, explain the limitation and offer optional AI schema assistance only after manual mapping.
