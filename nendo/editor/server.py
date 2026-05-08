"""Local editor server — serves VRM file + web UI for visual editing."""

from __future__ import annotations

import json
import shutil
import urllib.parse
from functools import partial
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any

from nendo.vrm import Vrm

STATIC_DIR = Path(__file__).parent / "static"


class EditorHandler(SimpleHTTPRequestHandler):
    vrm_path: Path
    vrm: Vrm

    def __init__(self, *args: Any, vrm_path: Path, vrm: Vrm, **kwargs: Any) -> None:
        self._vrm_path = vrm_path
        self._vrm = vrm
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/vrm":
            self._serve_vrm_file()
        elif path == "/api/meta":
            self._json_response(self._vrm.meta)
        elif path == "/api/summary":
            self._json_response(self._vrm.summary())
        elif path == "/api/expressions":
            self._json_response(self._vrm.expressions)
        elif path == "/api/springbone":
            self._json_response(self._vrm.spring_bone)
        elif path.startswith("/api/texture/"):
            self._serve_texture(path)
        elif path == "/api/textures":
            self._list_textures()
        elif path == "/api/presets":
            self._list_presets()
        elif path == "/playground":
            self._serve_file("playground.html", "text/html")
        elif path == "/":
            self._serve_file("index.html", "text/html")
        else:
            super().do_GET()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_body()

        if path == "/api/meta":
            data = json.loads(body)
            self._vrm.meta = data
            self._vrm.save(self._vrm_path)
            self._vrm = Vrm.load(self._vrm_path)
            # Update class-level reference so other requests see it
            type(self)._current_vrm = self._vrm
            self._json_response({"ok": True})
        elif path == "/api/springbone":
            data = json.loads(body)
            self._save_spring_bone(data)
            self._json_response({"ok": True})
        elif path == "/api/save-customization":
            data = json.loads(body)
            self._save_customization(data)
            self._json_response({"ok": True})
        elif path.startswith("/api/texture/"):
            self._replace_texture(path, body)
        elif path == "/api/upload-vrm":
            self._upload_vrm(body)
        elif path == "/api/bake":
            data = json.loads(body)
            self._bake_shape_keys(data)
        elif path == "/api/presets":
            self._save_preset(body)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/presets/"):
            self._delete_preset(path)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def _save_spring_bone(self, data: dict) -> None:
        from nendo.vrm import VrmVersion

        ext = self._vrm.extensions
        if self._vrm.version == VrmVersion.V1:
            ext["VRMC_springBone"] = data
        else:
            vrm_ext = ext.get("VRM", {})
            vrm_ext["secondaryAnimation"] = data
            ext["VRM"] = vrm_ext
        self._vrm.save(self._vrm_path)

    def _save_customization(self, data: dict) -> None:
        """Save morph target weights and material colors back to the GLB."""
        gltf = self._vrm.glb.json_data

        # Morph target weights: { mesh_index: [weight, ...] }
        weights = data.get("weights", {})
        for mesh_idx_str, w_list in weights.items():
            mesh_idx = int(mesh_idx_str)
            meshes = gltf.get("meshes", [])
            if mesh_idx < len(meshes):
                meshes[mesh_idx]["weights"] = w_list

        # Material colors: { material_index: { baseColor: [r,g,b,a], ... } }
        materials = data.get("materials", {})
        for mat_idx_str, props in materials.items():
            mat_idx = int(mat_idx_str)
            mats = gltf.get("materials", [])
            if mat_idx < len(mats):
                mat = mats[mat_idx]
                if "baseColor" in props:
                    mat.setdefault("pbrMetallicRoughness", {})[
                        "baseColorFactor"
                    ] = props["baseColor"]

        self._vrm.save(self._vrm_path)
        self._vrm = Vrm.load(self._vrm_path)

    def _list_textures(self) -> None:
        images = self._vrm.glb.json_data.get("images", [])
        textures = self._vrm.glb.json_data.get("textures", [])
        materials = self._vrm.glb.json_data.get("materials", [])

        # Map texture index -> material names
        tex_to_mats: dict[int, list[str]] = {}
        for mat in materials:
            pbr = mat.get("pbrMetallicRoughness", {})
            tex_idx = pbr.get("baseColorTexture", {}).get("index")
            if tex_idx is not None:
                tex_to_mats.setdefault(tex_idx, []).append(mat.get("name", "?"))

        result = []
        for i, img in enumerate(images):
            bv = self._vrm.glb.json_data["bufferViews"][img["bufferView"]]
            result.append({
                "index": i,
                "name": img.get("name", f"image_{i}"),
                "mimeType": img.get("mimeType", "image/png"),
                "byteLength": bv["byteLength"],
                "materials": tex_to_mats.get(i, []),
            })
        self._json_response(result)

    def _serve_texture(self, path: str) -> None:
        idx = int(path.rsplit("/", 1)[-1])
        try:
            data = self._vrm.glb.extract_image(idx)
        except IndexError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        images = self._vrm.glb.json_data.get("images", [])
        mime = images[idx].get("mimeType", "image/png")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _replace_texture(self, path: str, body: bytes) -> None:
        idx = int(path.rsplit("/", 1)[-1])
        try:
            self._vrm.glb.replace_image(idx, body)
            self._vrm.save(self._vrm_path)
            self._vrm = Vrm.load(self._vrm_path)
            self._json_response({"ok": True})
        except (IndexError, Exception) as e:
            self.send_response(HTTPStatus.BAD_REQUEST)
            self._json_response({"error": str(e)})

    @property
    def _presets_path(self) -> Path:
        return self._vrm_path.with_suffix(".presets.json")

    def _list_presets(self) -> None:
        p = self._presets_path
        data = json.loads(p.read_text("utf-8")) if p.exists() else []
        self._json_response(data)

    def _save_preset(self, body: bytes) -> None:
        preset = json.loads(body)
        p = self._presets_path
        data = json.loads(p.read_text("utf-8")) if p.exists() else []
        # Replace if same name exists
        data = [d for d in data if d.get("name") != preset.get("name")]
        data.append(preset)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        self._json_response({"ok": True})

    def _delete_preset(self, path: str) -> None:
        name = urllib.parse.unquote(path.rsplit("/", 1)[-1])
        p = self._presets_path
        data = json.loads(p.read_text("utf-8")) if p.exists() else []
        data = [d for d in data if d.get("name") != name]
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        self._json_response({"ok": True})

    def _upload_vrm(self, body: bytes) -> None:
        """Replace the current VRM with an uploaded one."""
        # Save to the same path (overwrite)
        self._vrm_path.write_bytes(body)
        self._vrm = Vrm.load(self._vrm_path)
        self._json_response({"ok": True, "summary": self._vrm.summary()})

    def _bake_shape_keys(self, data: dict) -> None:
        from nendo.bake import bake_shape_keys

        targets = data.get("targets", {})
        result = bake_shape_keys(self._vrm, targets)
        self._vrm.save(self._vrm_path)
        self._vrm = Vrm.load(self._vrm_path)
        self._json_response({"ok": True, "baked": result})

    def _serve_vrm_file(self) -> None:
        data = self._vrm_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _serve_file(self, filename: str, content_type: str) -> None:
        filepath = STATIC_DIR / filename
        if not filepath.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = filepath.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json_response(self, data: Any) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length)

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress default logging noise
        pass


def start_server(vrm_path: Path, port: int = 8765) -> None:
    vrm_path = vrm_path.resolve()
    vrm = Vrm.load(vrm_path)

    handler = partial(EditorHandler, vrm_path=vrm_path, vrm=vrm)
    server = HTTPServer(("127.0.0.1", port), handler)

    print(f"VRM Editor: http://localhost:{port}")
    print(f"File: {vrm_path}")
    print("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
        server.server_close()
