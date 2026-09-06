"""Packaging tests run without installing Infernux or a platform SDK."""

import json
from pathlib import Path
import tempfile
import unittest

import release


class ReleaseTests(unittest.TestCase):
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
