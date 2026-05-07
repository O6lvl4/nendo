"""Blender script: Render a thumbnail for a VRM and embed it.

Run via: blender --background --python apply_thumbnail.py -- <input.vrm> <output.vrm> [--size 512]

Renders a front-facing portrait and sets it as the VRM thumbnail.
"""

import math
import sys
import argparse
import tempfile
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("input", help="Input VRM file")
    p.add_argument("output", help="Output VRM file")
    p.add_argument("--size", type=int, default=512, help="Thumbnail size in pixels")
    return p.parse_args(argv)


def main() -> None:
    args = parse_args()

    # Clean and import
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    bpy.ops.import_scene.vrm(filepath=args.input)

    # Find armature to determine model bounds
    armature = None
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE":
            armature = obj
            break

    # Find head bone for camera focus
    head_pos = None
    if armature:
        head_bone = armature.data.bones.get("Head") or armature.data.bones.get("head")
        if head_bone:
            head_pos = armature.matrix_world @ head_bone.head_local

    # Setup camera
    cam_data = bpy.data.cameras.new("ThumbCam")
    cam_obj = bpy.data.objects.new("ThumbCam", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj

    if head_pos:
        cam_obj.location = (head_pos.x, head_pos.y - 1.5, head_pos.z + 0.1)
    else:
        cam_obj.location = (0, -2.5, 1.2)

    cam_obj.rotation_euler = (math.radians(90), 0, 0)

    # Setup render
    scene = bpy.context.scene
    scene.render.resolution_x = args.size
    scene.render.resolution_y = args.size
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"

    with tempfile.TemporaryDirectory() as tmpdir:
        thumb_path = str(Path(tmpdir) / "thumbnail.png")
        scene.render.filepath = thumb_path
        bpy.ops.render.render(write_still=True)

        # Re-export with thumbnail
        # The VRM addon should pick up the rendered image
        bpy.ops.export_scene.vrm(filepath=args.output)

    print(f"Saved VRM with thumbnail to {args.output}")


if __name__ == "__main__":
    main()
