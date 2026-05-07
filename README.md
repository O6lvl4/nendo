# vrm-kit

VRM avatar file toolkit — inspect, edit, validate, and visually customize VRM files.

Combines a zero-dependency GLB parser, Blender headless integration, and a browser-based 3D character editor powered by [three-vrm](https://github.com/pixiv/three-vrm).

## Install

```bash
git clone https://github.com/O6lvl4/vrm-kit.git
cd vrm-kit
pip install -e .
```

Optional: `brew install --cask blender` for Blender-powered commands.

## Visual Editor

```bash
python3 -m vrm_kit editor model.vrm
```

Opens a browser-based character editor at `http://localhost:8765`.

**Parts** — Toggle mesh visibility (clothing, hair, accessories)
**Shape** — Body shape keys grouped by category (chest, hair, boots, etc.)
**Face** — VRM expressions + face shape keys (eyes, mouth, eyebrows)
**Recolor** — Click on 3D model to sample a color, pick a new color from the color picker. Works on texture atlases — change eye color, hair color, skin tone on any VRM.
**Material** — Per-material base color and emissive editing
**Meta** — VRM metadata editing (title, author, license)

All changes save back to the VRM file.

## CLI

```
vrm-kit inspect <file>              # Structure overview (meta, bones, expressions, spring bones)
vrm-kit validate <file>             # Spec validation (required bones, license, etc.)
vrm-kit meta <file> --set title=Foo # Edit metadata
vrm-kit tree <file>                 # Node hierarchy tree
vrm-kit dump <file> --ext VRM       # Raw glTF JSON extraction
vrm-kit blender info <file>         # Deep analysis via Blender (vertex counts, shape keys)
vrm-kit blender convert <fbx> <vrm> # FBX to VRM conversion
```

## Architecture

```
vrm_kit/
├── glb.py                  # Zero-dep GLB parser (JSON + binary chunk manipulation)
├── vrm.py                  # VRM 0.x / 1.0 model layer
├── cli.py                  # Typer + Rich CLI
├── blender.py              # Blender headless runner
├── blender_scripts/        # Blender Python scripts (convert, info, thumbnail)
└── editor/
    ├── server.py           # Local HTTP server (VRM file serving, texture/meta APIs)
    └── static/index.html   # three-vrm editor (single HTML, CDN imports)
```

**GLB parser** reads/writes the binary glTF container directly, including image extraction and replacement with automatic `bufferView` offset adjustment. No glTF library dependency.

**VRM model** provides version-aware accessors for both VRM 0.x (`VRM` extension) and VRM 1.0 (`VRMC_vrm`, `VRMC_springBone`, etc.).

**Recolor engine** works at the texture pixel level: raycast hit → UV coordinate → texture sampling → HSL-space color matching with configurable tolerance → sparse pixel recoloring (only affected pixels are processed per frame). Uses `CanvasTexture` for zero-copy GPU upload.

## Requirements

- Python 3.10+
- Blender 4.x + [VRM Addon for Blender](https://github.com/saturday06/VRM-Addon-for-Blender) (optional, for `blender` subcommands)
- Modern browser (for editor)
