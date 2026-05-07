"""vrm-kit CLI — inspect, edit, validate VRM files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from vrmkit.vrm import Vrm, VrmVersion

app = typer.Typer(name="vrm-kit", help="VRM avatar file toolkit")
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


# ---- blender subcommands ----


@blender_app.command("info")
def blender_info(
    file: Path = typer.Argument(..., help="Path to .vrm file"),
) -> None:
    """Deep inspection via Blender (vertex counts, shape keys, bone positions)."""
    from vrmkit.blender import run_script_json

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
    from vrmkit.blender import run_script

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


# ---- editor ----


@app.command()
def editor(
    file: Path = typer.Argument(..., help="Path to .vrm file"),
    port: int = typer.Option(8765, "--port", "-p", help="Server port"),
) -> None:
    """Open visual editor in browser (three-vrm powered)."""
    import webbrowser

    from vrmkit.editor.server import start_server

    webbrowser.open(f"http://localhost:{port}")
    start_server(file, port=port)


def main() -> None:
    app()
