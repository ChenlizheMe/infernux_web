"""Build this repository's standalone InxPackage and GitHub release manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import package


def build_release(tag: str, output: Path | None = None) -> tuple[Path, Path]:
    root = Path(__file__).resolve().parent
    metadata = json.loads((root / "package/inx_package.json").read_text(encoding="utf-8"))
    expected = f"v{metadata['version']}"
    if tag != expected:
        raise ValueError(f"Release tag must match package version: {expected}")
    destination = output if output is not None else root / "dist"
    destination.mkdir(parents=True, exist_ok=True)
    stem = metadata["reference"].replace("/", ".")
    artifact = package.build(destination / f"{stem}.inxpkg")
    manifest = destination / f"{stem}.release.json"
    document = {
        "$schema": "infernux.plugin_release",
        "reference": metadata["reference"],
        "version": metadata["version"],
        "engine": metadata["engine"],
        "artifact": {"name": artifact.name},
        "generator": "Infernux platform package release.py",
        "release_tag": tag,
    }
    manifest.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return artifact, manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", help="v followed by package/inx_package.json version")
    arguments = parser.parse_args()
    for path in build_release(arguments.tag):
        print(path)
