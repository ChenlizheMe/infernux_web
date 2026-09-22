"""Source-only contracts for the pinned NumPy wasm static-built-in builder."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / "package/editor"
sys.path.insert(0, str(EDITOR))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PACKAGER = _load(
    "prepare_numpy_static_payload",
    ROOT / "native/python_runtime/prepare_numpy_static_payload.py",
)
COMPILER = _load(
    "numpy_static_compiler",
    ROOT / "native/python_runtime/numpy_static_compiler.py",
)


def _fake_build(tmp_path: Path):
    install = tmp_path / "install"
    site = install / "usr/local/lib/python3.13/site-packages"
    (site / "numpy").mkdir(parents=True)
    (site / "numpy/__init__.py").write_text("__version__ = '2.2.5'\n", encoding="utf-8")
    build = tmp_path / "build"
    build.mkdir()
    cpython = tmp_path / "cpython-build"
    cpython.mkdir()
    records = tmp_path / "records"
    records.mkdir()
    for index, module in enumerate(PACKAGER.EXPECTED_MODULES):
        parts = module.split(".")
        extension = site.joinpath(*parts[:-1], parts[-1] + ".cpython-313-wasm32-emscripten.so")
        extension.parent.mkdir(parents=True, exist_ok=True)
        extension.write_bytes(b"!<arch>\n" + bytes([index]))
        linked = build / f"{parts[-1]}.cpython-313-wasm32-emscripten.so"
        linked.write_bytes(extension.read_bytes())
        (records / f"{index:02}.json").write_text(json.dumps({
            "schema": "infernux.numpy_static_link.v1",
            "output": str(linked.resolve()),
            "objects": [str((build / f"{index}.o").resolve())],
            "dependency_archives": [],
            "link_arguments": ["-shared", "-o", str(linked.resolve())],
        }), encoding="utf-8")
    return install, records, build, cpython


def test_packager_requires_exact_runtime_extensions_and_is_atomic(tmp_path: Path) -> None:
    install, records, build, cpython = _fake_build(tmp_path)
    numpy = install / "usr/local/lib/python3.13/site-packages/numpy"
    (numpy / "__pycache__").mkdir()
    (numpy / "__pycache__/__init__.cpython-313.pyc").write_bytes(b"bytecode")
    (numpy / "_core/tests").mkdir(parents=True)
    (numpy / "_core/tests/test_fixture.py").write_text("raise AssertionError\n")
    (numpy / "typing_fixture.pyi").write_text("value: int\n")
    output = tmp_path / "runtime"
    PACKAGER.prepare(install, records, build, cpython, output)

    from infernux_web.native_payload import verify_python_package_payload

    runtime = json.loads((output / "runtime-manifest.json").read_text(encoding="utf-8"))
    identity = verify_python_package_payload(
        output / "payload", runtime, package_name="numpy"
    )
    assert identity["files"] >= len(PACKAGER.EXPECTED_MODULES) + 3
    assert not list((output / "payload").rglob("*.so"))
    assert not list((output / "payload").rglob("__pycache__"))
    assert not list((output / "payload").rglob("tests"))
    assert not list((output / "payload").rglob("*.pyc"))
    assert not list((output / "payload").rglob("*.pyi"))
    registry = (output / "payload/numpy_builtin_registry.c").read_text(encoding="utf-8")
    assert registry.count("PyImport_AppendInittab") == len(PACKAGER.EXPECTED_MODULES)


def test_packager_cli_does_not_require_the_engine_package(tmp_path: Path) -> None:
    staged = tmp_path / "source"
    script = staged / "native/python_runtime/prepare_numpy_static_payload.py"
    native_payload = staged / "package/editor/infernux_web/native_payload.py"
    script.parent.mkdir(parents=True)
    native_payload.parent.mkdir(parents=True)
    shutil.copyfile(
        ROOT / "native/python_runtime/prepare_numpy_static_payload.py", script
    )
    shutil.copyfile(
        ROOT / "package/editor/infernux_web/native_payload.py", native_payload
    )
    environment = os.environ.copy()
    environment.pop("PYTHONDONTWRITEBYTECODE", None)
    completed = subprocess.run(
        [sys.executable, "-I", "-S", str(script), "--help"],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Package an exact NumPy wasm static-built-in payload" in completed.stdout
    assert not list(staged.rglob("__pycache__"))
    assert not list(staged.rglob("*.pyc"))


def test_packager_rejects_extra_installed_extension_without_output(tmp_path: Path) -> None:
    install, records, build, cpython = _fake_build(tmp_path)
    extra = install / "usr/local/lib/python3.13/site-packages/numpy/_core/_test.so"
    extra.write_bytes(b"!<arch>\n")
    output = tmp_path / "runtime"
    with pytest.raises(ValueError, match="extension closure mismatch"):
        PACKAGER.prepare(install, records, build, cpython, output)
    assert not output.exists()


def test_packager_materializes_thin_dependency_archive(tmp_path: Path) -> None:
    build = tmp_path / "build"
    build.mkdir()
    member = build / "member.o"
    member.write_bytes(b"wasm object")
    source = build / "dependency.a"
    source.write_bytes(b"!<thin>\nindex")
    destination = tmp_path / "payload-dependency.a"
    archiver = tmp_path / "emar"
    archiver.write_bytes(b"archiver fixture")

    def run(arguments, **options):
        if arguments[1] == "t":
            assert options["cwd"] == source.parent
            return subprocess.CompletedProcess(arguments, 0, stdout=f"{member}\n", stderr="")
        assert arguments[1] == "rcsD"
        Path(arguments[2]).write_bytes(b"!<arch>\nmaterialized")
        return subprocess.CompletedProcess(arguments, 0)

    with patch.object(PACKAGER.subprocess, "run", side_effect=run) as invoked:
        PACKAGER._copy_dependency_archive(
            source,
            destination,
            archiver=archiver,
            numpy_build_root=build,
        )

    assert destination.read_bytes().startswith(b"!<arch>\n")
    assert invoked.call_count == 2


def test_static_compiler_record_rejects_missing_inputs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="input is missing"):
        COMPILER._write_record(
            tmp_path / "records",
            tmp_path / "module.so",
            [str(tmp_path / "missing.o"), str(tmp_path / "missing.a")],
        )


def test_builder_is_pinned_and_runs_a_real_node_numeric_probe() -> None:
    script = (ROOT / "native/python_runtime/build_numpy_static_runtime.sh").read_text(
        encoding="utf-8"
    )
    assert 'CPYTHON_VERSION="3.13.15"' in script
    assert 'NUMPY_VERSION="2.2.5"' in script
    assert 'EMSCRIPTEN_VERSION="4.0.10"' in script
    assert 'CYTHON_VERSION="3.0.12"' in script
    assert 'NINJA_VERSION="1.12.1"' in script
    assert 'NINJA_REVISION="2daa09ba270b0a43e1929d29b073348aa985dfaa"' in script
    assert "https://github.com/ninja-build/ninja.git" in script
    assert 'export MAKEFLAGS="-j2"' in script
    assert 'export PYTHONDONTWRITEBYTECODE="1"' in script
    assert 'export EM_CONFIG="$em_config"' in script
    assert 'node_path="${EMSDK_NODE:-}"' in script
    assert 'export CYTHON="$cython"' in script
    assert 'export PATH="$root:$ninja_source:$PATH"' in script
    assert "python = '$cross_python'" in script
    assert "python = ['$node_path', '$cpython_build/python.js']" not in script
    assert "unset PYTHONHOME PYTHONPATH" in script
    assert "_PYTHON_PROJECT_BASE" in script
    assert "_PYTHON_HOST_PLATFORM='emscripten-wasm32'" in script
    assert "_PYTHON_SYSCONFIGDATA_NAME" in script
    assert "_PYTHON_SYSCONFIGDATA_PATH" in script
    assert 'mesonbuild/scripts/python_info.py' in script
    assert '"link_libpython": False' in script
    assert '"SOABI": "cpython-313-wasm32-emscripten"' in script
    assert '"MULTIARCH": "wasm32-emscripten"' in script
    assert '"SIZEOF_VOID_P": 4' in script
    assert "cross-python-provenance.json" in script
    assert 'plugin_root="$(cd "$script_dir/../.." && pwd)"' in script
    assert 'native_payload="$plugin_root/package/editor/infernux_web/native_payload.py"' in script
    assert '--archiver "$emsdk/upstream/emscripten/emar"' in script
    assert "Required source-layout input is missing" in script
    assert script.index("Required source-layout input is missing") < script.index('mkdir "$root"')
    assert "command -v node" not in script
    assert "a9c0d994680cd991b1cb772e8b297340085466a6fe964bc9d4e80f5e2f43c291" in script
    assert "pyodide" not in script.lower()
    assert '(cd "$runtime_root" && "$node_path" "$(basename "$probe")")' in script
    assert '"$node_path" "$probe"' not in script
    assert "ndarray=ok ufunc=ok matmul=ok loader=builtin" in script


def test_node_probe_compiles_against_the_cpython_api_contract(tmp_path: Path) -> None:
    include = tmp_path / "include"
    include.mkdir()
    (include / "Python.h").write_text(
        """#pragma once
struct PyCompilerFlags;
struct PyObject {};
#define PyMODINIT_FUNC extern "C" PyObject *
void Py_Initialize(void);
int PyRun_SimpleStringFlags(const char *, PyCompilerFlags *);
void PyErr_Print(void);
int Py_FinalizeEx(void);
int PyImport_AppendInittab(const char *, PyObject *(*)(void));
""",
        encoding="utf-8",
    )
    (include / "cstdio").write_text(
        """#pragma once
struct InfernuxFakeFile;
extern InfernuxFakeFile *stderr;
namespace std { int fprintf(InfernuxFakeFile *, const char *, ...); }
""",
        encoding="utf-8",
    )
    source = ROOT / "native/python_runtime/NumpyStaticProbe.cpp"
    registry = tmp_path / "numpy_builtin_registry.c"
    registry.write_text(PACKAGER._registry(PACKAGER.EXPECTED_MODULES), encoding="utf-8")
    compiler = next(
        (path for name in ("c++", "clang++", "g++", "cl") if (path := shutil.which(name))),
        None,
    )
    assert compiler is not None, "a host C++ compiler is required for the probe contract"
    if Path(compiler).name.lower() in {"cl", "cl.exe"}:
        probe_object = tmp_path / "probe.obj"
        registry_object = tmp_path / "registry.obj"
        commands = [
            [
                compiler,
                "/nologo",
                "/std:c++17",
                "/TP",
                "/c",
                str(source),
                f"/I{include}",
                f"/Fo{probe_object}",
            ],
            [
                compiler,
                "/nologo",
                "/std:c++17",
                "/TP",
                "/c",
                str(registry),
                f"/I{include}",
                f"/Fo{registry_object}",
            ],
        ]
        symbol_tool = shutil.which("dumpbin")
        assert symbol_tool is not None, "dumpbin is required to inspect the registry object"
        symbol_command = [symbol_tool, "/symbols", str(registry_object)]
    else:
        probe_object = tmp_path / "probe.o"
        registry_object = tmp_path / "registry.o"
        commands = [
            [
                compiler,
                "-std=c++17",
                "-c",
                str(source),
                "-I",
                str(include),
                "-o",
                str(probe_object),
            ],
            [
                compiler,
                "-std=c++17",
                "-x",
                "c++",
                "-c",
                str(registry),
                "-I",
                str(include),
                "-o",
                str(registry_object),
            ],
        ]
        symbol_tool = shutil.which("nm")
        assert symbol_tool is not None, "nm is required to inspect the registry object"
        symbol_command = [symbol_tool, "-g", str(registry_object)]
    for command in commands:
        completed = subprocess.run(command, cwd=tmp_path, check=False, capture_output=True)
        output = (completed.stdout + completed.stderr).decode("utf-8", errors="replace")
        assert completed.returncode == 0, output
    inspected = subprocess.run(
        symbol_command, cwd=tmp_path, check=False, capture_output=True, text=True
    )
    assert inspected.returncode == 0, inspected.stdout + inspected.stderr
    symbol_lines = [
        line for line in inspected.stdout.splitlines() if "InfernuxRegisterNumPyBuiltins" in line
    ]
    assert symbol_lines, inspected.stdout
    assert any(
        line.split()[-1]
        in {"InfernuxRegisterNumPyBuiltins", "_InfernuxRegisterNumPyBuiltins"}
        for line in symbol_lines
    ), inspected.stdout
