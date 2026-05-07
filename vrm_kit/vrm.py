"""Core VRM model — version-aware access to VRM extensions."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from vrm_kit.glb import GlbFile


class VrmVersion(Enum):
    V0 = "0.x"
    V1 = "1.0"
    UNKNOWN = "unknown"


class Vrm:
    """Thin wrapper over a GLB file that provides VRM-specific accessors."""

    __slots__ = ("glb", "_version")

    def __init__(self, glb: GlbFile) -> None:
        self.glb = glb
        self._version = self._detect_version()

    @classmethod
    def load(cls, path: str | Path) -> Vrm:
        return cls(GlbFile.load(path))

    def save(self, path: str | Path) -> None:
        self.glb.save(path)

    # ---- Version ----

    @property
    def version(self) -> VrmVersion:
        return self._version

    def _detect_version(self) -> VrmVersion:
        ext = self.extensions
        if "VRMC_vrm" in ext:
            return VrmVersion.V1
        if "VRM" in ext:
            return VrmVersion.V0
        return VrmVersion.UNKNOWN

    # ---- Raw extension access ----

    @property
    def extensions(self) -> dict[str, Any]:
        return self.glb.json_data.get("extensions", {})

    @property
    def _vrm_root(self) -> dict[str, Any]:
        """The top-level VRM extension object."""
        if self._version == VrmVersion.V1:
            return self.extensions.get("VRMC_vrm", {})
        return self.extensions.get("VRM", {})

    # ---- Meta ----

    @property
    def meta(self) -> dict[str, Any]:
        return dict(self._vrm_root.get("meta", {}))

    @meta.setter
    def meta(self, value: dict[str, Any]) -> None:
        if self._version == VrmVersion.V1:
            self.extensions.setdefault("VRMC_vrm", {})["meta"] = value
        elif self._version == VrmVersion.V0:
            self.extensions.setdefault("VRM", {})["meta"] = value

    @property
    def title(self) -> str:
        key = "name" if self._version == VrmVersion.V1 else "title"
        return self.meta.get(key, "")

    @title.setter
    def title(self, value: str) -> None:
        m = self.meta
        key = "name" if self._version == VrmVersion.V1 else "title"
        m[key] = value
        self.meta = m

    @property
    def author(self) -> str | list[str]:
        if self._version == VrmVersion.V1:
            return self.meta.get("authors", [])
        return self.meta.get("author", "")

    # ---- Humanoid ----

    @property
    def humanoid(self) -> dict[str, Any]:
        return self._vrm_root.get("humanoid", {})

    @property
    def human_bones(self) -> dict[str, Any] | list[Any]:
        h = self.humanoid
        return h.get("humanBones", {} if self._version == VrmVersion.V1 else [])

    # ---- Expressions / BlendShapes ----

    @property
    def expressions(self) -> dict[str, Any]:
        if self._version == VrmVersion.V1:
            return self._vrm_root.get("expressions", {})
        return self._vrm_root.get("blendShapeMaster", {})

    # ---- Spring Bone ----

    @property
    def spring_bone(self) -> dict[str, Any]:
        if self._version == VrmVersion.V1:
            return self.extensions.get("VRMC_springBone", {})
        return self._vrm_root.get("secondaryAnimation", {})

    # ---- Materials ----

    @property
    def materials(self) -> list[dict[str, Any]]:
        all_mats = self.glb.json_data.get("materials", [])
        if self._version == VrmVersion.V1:
            return [
                m for m in all_mats
                if "VRMC_materials_mtoon" in m.get("extensions", {})
            ]
        return self._vrm_root.get("materialProperties", [])

    # ---- Node tree ----

    @property
    def nodes(self) -> list[dict[str, Any]]:
        return self.glb.json_data.get("nodes", [])

    def root_node_indices(self) -> list[int]:
        scenes = self.glb.json_data.get("scenes", [])
        scene_idx = self.glb.json_data.get("scene", 0)
        if scene_idx < len(scenes):
            return scenes[scene_idx].get("nodes", [])
        return []

    # ---- Stats ----

    def _count(self, key: str) -> int:
        return len(self.glb.json_data.get(key, []))

    def summary(self) -> dict[str, Any]:
        return {
            "version": self._version.value,
            "title": self.title,
            "author": self.author,
            "meshes": self._count("meshes"),
            "nodes": self._count("nodes"),
            "materials": self._count("materials"),
            "textures": self._count("textures"),
            "images": self._count("images"),
            "human_bones": len(self.human_bones),
            "expressions": self._count_expressions(),
            "spring_bone_groups": self._count_spring_bones(),
        }

    def _count_expressions(self) -> int:
        e = self.expressions
        if self._version == VrmVersion.V1:
            return len(e.get("preset", {})) + len(e.get("custom", {}))
        return len(e.get("blendShapeGroups", []))

    def _count_spring_bones(self) -> int:
        sb = self.spring_bone
        if self._version == VrmVersion.V1:
            return len(sb.get("springs", []))
        return len(sb.get("boneGroups", []))
