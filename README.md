# nendo

Avatar sculpting toolkit — inspect, edit, and visually customize 3D avatar files.

Currently supports VRM (0.x / 1.0). Combines a zero-dependency GLB parser, Blender headless integration, and a browser-based 3D character editor powered by [three-vrm](https://github.com/pixiv/three-vrm).

## Install

```bash
git clone https://github.com/O6lvl4/nendo.git
cd nendo
pip install -e .
```

Optional: `brew install --cask blender` for Blender-powered commands.

## Editor

```bash
python3 -m nendo editor model.vrm
```

Opens a browser-based character editor at `http://localhost:8765`.

- **Parts** — Toggle mesh visibility (clothing, hair, accessories)
- **Shape** — Body shape keys grouped by category (chest, hair, boots, etc.)
- **Face** — VRM expressions + face shape keys (eyes, mouth, eyebrows)
- **Recolor** — Click on model to sample a color, pick a new color. GPU shader recolor on texture atlases.
- **Material** — Per-material base color and emissive editing
- **Meta** — Metadata editing (title, author, license)

All changes save back to the file.

## Playground

```bash
python3 -m nendo editor model.vrm
# then open http://localhost:8765/playground
```

- Idle animation (breathing, blinking, subtle sway)
- Drag & drop Mixamo FBX for instant retargeted playback
- Expression mixer with preset save/load
- Screenshot capture

## CLI

```
nendo inspect <file>              # Structure overview
nendo validate <file>             # Spec validation
nendo meta <file> --set title=Foo # Edit metadata
nendo tree <file>                 # Node hierarchy tree
nendo dump <file> --ext VRM       # Raw glTF JSON extraction
nendo blender info <file>         # Deep analysis via Blender
nendo blender convert <fbx> <vrm> # FBX to VRM conversion
```

## Architecture

```
nendo/
├── glb.py                  # Zero-dep GLB parser (JSON + binary chunk ops)
├── vrm.py                  # VRM 0.x / 1.0 model layer
├── cli.py                  # Typer + Rich CLI
├── blender.py              # Blender headless runner
├── blender_scripts/        # Blender Python scripts
└── editor/
    ├── server.py           # Local HTTP server + APIs
    └── static/
        ├── index.html      # Character editor (recolor, shape keys, materials)
        └── playground.html # Animation playground (idle, Mixamo, expressions)
```

## Requirements

- Python 3.10+
- Blender 4.x + [VRM Addon for Blender](https://github.com/saturday06/VRM-Addon-for-Blender) (optional, for `blender` subcommands)
- Modern browser (for editor/playground)
