"""VRM 0.x → 1.0 migration."""

from __future__ import annotations

from typing import Any

from nendo.vrm import Vrm, VrmVersion


# VRM 0.x bone name → VRM 1.0 humanBones key
BONE_MAP_0_TO_1: dict[str, str] = {
    "hips": "hips", "spine": "spine", "chest": "chest",
    "upperChest": "upperChest", "neck": "neck", "head": "head",
    "leftEye": "leftEye", "rightEye": "rightEye", "jaw": "jaw",
    "leftShoulder": "leftShoulder",
    "leftUpperArm": "leftUpperArm", "leftLowerArm": "leftLowerArm", "leftHand": "leftHand",
    "rightShoulder": "rightShoulder",
    "rightUpperArm": "rightUpperArm", "rightLowerArm": "rightLowerArm", "rightHand": "rightHand",
    "leftUpperLeg": "leftUpperLeg", "leftLowerLeg": "leftLowerLeg",
    "leftFoot": "leftFoot", "leftToes": "leftToes",
    "rightUpperLeg": "rightUpperLeg", "rightLowerLeg": "rightLowerLeg",
    "rightFoot": "rightFoot", "rightToes": "rightToes",
    "leftThumbProximal": "leftThumbMetacarpal",
    "leftThumbIntermediate": "leftThumbProximal",
    "leftThumbDistal": "leftThumbDistal",
    "leftIndexProximal": "leftIndexProximal",
    "leftIndexIntermediate": "leftIndexIntermediate",
    "leftIndexDistal": "leftIndexDistal",
    "leftMiddleProximal": "leftMiddleProximal",
    "leftMiddleIntermediate": "leftMiddleIntermediate",
    "leftMiddleDistal": "leftMiddleDistal",
    "leftRingProximal": "leftRingProximal",
    "leftRingIntermediate": "leftRingIntermediate",
    "leftRingDistal": "leftRingDistal",
    "leftLittleProximal": "leftLittleProximal",
    "leftLittleIntermediate": "leftLittleIntermediate",
    "leftLittleDistal": "leftLittleDistal",
    "rightThumbProximal": "rightThumbMetacarpal",
    "rightThumbIntermediate": "rightThumbProximal",
    "rightThumbDistal": "rightThumbDistal",
    "rightIndexProximal": "rightIndexProximal",
    "rightIndexIntermediate": "rightIndexIntermediate",
    "rightIndexDistal": "rightIndexDistal",
    "rightMiddleProximal": "rightMiddleProximal",
    "rightMiddleIntermediate": "rightMiddleIntermediate",
    "rightMiddleDistal": "rightMiddleDistal",
    "rightRingProximal": "rightRingProximal",
    "rightRingIntermediate": "rightRingIntermediate",
    "rightRingDistal": "rightRingDistal",
    "rightLittleProximal": "rightLittleProximal",
    "rightLittleIntermediate": "rightLittleIntermediate",
    "rightLittleDistal": "rightLittleDistal",
}

# VRM 0.x expression preset → VRM 1.0 expression preset
EXPRESSION_MAP: dict[str, str] = {
    "neutral": "neutral",
    "a": "aa", "i": "ih", "u": "ou", "e": "ee", "o": "oh",
    "blink": "blink", "blink_l": "blinkLeft", "blink_r": "blinkRight",
    "joy": "happy", "angry": "angry", "sorrow": "sad",
    "fun": "relaxed", "surprised": "surprised",
    "lookup": "lookUp", "lookdown": "lookDown",
    "lookleft": "lookLeft", "lookright": "lookRight",
}

LICENSE_MAP: dict[str, str] = {
    "Redistribution_Prohibited": "https://vrm.dev/licenses/1.0/",
    "CC0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "CC_BY": "https://creativecommons.org/licenses/by/4.0/",
    "CC_BY_NC": "https://creativecommons.org/licenses/by-nc/4.0/",
    "CC_BY_SA": "https://creativecommons.org/licenses/by-sa/4.0/",
    "CC_BY_NC_SA": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
    "CC_BY_ND": "https://creativecommons.org/licenses/by-nd/4.0/",
    "CC_BY_NC_ND": "https://creativecommons.org/licenses/by-nc-nd/4.0/",
    "Other": "https://vrm.dev/licenses/1.0/",
}

ALLOWED_USER_MAP: dict[str, str] = {
    "OnlyAuthor": "onlyAuthor",
    "ExplicitlyLicensedPerson": "onlySeparatelyLicensedPerson",
    "Everyone": "everyone",
}

USAGE_MAP: dict[str, str] = {
    "Allow": "allow",
    "Disallow": "disallow",
}


def migrate_0_to_1(vrm: Vrm) -> Vrm:
    """Migrate a VRM 0.x file to VRM 1.0 in-place and return it."""
    if vrm.version != VrmVersion.V0:
        raise ValueError(f"Expected VRM 0.x, got {vrm.version.value}")

    v0 = vrm.extensions.get("VRM", {})
    gltf = vrm.glb.json_data

    # ---- VRMC_vrm ----
    vrmc: dict[str, Any] = {"specVersion": "1.0"}

    # Meta
    m0 = v0.get("meta", {})
    vrmc["meta"] = {
        "name": m0.get("title", ""),
        "version": m0.get("version", ""),
        "authors": [m0["author"]] if m0.get("author") else [],
        "contactInformation": m0.get("contactInformation", ""),
        "references": [m0["reference"]] if m0.get("reference") else [],
        "licenseUrl": LICENSE_MAP.get(m0.get("licenseName", ""), "https://vrm.dev/licenses/1.0/"),
        "avatarPermission": ALLOWED_USER_MAP.get(m0.get("allowedUserName", ""), "onlyAuthor"),
        "allowExcessivelyViolentUsage": USAGE_MAP.get(m0.get("violentUssageName", ""), "disallow") == "allow",
        "allowExcessivelySexualUsage": USAGE_MAP.get(m0.get("sexualUssageName", ""), "disallow") == "allow",
        "commercialUsage": "allow" if USAGE_MAP.get(m0.get("commercialUssageName", "")) == "allow" else "personalNonProfit",
        "allowRedistribution": False,
        "modification": "prohibited",
    }
    if m0.get("texture") is not None:
        vrmc["meta"]["thumbnailImage"] = m0["texture"]

    # Humanoid
    bones_v0 = v0.get("humanoid", {}).get("humanBones", [])
    human_bones_v1: dict[str, Any] = {}
    for b in bones_v0:
        name_v0 = b.get("bone", "")
        name_v1 = BONE_MAP_0_TO_1.get(name_v0)
        if name_v1 and b.get("node") is not None:
            human_bones_v1[name_v1] = {"node": b["node"]}
    vrmc["humanoid"] = {"humanBones": human_bones_v1}

    # Expressions
    blend_groups = v0.get("blendShapeMaster", {}).get("blendShapeGroups", [])
    preset_exprs: dict[str, Any] = {}
    custom_exprs: dict[str, Any] = {}
    for g in blend_groups:
        preset_v0 = g.get("presetName", "").lower()
        name_v1 = EXPRESSION_MAP.get(preset_v0)
        expr: dict[str, Any] = {}
        binds = g.get("binds", [])
        if binds:
            expr["morphTargetBinds"] = [
                {"node": b.get("mesh", 0), "index": b.get("index", 0), "weight": b.get("weight", 0) / 100}
                for b in binds
            ]
        if g.get("isBinary"):
            expr["isBinary"] = True
        if name_v1:
            preset_exprs[name_v1] = expr
        else:
            custom_exprs[g.get("name", "custom")] = expr
    vrmc["expressions"] = {"preset": preset_exprs, "custom": custom_exprs}

    # LookAt
    fp0 = v0.get("firstPerson", {})
    look_type = fp0.get("lookAtTypeName", "")
    if look_type:
        look_at: dict[str, Any] = {"type": "bone" if look_type == "Bone" else "expression"}
        bone_offset = fp0.get("firstPersonBoneOffset", {})
        if bone_offset:
            look_at["offsetFromHeadBone"] = [
                bone_offset.get("x", 0), bone_offset.get("y", 0), bone_offset.get("z", 0)
            ]
        for v0_key, v1_key in [
            ("lookAtHorizontalInner", "rangeMapHorizontalInner"),
            ("lookAtHorizontalOuter", "rangeMapHorizontalOuter"),
            ("lookAtVerticalDown", "rangeMapVerticalDown"),
            ("lookAtVerticalUp", "rangeMapVerticalUp"),
        ]:
            rm = fp0.get(v0_key, {})
            if rm:
                look_at[v1_key] = {
                    "inputMaxValue": rm.get("xRange", 90),
                    "outputScale": rm.get("yRange", 10),
                }
        vrmc["lookAt"] = look_at

    # FirstPerson
    mesh_anns = fp0.get("meshAnnotations", [])
    if mesh_anns:
        vrmc["firstPerson"] = {
            "meshAnnotations": [
                {"node": a.get("mesh", 0), "type": a.get("firstPersonFlag", "auto").lower()}
                for a in mesh_anns
            ]
        }

    # ---- MToon Materials ----
    MTOON_FLOAT_MAP = {
        "_ShadeShift": "shadingShiftFactor",
        "_ShadeToony": "shadingToonyFactor",
        "_RimFresnelPower": "parametricRimFresnelPowerFactor",
        "_RimLift": "parametricRimLiftFactor",
        "_OutlineWidth": "outlineWidthFactor",
        "_OutlineLightingMix": "outlineLightingMixFactor",
        "_UvAnimScrollX": "uvAnimationScrollXSpeedFactor",
        "_UvAnimScrollY": "uvAnimationScrollYSpeedFactor",
        "_UvAnimRotation": "uvAnimationRotationSpeedFactor",
    }
    MTOON_VECTOR_MAP = {
        "_ShadeColor": "shadeColorFactor",
        "_RimColor": "parametricRimColorFactor",
        "_OutlineColor": "outlineColorFactor",
    }
    MTOON_TEX_MAP = {
        "_ShadeTexture": "shadeMultiplyTexture",
        "_SphereAdd": "matcapTexture",
        "_RimTexture": "rimMultiplyTexture",
        "_OutlineWidthTexture": "outlineWidthMultiplyTexture",
        "_UvAnimMaskTexture": "uvAnimationMaskTexture",
    }
    OUTLINE_MODE_MAP = {0: "none", 1: "worldCoordinates", 2: "screenCoordinates"}

    mat_props = v0.get("materialProperties", [])
    gltf_mats = gltf.get("materials", [])
    for i, mp in enumerate(mat_props):
        shader = mp.get("shader", "")
        if "MToon" not in shader and "VRM/MToon" not in shader:
            continue
        if i >= len(gltf_mats):
            continue
        floats = mp.get("floatProperties", {})
        vectors = mp.get("vectorProperties", {})
        textures = mp.get("textureProperties", {})

        mtoon: dict[str, Any] = {"specVersion": "1.0"}
        for v0_key, v1_key in MTOON_FLOAT_MAP.items():
            v = floats.get(v0_key)
            if v is not None:
                mtoon[v1_key] = v
        for v0_key, v1_key in MTOON_VECTOR_MAP.items():
            v = vectors.get(v0_key)
            if v and len(v) >= 3:
                mtoon[v1_key] = v[:3]
        for v0_key, v1_key in MTOON_TEX_MAP.items():
            v = textures.get(v0_key)
            if v is not None:
                mtoon[v1_key] = {"index": v}
        outline_mode = floats.get("_OutlineWidthMode")
        if outline_mode is not None:
            mtoon["outlineWidthMode"] = OUTLINE_MODE_MAP.get(int(outline_mode), "none")

        gltf_mats[i].setdefault("extensions", {})["VRMC_materials_mtoon"] = mtoon

    # ---- Write extensions ----
    gltf.setdefault("extensions", {})["VRMC_vrm"] = vrmc

    # SpringBone → VRMC_springBone
    sec = v0.get("secondaryAnimation", {})
    bone_groups = sec.get("boneGroups", [])
    collider_groups_v0 = sec.get("colliderGroups", [])
    if bone_groups:
        springs = []
        for g in bone_groups:
            joints = []
            for bone_idx in g.get("bones", []):
                joints.append({
                    "node": bone_idx,
                    "hitRadius": g.get("hitRadius", 0.02),
                    "stiffness": g.get("stiffiness", 1.0),
                    "gravityPower": g.get("gravityPower", 0),
                    "gravityDir": g.get("gravityDir", {"x": 0, "y": -1, "z": 0}),
                    "dragForce": g.get("dragForce", 0.4),
                })
            spring: dict[str, Any] = {"joints": joints}
            cg_indices = g.get("colliderGroups", [])
            if cg_indices:
                spring["colliderGroups"] = cg_indices
            springs.append(spring)

        colliders_v1 = []
        collider_groups_v1 = []
        for cg in collider_groups_v0:
            group_collider_indices = []
            for c in cg.get("colliders", []):
                offset = c.get("offset", {"x": 0, "y": 0, "z": 0})
                colliders_v1.append({
                    "node": cg.get("node", 0),
                    "shape": {"sphere": {"offset": [offset.get("x", 0), offset.get("y", 0), offset.get("z", 0)], "radius": c.get("radius", 0.05)}},
                })
                group_collider_indices.append(len(colliders_v1) - 1)
            collider_groups_v1.append({"colliders": group_collider_indices})

        sb_ext: dict[str, Any] = {"specVersion": "1.0", "springs": springs}
        if colliders_v1:
            sb_ext["colliders"] = colliders_v1
            sb_ext["colliderGroups"] = collider_groups_v1
        gltf["extensions"]["VRMC_springBone"] = sb_ext

    # Register used extensions
    used = gltf.setdefault("extensionsUsed", [])
    for ext in ("VRMC_vrm", "VRMC_springBone", "VRMC_materials_mtoon"):
        if ext in gltf.get("extensions", {}) and ext not in used:
            used.append(ext)

    # Remove old VRM extension
    gltf["extensions"].pop("VRM", None)
    if "VRM" in used:
        used.remove("VRM")

    # Update version detection
    vrm._version = VrmVersion.V1

    return vrm
