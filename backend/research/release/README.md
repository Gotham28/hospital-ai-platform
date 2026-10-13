# AROGYA Bilingual Grounding Benchmark Release Pack

This package contains tools and specifications for generating and inspecting the public release of the AROGYA bilingual (English + Malayalam) grounding dataset.

## Contents

- `DATASHEET.md`: Full dataset documentation covering provenance, ethical boundaries, and composition.
- `build_release.py`: Sanitisation and export utility. Ensures no unconsented real queries or personal data leak into public releases.
- `licence_options.md`: Legal licensing comparison for the benchmark artifacts.

## Usage

To generate the public release file from the repository fixture:

```powershell
python -m backend.research.release.build_release
```
