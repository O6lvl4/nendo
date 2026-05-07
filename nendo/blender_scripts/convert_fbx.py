"""Blender script: Convert FBX to VRM.

Run via: blender --background --python convert_fbx.py -- <input.fbx> <output.vrm> [--title NAME] [--author AUTHOR]

The VRM Add-on for Blender must be installed and enabled.
"""

import sys
import argparse

import bpy


def parse_args() -> argparse.Namespace:
    # Arguments after '--' are passed to the script
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    p = argparse.ArgumentParser(description="Convert FBX to VRM")
    p.add_argument("input", help="Input FBX file")
    p.add_argument("output", help="Output VRM file")
    p.add_argument("--title", default="", help="VRM title")
    p.add_argument("--author", default="", help="VRM author")
    p.add_argument("--version", default="0", choices=["0", "1"], help="VRM version")
    return p.parse_args(argv)


def clean_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for block in bpy.data.meshes:
        bpy.data.meshes.remove(block)
    for block in bpy.data.armatures:
        bpy.data.armatures.remove(block)


def main() -> None:
    args = parse_args()

    clean_scene()

    # Import FBX
    print(f"Importing FBX: {args.input}")
    bpy.ops.import_scene.fbx(filepath=args.input)

    # Select all objects
    bpy.ops.object.select_all(action="SELECT")

    # Find armature and set as active
    armature = None
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE":
            armature = obj
            break

    if armature is None:
        print("ERROR: No armature found in FBX file")
        sys.exit(1)

    bpy.context.view_layer.objects.active = armature

    # Export as VRM
    print(f"Exporting VRM: {args.output}")
    bpy.ops.export_scene.vrm(filepath=args.output)
    print("Done")


if __name__ == "__main__":
    main()
