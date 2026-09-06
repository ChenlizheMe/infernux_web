"""The platform plugin's precompiled browser and host-tool layout."""

from __future__ import annotations

import json
from pathlib import Path

PLAYER_FILES = ("infernux-runtime.js", "infernux-runtime.wasm", "infernux-runtime.data")
HOSTS = ("windows-x64", "linux-x64")


def inspect_player_payload(root: Path, *, engine: str) -> dict[str, object]:
    manifest = json.loads((root / "Player.inxmanifest").read_text(encoding="utf-8"))
    expected = {"$schema": "infernux.web_player", "engine": engine,
                "platform": "web", "architecture": "wasm32", "python_abi": "cp313"}
    if not isinstance(manifest, dict) or any(manifest.get(k) != v for k, v in expected.items()):
        raise ValueError("Web Player payload does not match this engine")
    if manifest.get("configuration") not in {"Release", "RelWithDebInfo"}:
        raise ValueError("Web Player payload must be an optimized native build")
    for name in PLAYER_FILES:
        if not (root / name).is_file():
            raise FileNotFoundError(f"Web platform plugin is missing {root / name}")
    return manifest


def inspect_shader_tools(root: Path, *, host: str) -> dict[str, str]:
    if host not in HOSTS:
        raise ValueError(f"Unsupported Web shader tool host: {host}")
    suffix = ".exe" if host == "windows-x64" else ""
    tools = {"glslang": root / host / f"glslangValidator{suffix}",
             "tint": root / host / f"tint{suffix}"}
    for path in tools.values():
        if not path.is_file():
            raise FileNotFoundError(f"Web platform plugin is missing {path}")
    return {name: str(path) for name, path in tools.items()}
