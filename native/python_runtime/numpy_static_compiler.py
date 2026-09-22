#!/usr/bin/env python3
"""Turn NumPy's Emscripten extension link steps into deterministic archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


def _expanded(arguments: list[str]) -> list[str]:
    result: list[str] = []
    for argument in arguments:
        if argument.startswith("@"):
            response = Path(argument[1:])
            if not response.is_file():
                raise ValueError(f"compiler response file is missing: {response}")
            result.extend(shlex.split(response.read_text(encoding="utf-8"), posix=True))
        else:
            result.append(argument)
    return result


def _output(arguments: list[str]) -> Path | None:
    for index, argument in enumerate(arguments[:-1]):
        if argument == "-o":
            return Path(arguments[index + 1]).resolve()
    return None


def _write_record(record_dir: Path, output: Path, arguments: list[str]) -> None:
    objects = [str(Path(item).resolve()) for item in arguments if item.endswith((".o", ".obj"))]
    archives = [str(Path(item).resolve()) for item in arguments if item.endswith(".a")]
    if not objects:
        raise ValueError(f"NumPy extension link has no object files: {output}")
    missing = [item for item in objects + archives if not Path(item).is_file()]
    if missing:
        raise ValueError("NumPy extension link input is missing: " + ", ".join(missing))
    record = {
        "schema": "infernux.numpy_static_link.v1",
        "output": str(output),
        "objects": objects,
        "dependency_archives": archives,
        "link_arguments": arguments,
    }
    key = hashlib.sha256(str(output).encode("utf-8")).hexdigest()
    record_dir.mkdir(parents=True, exist_ok=True)
    temporary = record_dir / f".{key}.{os.getpid()}.tmp"
    destination = record_dir / f"{key}.json"
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--driver", required=True, type=Path)
    parser.add_argument("--archiver", required=True, type=Path)
    parser.add_argument("--record-dir", required=True, type=Path)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    options = parser.parse_args()
    arguments = options.arguments[1:] if options.arguments[:1] == ["--"] else options.arguments
    if not options.driver.is_file() or not options.archiver.is_file():
        parser.error("--driver and --archiver must be existing files")
    expanded = _expanded(arguments)
    output = _output(expanded)
    is_extension_link = (
        "-shared" in expanded
        and output is not None
        and output.name.endswith(".so")
    )
    if not is_extension_link:
        return subprocess.run([str(options.driver), *arguments], check=False).returncode

    _write_record(options.record_dir.resolve(), output, expanded)
    objects = [item for item in expanded if item.endswith((".o", ".obj"))]
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    subprocess.run([str(options.archiver), "rcsD", str(output), *objects], check=True)
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"archiver did not create NumPy extension archive: {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"numpy-static-compiler: {error}", file=sys.stderr)
        raise SystemExit(1)
