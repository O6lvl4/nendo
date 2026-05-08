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
- **Shape** — Body shape keys by category + Bake button (permanently apply customizations into mesh geometry)
- **Face** — VRM expressions + face shape keys (eyes, mouth, eyebrows)
- **Textures** — Texture list with thumbnails, Export All (zip), Import edited PNGs
- **Material** — Per-material base color and emissive editing
- **Meta** — Metadata editing (title, author, license)

Drag & drop a VRM file onto the editor to switch models.

## Playground

```bash
python3 -m nendo editor model.vrm
# then open http://localhost:8765/playground
```

- Idle animation (breathing, blinking, subtle sway)
- Drag & drop Mixamo FBX for instant retargeted playback
- Drag & drop VRM to switch models
- Expression mixer with preset save/load
- Screenshot capture

## CLI

```
nendo inspect <file>                        # Structure overview (meta, bones, expressions, MToon, etc.)
nendo validate <file>                       # Spec validation
nendo meta <file> --set title=Foo           # Edit metadata
nendo tree <file>                           # Node hierarchy tree
nendo dump <file> --ext VRM                 # Raw glTF JSON extraction
nendo migrate <file>                        # VRM 0.x → 1.0 migration
nendo bake <file> --set mesh:key=weight     # Bake shape keys into geometry
nendo texture list <file>                   # List all textures with material mapping
nendo texture export <file> -o dir          # Extract all textures as PNG
nendo texture import <file> -f dir          # Import edited textures back
nendo texture recolor <png> --hue 120       # Hue shift a texture
nendo texture recolor <png> --tint "#ff33"  # Tint (multiply) a texture
nendo blender info <file>                   # Deep analysis via Blender
nendo blender convert <fbx> <vrm>           # FBX to VRM conversion
```

### Texture editing workflow

```bash
nendo texture export model.vrm -o textures/           # Extract all textures
# Edit EyeIris_00.png, Tops_01.png, etc. in Krita/Photoshop
nendo texture import model.vrm --from textures/       # Import back into VRM
```

Or use the CLI recolor for quick adjustments:

```bash
nendo texture recolor textures/EyeIris_00.png --hue 120       # Eyes: brown → green
nendo texture recolor textures/Tops_01.png --tint "#ff3333"    # Shirt: green → red
nendo texture import model.vrm --from textures/
```

## Architecture

```
nendo/
├── glb.py                  # Zero-dep GLB parser (read/write/image extract+replace)
├── vrm.py                  # VRM 0.x / 1.0 model (meta, humanoid, expressions,
│                           #   firstPerson, lookAt, constraints, MToon materials)
├── bake.py                 # Shape key baking (morph target → base geometry)
├── migrate.py              # VRM 0.x → 1.0 migration (meta, bones, expressions,
│                           #   springBone, MToon materials, lookAt, firstPerson)
├── cli.py                  # Typer + Rich CLI
├── blender.py              # Blender headless runner
├── blender_scripts/        # Blender Python scripts (convert, info, thumbnail)
└── editor/
    ├── server.py           # Local HTTP server + APIs (shared state, texture ops)
    └── static/
        ├── index.html      # Character editor (parts, shape, textures, materials)
        └── playground.html # Animation playground (idle, Mixamo, expressions)
```

## Requirements

- Python 3.10+
- Pillow, NumPy (installed automatically)
- Blender 4.x + [VRM Addon for Blender](https://github.com/saturday06/VRM-Addon-for-Blender) (optional, for `blender` subcommands)
- Modern browser (for editor/playground)
