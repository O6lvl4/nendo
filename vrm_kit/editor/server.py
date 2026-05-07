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

from vrm_kit.vrm import Vrm

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
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def _save_spring_bone(self, data: dict) -> None:
        from vrm_kit.vrm import VrmVersion

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
