"""nendo CLI — inspect, edit, validate VRM files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from nendo.vrm import Vrm, VrmVersion

app = typer.Typer(name="nendo", help="VRM avatar file toolkit")
blender_app = typer.Typer(help="Blender-powered operations (requires Blender)")
app.add_typer(blender_app, name="blender")
console = Console()


# ---- inspect ----


@app.command()
def inspect(
    file: Path = typer.Argument(..., help="Path to .vrm file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Inspect a VRM file and display its structure."""
    vrm = Vrm.load(file)

    if json_output:
        console.print_json(data=vrm.summary())
        return

    s = vrm.summary()
    author = s["author"]
    if isinstance(author, list):
        author = ", ".join(author)

    console.print(f"\n[bold]{file.name}[/bold]")
    console.print(f"  VRM Version : [cyan]{s['version']}[/cyan]")
    console.print(f"  Title       : [green]{s['title'] or '(none)'}[/green]")
    console.print(f"  Author      : [green]{author or '(none)'}[/green]")

    tbl = Table(title="Assets", show_header=False, box=None, padding=(0, 2))
    tbl.add_column("Key", style="dim")
    tbl.add_column("Value", style="bold")
    for label, key in [
        ("Meshes", "meshes"),
        ("Nodes", "nodes"),
        ("Materials", "materials"),
        ("Textures", "textures"),
        ("Images", "images"),
        ("Human Bones", "human_bones"),
        ("Expressions", "expressions"),
        ("Spring Bone Groups", "spring_bone_groups"),
    ]:
        tbl.add_row(label, str(s[key]))
    console.print(tbl)

    _print_meta(vrm)
    _print_bones(vrm)
    _print_expressions(vrm)
    _print_spring_bones(vrm)
    _print_first_person(vrm)
    _print_look_at(vrm)
    _print_mtoon(vrm)
    _print_constraints(vrm)
    console.print()


# ---- meta ----


@app.command()
def meta(
    file: Path = typer.Argument(..., help="Path to .vrm file"),
    set_field: Optional[list[str]] = typer.Option(
        None, "--set", "-s", help="Set field: key=value"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output path (default: overwrite)"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """View or edit VRM metadata."""
    vrm = Vrm.load(file)

    if not set_field:
        if json_output:
            console.print_json(data=vrm.meta)
        else:
            _print_meta(vrm)
        return

    meta_data = vrm.meta
    for field in set_field:
        if "=" not in field:
            console.print(f"[red]Invalid format: {field} (expected key=value)[/red]")
            raise typer.Exit(1)
        key, value = field.split("=", 1)
        if key == "authors":
            meta_data[key] = [v.strip() for v in value.split(",")]
        else:
            meta_data[key] = value

    vrm.meta = meta_data
    out_path = output or file
    vrm.save(out_path)
    console.print(f"[green]Saved to {out_path}[/green]")


# ---- validate ----

REQUIRED_BONES = frozenset({
    "hips", "spine", "chest", "neck", "head",
    "leftUpperArm", "leftLowerArm", "leftHand",
    "rightUpperArm", "rightLowerArm", "rightHand",
    "leftUpperLeg", "leftLowerLeg", "leftFoot",
    "rightUpperLeg", "rightLowerLeg", "rightFoot",
})


@app.command()
def validate(
    file: Path = typer.Argument(..., help="Path to .vrm file"),
) -> None:
    """Validate a VRM file against the spec."""
    vrm = Vrm.load(file)
    issues: list[tuple[str, str]] = []

    if vrm.version == VrmVersion.UNKNOWN:
        issues.append(("error", "No VRM extension found"))

    if not vrm.title:
        issues.append(("warn", "Missing title/name"))
    if not vrm.author:
        issues.append(("warn", "Missing author"))

    # Humanoid bone checks
    bones = vrm.human_bones
    if isinstance(bones, dict):
        missing = REQUIRED_BONES - set(bones.keys())
    elif isinstance(bones, list):
        missing = REQUIRED_BONES - {b.get("bone") for b in bones}
    else:
        missing = REQUIRED_BONES
    for b in sorted(missing):
        issues.append(("error", f"Missing required bone: {b}"))

    # License
    m = vrm.meta
    if vrm.version == VrmVersion.V1 and not m.get("licenseUrl"):
        issues.append(("error", "VRM 1.0 requires licenseUrl"))
    elif vrm.version == VrmVersion.V0 and not m.get("licenseName"):
        issues.append(("warn", "Missing licenseName"))

    if not issues:
        console.print("[green]Valid[/green]")
        return

    for level, msg in issues:
        tag = "[red]ERROR[/red]" if level == "error" else "[yellow]WARN[/yellow] "
        console.print(f"  {tag} {msg}")

    errors = sum(1 for l, _ in issues if l == "error")
    warns = sum(1 for l, _ in issues if l == "warn")
    console.print(f"\n{errors} error(s), {warns} warning(s)")
    if errors:
        raise typer.Exit(1)


# ---- tree ----


@app.command()
def tree(
    file: Path = typer.Argument(..., help="Path to .vrm file"),
) -> None:
    """Display the node hierarchy as a tree."""
    vrm = Vrm.load(file)
    nodes = vrm.nodes
    root_tree = Tree(f"[bold]{file.name}[/bold]")

    def _add(parent: Tree, idx: int) -> None:
        node = nodes[idx]
        name = node.get("name", f"node_{idx}")
        mesh = node.get("mesh")
        skin = node.get("skin")
        suffix = ""
        if mesh is not None:
            suffix += f" [dim](mesh {mesh})[/dim]"
        if skin is not None:
            suffix += f" [dim](skin {skin})[/dim]"
        branch = parent.add(f"{name}{suffix}")
        for child in node.get("children", []):
            _add(branch, child)

    for ri in vrm.root_node_indices():
        _add(root_tree, ri)

    console.print(root_tree)


# ---- dump ----


@app.command()
def dump(
    file: Path = typer.Argument(..., help="Path to .vrm file"),
    extension: Optional[str] = typer.Option(
        None, "--ext", "-e", help="Dump specific extension (e.g. VRM, VRMC_vrm)"
    ),
) -> None:
    """Dump raw glTF JSON (or a specific extension)."""
    vrm = Vrm.load(file)
    if extension:
        data = vrm.extensions.get(extension)
        if data is None:
            console.print(f"[red]Extension '{extension}' not found[/red]")
            console.print(f"Available: {', '.join(vrm.extensions.keys())}")
            raise typer.Exit(1)
        console.print_json(data=data)
    else:
        console.print_json(data=vrm.glb.json_data)


# ---- helpers ----


def _print_meta(vrm: Vrm) -> None:
    meta = vrm.meta
    if not meta:
        return
    console.print("\n[bold]Meta[/bold]")
    for k, v in meta.items():
        if isinstance(v, (dict, list)):
            console.print(f"  {k}: {json.dumps(v, ensure_ascii=False)}")
        else:
            console.print(f"  {k}: [yellow]{v}[/yellow]")


def _print_bones(vrm: Vrm) -> None:
    bones = vrm.human_bones
    if not bones:
        return
    console.print("\n[bold]Humanoid Bones[/bold]")
    if isinstance(bones, dict):
        for name, data in sorted(bones.items()):
            console.print(f"  {name}: node {data.get('node', '?')}")
    else:
        for b in bones:
            console.print(f"  {b.get('bone', '?')}: node {b.get('node', '?')}")


def _print_expressions(vrm: Vrm) -> None:
    expr = vrm.expressions
    if not expr:
        return
    console.print("\n[bold]Expressions[/bold]")
    if vrm.version == VrmVersion.V1:
        for cat in ("preset", "custom"):
            items = expr.get(cat, {})
            if items:
                console.print(f"  [{cat}]")
                for name in sorted(items.keys()):
                    console.print(f"    {name}")
    else:
        for g in expr.get("blendShapeGroups", []):
            console.print(
                f"  {g.get('name', '?')} (preset: {g.get('presetName', 'custom')})"
            )


def _print_spring_bones(vrm: Vrm) -> None:
    sb = vrm.spring_bone
    if not sb:
        return
    console.print("\n[bold]Spring Bones[/bold]")
    if vrm.version == VrmVersion.V1:
        for i, s in enumerate(sb.get("springs", [])):
            console.print(f"  Spring {i}: {len(s.get('joints', []))} joints")
    else:
        for i, g in enumerate(sb.get("boneGroups", [])):
            console.print(
                f"  Group {i}: {len(g.get('bones', []))} bones"
                f", stiffness={g.get('stiffiness', '?')}"
            )


def _print_first_person(vrm: Vrm) -> None:
    fp = vrm.first_person
    if not fp:
        return
    console.print("\n[bold]First Person[/bold]")
    if vrm.version == VrmVersion.V1:
        for ann in fp.get("meshAnnotations", []):
            console.print(f"  mesh {ann.get('node', '?')}: {ann.get('type', '?')}")
    else:
        bone = fp.get("firstPersonBone")
        offset = fp.get("firstPersonBoneOffset", {})
        if bone is not None:
            console.print(f"  bone: {bone}, offset: ({offset.get('x',0):.2f}, {offset.get('y',0):.2f}, {offset.get('z',0):.2f})")
        for ann in fp.get("meshAnnotations", []):
            console.print(f"  mesh {ann.get('mesh', '?')}: {ann.get('firstPersonFlag', '?')}")


def _print_look_at(vrm: Vrm) -> None:
    if vrm.version == VrmVersion.V1:
        la = vrm._vrm_root.get("lookAt", {})
        if not la:
            return
        console.print("\n[bold]LookAt[/bold]")
        console.print(f"  type: {la.get('type', '?')}")
        console.print(f"  offsetFromHeadBone: {la.get('offsetFromHeadBone', [0,0,0])}")
        for key in ("rangeMapHorizontalInner", "rangeMapHorizontalOuter", "rangeMapVerticalDown", "rangeMapVerticalUp"):
            rm = la.get(key, {})
            if rm:
                console.print(f"  {key}: input={rm.get('inputMaxValue','?')}, output={rm.get('outputScale','?')}")
    else:
        fp = vrm._vrm_root.get("firstPerson", {})
        look_type = fp.get("lookAtTypeName")
        if look_type:
            console.print("\n[bold]LookAt[/bold]")
            console.print(f"  type: {look_type}")
            for key in ("lookAtHorizontalInner", "lookAtHorizontalOuter", "lookAtVerticalDown", "lookAtVerticalUp"):
                la = fp.get(key, {})
                if la:
                    console.print(f"  {key}: curve={la.get('curve', [])}, x={la.get('xRange','?')}, y={la.get('yRange','?')}")


def _print_mtoon(vrm: Vrm) -> None:
    mats = vrm.mtoon_materials
    if not mats:
        return
    console.print(f"\n[bold]MToon Materials ({len(mats)})[/bold]")
    for m in mats:
        console.print(f"  [cyan]{m.get('name', '?')}[/cyan]")
        if vrm.version == VrmVersion.V1:
            mt = m.get("mtoon", {})
            for k in ("shadeColorFactor", "shadeMultiplyTexture", "shadingShiftFactor",
                       "shadingToonyFactor", "matcapFactor", "matcapTexture",
                       "parametricRimColorFactor", "parametricRimFresnelPowerFactor",
                       "outlineWidthMode", "outlineWidthFactor", "outlineColorFactor",
                       "uvAnimationScrollXSpeedFactor", "uvAnimationScrollYSpeedFactor",
                       "uvAnimationRotationSpeedFactor"):
                v = mt.get(k)
                if v is not None:
                    console.print(f"    {k}: {v}")
        else:
            vp = m.get("vectorProperties", {})
            for k, v in vp.items():
                if any(x in k for x in ("Color", "color")):
                    console.print(f"    {k}: {v}")
            fp = m.get("floatProperties", {})
            for k in ("_ShadeShift", "_ShadeToony", "_OutlineWidth", "_OutlineWidthMode",
                       "_RimFresnelPower", "_RimLift", "_UvAnimScrollX", "_UvAnimScrollY", "_UvAnimRotation"):
                v = fp.get(k)
                if v is not None:
                    console.print(f"    {k}: {v}")


def _print_constraints(vrm: Vrm) -> None:
    constraints = vrm.constraints
    if not constraints:
        return
    console.print(f"\n[bold]Node Constraints ({len(constraints)})[/bold]")
    for c in constraints:
        ctype = "roll" if "roll" in c else "aim" if "aim" in c else "rotation" if "rotation" in c else "?"
        detail = c.get(ctype, {})
        console.print(f"  {c.get('name', '?')}: {ctype} (source={detail.get('source','?')}, weight={detail.get('weight','?')})")


# ---- blender subcommands ----


@blender_app.command("info")
def blender_info(
    file: Path = typer.Argument(..., help="Path to .vrm file"),
) -> None:
    """Deep inspection via Blender (vertex counts, shape keys, bone positions)."""
    from nendo.blender import run_script_json

    with console.status("Running Blender..."):
        data = run_script_json("export_info.py", [str(file)], timeout=120)

    if data.get("armature"):
        arm = data["armature"]
        console.print(f"\n[bold]Armature: {arm['name']}[/bold] ({arm['bone_count']} bones)")

    if data.get("meshes"):
        console.print("\n[bold]Meshes[/bold]")
        tbl = Table(show_header=True, box=None, padding=(0, 2))
        tbl.add_column("Name")
        tbl.add_column("Vertices", justify="right")
        tbl.add_column("Polygons", justify="right")
        tbl.add_column("Materials")
        tbl.add_column("Shape Keys", justify="right")
        total_verts = 0
        total_polys = 0
        for m in data["meshes"]:
            total_verts += m["vertices"]
            total_polys += m["polygons"]
            sk = str(len(m.get("shape_keys", []))) if m.get("shape_keys") else "-"
            tbl.add_row(
                m["name"],
                str(m["vertices"]),
                str(m["polygons"]),
                ", ".join(m["materials"]) if m["materials"] else "-",
                sk,
            )
        tbl.add_row("[bold]Total[/bold]", f"[bold]{total_verts}[/bold]", f"[bold]{total_polys}[/bold]", "", "")
        console.print(tbl)

    if data.get("shape_keys"):
        console.print("\n[bold]Shape Keys[/bold]")
        for mesh_name, keys in data["shape_keys"].items():
            console.print(f"  [cyan]{mesh_name}[/cyan]: {', '.join(keys)}")


@blender_app.command("convert")
def blender_convert(
    input_file: Path = typer.Argument(..., help="Input file (FBX, OBJ, etc.)"),
    output_file: Path = typer.Argument(..., help="Output VRM file"),
    title: str = typer.Option("", help="VRM title"),
    author: str = typer.Option("", help="VRM author"),
) -> None:
    """Convert FBX/OBJ to VRM via Blender."""
    from nendo.blender import run_script

    args = [str(input_file), str(output_file)]
    if title:
        args += ["--title", title]
    if author:
        args += ["--author", author]

    with console.status("Converting via Blender..."):
        result = run_script("convert_fbx.py", args, timeout=300)

    if result.returncode != 0:
        console.print(f"[red]Conversion failed[/red]")
        console.print(result.stderr[-1000:] if result.stderr else "(no stderr)")
        raise typer.Exit(1)

    console.print(f"[green]Saved to {output_file}[/green]")


# ---- bake ----


@app.command()
def bake(
    file: Path = typer.Argument(..., help="Path to .vrm file"),
    set_field: list[str] = typer.Option(..., "--set", "-s", help="mesh:key=weight (e.g. Body_Base:Waist_slim=0.5)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output path (default: overwrite)"),
) -> None:
    """Bake shape key weights permanently into mesh geometry."""
    from nendo.bake import bake_shape_keys

    vrm = Vrm.load(file)

    targets: dict[str, dict[str, float]] = {}
    for field in set_field:
        if ":" not in field or "=" not in field:
            console.print(f"[red]Invalid format: {field} (expected mesh:key=weight)[/red]")
            raise typer.Exit(1)
        mesh_key, weight_str = field.rsplit("=", 1)
        mesh_name, key_name = mesh_key.split(":", 1)
        targets.setdefault(mesh_name, {})[key_name] = float(weight_str)

    result = bake_shape_keys(vrm, targets)

    out_path = output or file
    vrm.save(out_path)

    for mesh_name, keys in result.items():
        console.print(f"  [green]{mesh_name}[/green]: baked {', '.join(keys)}")
    if not result:
        console.print("[yellow]No keys were baked (check mesh/key names)[/yellow]")
    else:
        console.print(f"[green]Saved to {out_path}[/green]")


# ---- texture export/import ----

texture_app = typer.Typer(help="Texture export/import")
app.add_typer(texture_app, name="texture")


@texture_app.command("export")
def texture_export(
    file: Path = typer.Argument(..., help="Path to .vrm file"),
    output_dir: Path = typer.Option(".", "--out", "-o", help="Output directory"),
) -> None:
    """Export all textures from a VRM as PNG files."""
    vrm = Vrm.load(file)
    images = vrm.glb.json_data.get("images", [])
    if not images:
        console.print("[yellow]No images found[/yellow]")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    for i, img in enumerate(images):
        name = img.get("name", f"texture_{i}")
        ext = ".png" if "png" in img.get("mimeType", "png") else ".jpg"
        out_path = output_dir / f"{name}{ext}"
        data = vrm.glb.extract_image(i)
        out_path.write_bytes(data)
        console.print(f"  [green]{out_path}[/green] ({len(data):,} bytes)")

    console.print(f"\nExported {len(images)} textures to {output_dir}/")


@texture_app.command("import")
def texture_import(
    file: Path = typer.Argument(..., help="Path to .vrm file"),
    from_dir: Path = typer.Option(..., "--from", "-f", help="Directory with edited textures"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output path (default: overwrite)"),
) -> None:
    """Import edited textures back into a VRM."""
    vrm = Vrm.load(file)
    images = vrm.glb.json_data.get("images", [])
    replaced = 0

    for i, img in enumerate(images):
        name = img.get("name", f"texture_{i}")
        # Try both .png and .jpg
        for ext in (".png", ".jpg", ".jpeg"):
            candidate = from_dir / f"{name}{ext}"
            if candidate.exists():
                data = candidate.read_bytes()
                vrm.glb.replace_image(i, data)
                console.print(f"  [green]{name}[/green] <- {candidate.name} ({len(data):,} bytes)")
                replaced += 1
                break

    if replaced == 0:
        console.print("[yellow]No matching textures found[/yellow]")
        console.print(f"Expected filenames: {', '.join(img.get('name', f'texture_{i}') + '.png' for i, img in enumerate(images))}")
        return

    out_path = output or file
    vrm.save(out_path)
    console.print(f"\nReplaced {replaced} texture(s), saved to {out_path}")


@texture_app.command("list")
def texture_list(
    file: Path = typer.Argument(..., help="Path to .vrm file"),
) -> None:
    """List all textures in a VRM."""
    vrm = Vrm.load(file)
    images = vrm.glb.json_data.get("images", [])
    materials = vrm.glb.json_data.get("materials", [])

    # Map texture index → material names
    tex_mats: dict[int, list[str]] = {}
    for mat in materials:
        tex_idx = mat.get("pbrMetallicRoughness", {}).get("baseColorTexture", {}).get("index")
        if tex_idx is not None:
            tex_mats.setdefault(tex_idx, []).append(mat.get("name", "?"))

    for i, img in enumerate(images):
        bv = vrm.glb.json_data["bufferViews"][img["bufferView"]]
        size = bv["byteLength"]
        name = img.get("name", f"texture_{i}")
        mats = tex_mats.get(i, [])
        mat_str = f" -> {', '.join(mats)}" if mats else ""
        console.print(f"  {i}: [cyan]{name}[/cyan] ({size:,} bytes){mat_str}")


@texture_app.command("recolor")
def texture_recolor(
    file: Path = typer.Argument(..., help="Path to PNG/JPG file"),
    hue: Optional[int] = typer.Option(None, "--hue", help="Hue shift in degrees (-180 to 180)"),
    tint: Optional[str] = typer.Option(None, "--tint", help="Tint color as hex (e.g. #ff3333)"),
    saturation: Optional[int] = typer.Option(None, "--saturation", "-s", help="Saturation adjust (-100 to 100)"),
    brightness: Optional[int] = typer.Option(None, "--brightness", "-b", help="Brightness adjust (-100 to 100)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output path (default: overwrite)"),
) -> None:
    """Recolor a texture PNG: hue shift, tint, or adjust saturation/brightness."""
    import colorsys
    import numpy as np
    from PIL import Image

    img = Image.open(file).convert("RGBA")
    arr = np.array(img, dtype=np.float32)
    rgb = arr[:, :, :3] / 255.0
    alpha = arr[:, :, 3:]

    if tint:
        # Multiply mode: multiply RGB by tint color
        hex_clean = tint.lstrip("#")
        tr = int(hex_clean[0:2], 16) / 255.0
        tg = int(hex_clean[2:4], 16) / 255.0
        tb = int(hex_clean[4:6], 16) / 255.0
        rgb[:, :, 0] *= tr
        rgb[:, :, 1] *= tg
        rgb[:, :, 2] *= tb
        console.print(f"  Tinted with {tint}")

    if hue is not None or saturation is not None or brightness is not None:
        # Convert to HSV, modify, convert back (vectorized)
        h_shift = (hue or 0) / 360.0
        s_adj = (saturation or 0) / 100.0
        b_adj = (brightness or 0) / 100.0

        r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        maxc = np.maximum(np.maximum(r, g), b)
        minc = np.minimum(np.minimum(r, g), b)
        v = maxc
        delta = maxc - minc

        # Saturation
        s = np.where(maxc > 0, delta / maxc, 0)

        # Hue
        h = np.zeros_like(r)
        mask = delta > 0
        rm = mask & (maxc == r)
        gm = mask & (maxc == g) & ~rm
        bm = mask & ~rm & ~gm
        h[rm] = ((g[rm] - b[rm]) / delta[rm]) % 6
        h[gm] = ((b[gm] - r[gm]) / delta[gm]) + 2
        h[bm] = ((r[bm] - g[bm]) / delta[bm]) + 4
        h /= 6.0

        # Apply adjustments
        h = (h + h_shift) % 1.0
        s = np.clip(s + s_adj, 0, 1)
        v = np.clip(v + b_adj, 0, 1)

        # HSV back to RGB
        hi = (h * 6).astype(int) % 6
        f = h * 6 - hi
        p = v * (1 - s)
        q = v * (1 - f * s)
        t = v * (1 - (1 - f) * s)

        out = np.zeros_like(rgb)
        for i, (r_val, g_val, b_val) in enumerate([(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)]):
            m = hi == i
            out[:, :, 0][m] = r_val[m]
            out[:, :, 1][m] = g_val[m]
            out[:, :, 2][m] = b_val[m]

        rgb = out
        parts = []
        if hue: parts.append(f"hue {hue:+d}")
        if saturation: parts.append(f"sat {saturation:+d}")
        if brightness: parts.append(f"bri {brightness:+d}")
        console.print(f"  Adjusted: {', '.join(parts)}")

    # Recombine and save
    result = np.concatenate([np.clip(rgb * 255, 0, 255), alpha], axis=2).astype(np.uint8)
    out_img = Image.fromarray(result, "RGBA")
    out_path = output or file
    out_img.save(out_path)
    console.print(f"  [green]Saved to {out_path}[/green]")


# ---- migrate ----


@app.command()
def migrate(
    file: Path = typer.Argument(..., help="Path to VRM 0.x file"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output path (default: <name>.v1.vrm)"),
) -> None:
    """Migrate VRM 0.x to VRM 1.0."""
    from nendo.migrate import migrate_0_to_1

    vrm = Vrm.load(file)
    if vrm.version != VrmVersion.V0:
        console.print(f"[yellow]Already VRM {vrm.version.value}, nothing to migrate[/yellow]")
        return

    migrate_0_to_1(vrm)
    out_path = output or file.with_suffix(".v1.vrm")
    vrm.save(out_path)
    console.print(f"[green]Migrated to VRM 1.0: {out_path}[/green]")


# ---- editor ----


@app.command()
def editor(
    file: Path = typer.Argument(..., help="Path to .vrm file"),
    port: int = typer.Option(8765, "--port", "-p", help="Server port"),
) -> None:
    """Open visual editor in browser (three-vrm powered)."""
    import webbrowser

    from nendo.editor.server import start_server

    webbrowser.open(f"http://localhost:{port}")
    start_server(file, port=port)


def main() -> None:
    app()
