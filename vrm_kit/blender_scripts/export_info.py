"""Blender script: Import VRM and print detailed info via Blender's data model.

Run via: blender --background --python export_info.py -- <input.vrm>

Provides info that's hard to get from raw glTF: actual vertex counts,
shape key names, modifier stacks, etc.
"""

import json
import sys

import bpy


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    if not argv:
        print("Usage: blender --background --python export_info.py -- <input.vrm>")
        sys.exit(1)

    vrm_path = argv[0]

    # Clean and import
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    bpy.ops.import_scene.vrm(filepath=vrm_path)

    result: dict = {"meshes": [], "armature": None, "shape_keys": {}}

    for obj in bpy.data.objects:
        if obj.type == "MESH":
            mesh_info = {
                "name": obj.name,
                "vertices": len(obj.data.vertices),
                "polygons": len(obj.data.polygons),
                "materials": [m.name for m in obj.data.materials if m],
            }
            # Shape keys
            if obj.data.shape_keys:
                keys = [kb.name for kb in obj.data.shape_keys.key_blocks]
                mesh_info["shape_keys"] = keys
                result["shape_keys"][obj.name] = keys
            result["meshes"].append(mesh_info)

        elif obj.type == "ARMATURE":
            bones = []
            for bone in obj.data.bones:
                bones.append({
                    "name": bone.name,
                    "parent": bone.parent.name if bone.parent else None,
                    "head": list(bone.head_local),
                    "tail": list(bone.tail_local),
                    "length": bone.length,
                })
            result["armature"] = {
                "name": obj.name,
                "bone_count": len(bones),
                "bones": bones,
            }

    print("===JSON_START===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("===JSON_END===")


if __name__ == "__main__":
    main()
