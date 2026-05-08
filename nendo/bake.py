"""Shape key baking — permanently apply morph target weights into base geometry."""

from __future__ import annotations

import struct
from typing import Any

from nendo.vrm import Vrm, VrmVersion


def _read_accessor_floats(glb, accessor_idx: int) -> list[float]:
    """Read float data from a glTF accessor."""
    acc = glb.json_data["accessors"][accessor_idx]
    bv = glb.json_data["bufferViews"][acc["bufferView"]]
    offset = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    count = acc["count"]

    # Determine number of components
    type_sizes = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
    components = type_sizes.get(acc["type"], 1)
    total = count * components

    # Only handle float (5126)
    if acc.get("componentType", 5126) != 5126:
        raise ValueError(f"Unsupported component type: {acc.get('componentType')}")

    stride = bv.get("byteStride", components * 4)
    result = []
    for i in range(count):
        base = offset + i * stride
        for c in range(components):
            val = struct.unpack_from("<f", glb.bin_data, base + c * 4)[0]
            result.append(val)
    return result


def _write_accessor_floats(glb, accessor_idx: int, data: list[float]) -> None:
    """Write float data back to a glTF accessor's buffer."""
    acc = glb.json_data["accessors"][accessor_idx]
    bv = glb.json_data["bufferViews"][acc["bufferView"]]
    offset = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)

    type_sizes = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
    components = type_sizes.get(acc["type"], 1)
    stride = bv.get("byteStride", components * 4)

    bin_data = bytearray(glb.bin_data)
    idx = 0
    for i in range(acc["count"]):
        base = offset + i * stride
        for c in range(components):
            struct.pack_into("<f", bin_data, base + c * 4, data[idx])
            idx += 1
    glb.bin_data = bytes(bin_data)


def _get_expression_morph_targets(vrm: Vrm) -> set[tuple[int, int]]:
    """Return set of (mesh_index, morph_target_index) used by VRM expressions."""
    used = set()
    if vrm.version == VrmVersion.V0:
        groups = vrm.expressions.get("blendShapeGroups", [])
        for g in groups:
            for b in g.get("binds", []):
                used.add((b.get("mesh", 0), b.get("index", 0)))
    elif vrm.version == VrmVersion.V1:
        for category in ("preset", "custom"):
            exprs = vrm.expressions.get(category, {})
            for expr in exprs.values():
                for b in expr.get("morphTargetBinds", []):
                    used.add((b.get("node", 0), b.get("index", 0)))
    return used


def bake_shape_keys(
    vrm: Vrm,
    targets: dict[str, dict[str, float]],
) -> dict[str, list[str]]:
    """Bake shape key weights into base geometry.

    Args:
        vrm: The VRM to modify in place.
        targets: { mesh_name: { shape_key_name: weight } }
            weight should be 0.0-1.0

    Returns:
        { mesh_name: [baked_key_names] } — which keys were baked per mesh.
    """
    glb = vrm.glb
    gltf = glb.json_data
    meshes = gltf.get("meshes", [])
    expression_targets = _get_expression_morph_targets(vrm)

    result: dict[str, list[str]] = {}

    for mesh_idx, mesh in enumerate(meshes):
        mesh_name = mesh.get("name", f"mesh_{mesh_idx}")
        if mesh_name not in targets:
            continue

        edits = targets[mesh_name]
        if not edits:
            continue

        baked_keys: list[str] = []

        for prim_idx, prim in enumerate(mesh.get("primitives", [])):
            morph_targets = prim.get("targets", [])
            if not morph_targets:
                continue

            # Get target names
            target_names = (
                mesh.get("extras", {}).get("targetNames", [])
                or prim.get("extras", {}).get("targetNames", [])
            )

            # Read base POSITION accessor
            pos_accessor = prim.get("attributes", {}).get("POSITION")
            if pos_accessor is None:
                continue

            base_positions = _read_accessor_floats(glb, pos_accessor)

            # Apply each edit
            indices_to_remove = []
            for target_idx, morph in enumerate(morph_targets):
                name = target_names[target_idx] if target_idx < len(target_names) else f"target_{target_idx}"
                weight = edits.get(name)
                if weight is None or weight == 0:
                    continue

                # Skip if this morph target is used by VRM expressions
                if (mesh_idx, target_idx) in expression_targets:
                    continue

                # Read morph target POSITION deltas
                morph_pos_accessor = morph.get("POSITION")
                if morph_pos_accessor is None:
                    continue

                deltas = _read_accessor_floats(glb, morph_pos_accessor)

                # Add weighted deltas to base positions
                for i in range(len(base_positions)):
                    base_positions[i] += deltas[i] * weight

                indices_to_remove.append(target_idx)
                if name not in baked_keys:
                    baked_keys.append(name)

            # Write modified base positions back
            if indices_to_remove:
                _write_accessor_floats(glb, pos_accessor, base_positions)

                # Also bake NORMAL if present
                norm_accessor = prim.get("attributes", {}).get("NORMAL")
                if norm_accessor is not None:
                    base_normals = _read_accessor_floats(glb, norm_accessor)
                    for target_idx in indices_to_remove:
                        morph = morph_targets[target_idx]
                        morph_norm = morph.get("NORMAL")
                        if morph_norm is None:
                            continue
                        name = target_names[target_idx] if target_idx < len(target_names) else ""
                        weight = edits.get(name, 0)
                        if weight == 0:
                            continue
                        deltas = _read_accessor_floats(glb, morph_norm)
                        for i in range(len(base_normals)):
                            base_normals[i] += deltas[i] * weight
                    _write_accessor_floats(glb, norm_accessor, base_normals)

            # Remove baked targets (reverse order to preserve indices)
            for idx in sorted(indices_to_remove, reverse=True):
                morph_targets.pop(idx)
                if idx < len(target_names):
                    target_names.pop(idx)

            # Update target names in extras
            if target_names:
                if mesh.get("extras", {}).get("targetNames"):
                    mesh["extras"]["targetNames"] = target_names
                if prim.get("extras", {}).get("targetNames"):
                    prim["extras"]["targetNames"] = target_names

        # Update mesh weights array
        weights = mesh.get("weights", [])
        if weights and indices_to_remove:
            for idx in sorted(indices_to_remove, reverse=True):
                if idx < len(weights):
                    weights.pop(idx)
            mesh["weights"] = weights

        # Update VRM expression bind indices (shift down for removed targets)
        if indices_to_remove:
            _update_expression_indices(vrm, mesh_idx, sorted(indices_to_remove))

        if baked_keys:
            result[mesh_name] = baked_keys

    return result


def _update_expression_indices(
    vrm: Vrm, mesh_idx: int, removed_indices: list[int]
) -> None:
    """Shift morph target indices in VRM expression binds after removal."""
    def shift(old_idx: int) -> int:
        offset = sum(1 for r in removed_indices if r < old_idx)
        return old_idx - offset

    if vrm.version == VrmVersion.V0:
        groups = vrm.expressions.get("blendShapeGroups", [])
        for g in groups:
            for b in g.get("binds", []):
                if b.get("mesh") == mesh_idx:
                    b["index"] = shift(b["index"])
    elif vrm.version == VrmVersion.V1:
        for category in ("preset", "custom"):
            exprs = vrm.expressions.get(category, {})
            for expr in exprs.values():
                for b in expr.get("morphTargetBinds", []):
                    if b.get("node") == mesh_idx:
                        b["index"] = shift(b["index"])
