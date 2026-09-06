"""Packaging tests run without installing Infernux or a platform SDK."""

import json
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        source = Path(__file__).resolve().parents[1]
        shutil.copytree(source / "package", self.root / "package",
                        ignore=shutil.ignore_patterns("player", "tools", "__pycache__"))
        self.payload = self.root / "package/editor/infernux_web"
        player = self.payload / "player"
        player.mkdir()
        (player / "Player.inxmanifest").write_text(json.dumps({
            "$schema": "infernux.web_player", "engine": "0.4.0", "platform": "web",
            "architecture": "wasm32", "python_abi": "cp313", "configuration": "Release",
        }), encoding="utf-8")
        (player / "infernux-runtime.wasm").write_bytes(b"\0asm\x01\0\0\0")
        (player / "infernux-runtime.js").write_bytes(b"// runtime fixture")
        (player / "infernux-runtime.data").write_bytes(b"python fixture")
        for host, suffix in (("windows-x64", ".exe"), ("linux-x64", "")):
            directory = self.payload / "tools" / host
            directory.mkdir(parents=True)
            header = b"MZ" if suffix else b"\x7fELF\x02\x01" + bytes(12) + (62).to_bytes(2, "little")
            for name in ("tint", "glslangValidator"):
                (directory / f"{name}{suffix}").write_bytes(header)
        for module in (release, release.package):
            override = patch.object(module, "__file__", str(self.root / Path(module.__file__).name))
            override.start()
            self.addCleanup(override.stop)

    def test_release_requires_both_host_tool_payloads(self):
        (self.payload / "tools/linux-x64/tint").unlink()
        with self.assertRaises(FileNotFoundError):
            release.build_release("v0.2.0")
        self.assertFalse((self.root / "dist").exists())

    def test_release_rejects_wrong_wasm(self):
        (self.payload / "player/infernux-runtime.wasm").write_bytes(b"not wasm")
        with self.assertRaisesRegex(ValueError, "WebAssembly"):
            release.build_release("v0.2.0")

    def test_package_and_manifest(self):
        root = Path(__file__).resolve().parents[1]
        source = json.loads((root / "package/inx_package.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporary:
            artifact, manifest = release.build_release(f"v{source['version']}", Path(temporary))
            document = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(document["artifact"]["name"], artifact.name)
            self.assertEqual(document["reference"], source["reference"])
            self.assertEqual(document["engine"], source["engine"])
            self.assertEqual(artifact.read_bytes()[:8], b"INXPKG\0\0")
            self.assertGreater(artifact.stat().st_size, 1024)
        self.assertTrue((root / "package/plugin_pages/media/overview.png").is_file())
        for name in ("README.md", "README.zh-CN.md"):
            self.assertIn("package/plugin_pages/media/overview.png", (root / name).read_text(encoding="utf-8"))

    def test_reject_mismatched_tag(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "Release tag must match"):
                release.build_release("v999.0.0", Path(temporary))
            self.assertEqual(list(Path(temporary).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
