"""Fetch the pinned shader-tool sources for release engineering, never an editor export."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from urllib.request import urlopen

REVISION = "31e25af254ab572c77054edec4946d2244e184dd"
SHA256 = "b439c354642fa7f19249e62b0e58fc7e4810442e2740998b586f9901eed58d68"

def require_dependencies(source: Path) -> None:
    # The pinned upstream fetch script does not propagate failed git subprocesses.
    # Do not cache an incomplete result as a successful toolchain download.
    for relative in (
        "third_party/abseil-cpp/CMakeLists.txt",
        "third_party/spirv-headers/src/CMakeLists.txt",
        "third_party/spirv-tools/src/CMakeLists.txt",
        "third_party/glslang/src/CMakeLists.txt",
        "third_party/protobuf/CMakeLists.txt",
    ):
        if not (source / relative).is_file():
            raise FileNotFoundError(
                f"Dawn dependency download is incomplete: {source / relative}"
            )


def prepare(destination: Path) -> Path:
    destination = destination.resolve()
    if destination.is_dir():
        require_dependencies(destination)
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".dawn-", dir=destination.parent) as temporary:
        workspace = Path(temporary)
        archive = workspace / "source.tar.gz"
        with urlopen(f"https://codeload.github.com/google/dawn/tar.gz/{REVISION}",
                     timeout=30) as response, archive.open("wb") as stream:
            shutil.copyfileobj(response, stream)
        with archive.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != SHA256:
                raise ValueError("Downloaded Dawn source does not match the pinned release")
        with tarfile.open(archive) as source:
            source.extractall(workspace, filter="data")
        extracted = workspace / f"dawn-{REVISION}"
        subprocess.run([sys.executable, str(extracted / "tools/fetch_dawn_dependencies.py"),
                        "--directory", str(extracted)], check=True)
        require_dependencies(extracted)
        extracted.replace(destination)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    print(prepare(parser.parse_args().destination))
