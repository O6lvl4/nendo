"""Low-level GLB (binary glTF) reader/writer.

VRM files are GLB files with VRM-specific extensions in the JSON chunk.
This module handles the binary container format directly, giving full
control over extension data without depending on any glTF library.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

GLB_MAGIC = 0x46546C67  # 'glTF'
GLB_VERSION = 2
CHUNK_JSON = 0x4E4F534A
CHUNK_BIN = 0x004E4942


class GlbFile:
    __slots__ = ("json_data", "bin_data")

    def __init__(self, json_data: dict[str, Any], bin_data: bytes = b"") -> None:
        self.json_data = json_data
        self.bin_data = bin_data

    # ---- I/O ----

    @classmethod
    def load(cls, path: str | Path) -> GlbFile:
        data = Path(path).read_bytes()
        if len(data) < 12:
            raise ValueError("File too small to be GLB")

        magic, version, total_length = struct.unpack_from("<III", data, 0)
        if magic != GLB_MAGIC:
            raise ValueError(f"Not a GLB file (magic: {magic:#010x})")
        if version != GLB_VERSION:
            raise ValueError(f"Unsupported GLB version: {version}")

        offset = 12
        json_obj: dict[str, Any] | None = None
        bin_bytes = b""

        while offset < total_length and offset + 8 <= len(data):
            chunk_len, chunk_type = struct.unpack_from("<II", data, offset)
            offset += 8
            chunk_data = data[offset : offset + chunk_len]
            offset += chunk_len

            if chunk_type == CHUNK_JSON:
                json_obj = json.loads(chunk_data)
            elif chunk_type == CHUNK_BIN:
                bin_bytes = chunk_data

        if json_obj is None:
            raise ValueError("GLB file has no JSON chunk")

        return cls(json_obj, bin_bytes)

    def save(self, path: str | Path) -> None:
        json_bytes = json.dumps(
            self.json_data, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        # Pad JSON to 4-byte boundary with spaces (per glTF spec)
        json_pad = (4 - len(json_bytes) % 4) % 4
        json_bytes += b" " * json_pad

        has_bin = bool(self.bin_data)
        bin_bytes = self.bin_data
        bin_pad = 0
        if has_bin:
            bin_pad = (4 - len(bin_bytes) % 4) % 4

        total = 12 + 8 + len(json_bytes)
        if has_bin:
            total += 8 + len(bin_bytes) + bin_pad

        out = bytearray()
        out += struct.pack("<III", GLB_MAGIC, GLB_VERSION, total)
        out += struct.pack("<II", len(json_bytes), CHUNK_JSON)
        out += json_bytes
        if has_bin:
            out += struct.pack("<II", len(bin_bytes) + bin_pad, CHUNK_BIN)
            out += bin_bytes
            out += b"\x00" * bin_pad

        Path(path).write_bytes(bytes(out))
