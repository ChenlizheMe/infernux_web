"""Build and publish the project-independent Web runtime (release engineering)."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emsdk", required=True, type=Path)
    parser.add_argument("--cpython-source", required=True, type=Path)
    parser.add_argument("--build-root", required=True, type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    subprocess.run([
        str(args.emsdk.resolve() / "upstream/emscripten/emcmake"), "cmake",
        "-S", str(source), "-B", str(args.build_root.resolve()), "-G", "Ninja",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DINFERNUX_WEB_CPYTHON_SOURCE={args.cpython_source.resolve()}",
        f"-DINFERNUX_WEB_CPYTHON_BUILD={args.cpython_source.resolve() / 'builddir/emscripten-browser'}",
    ], check=True)
    subprocess.run(["cmake", "--build", str(args.build_root.resolve()),
                    "--target", "prebuild_web_player", "--parallel", "2"], check=True)


if __name__ == "__main__":
    main()
