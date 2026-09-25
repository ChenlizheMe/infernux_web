"""Web exporter policy tests."""

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from Infernux.engine.game_builder import GameBuilder
from infernux_web.exporter import (
    _reject_unshipped_web_dependencies,
    _validate_web_python_payload,
    _web_engine_python_ignore,
)


def _python_sources(root: Path) -> tuple[Path, ...]:
    return tuple(sorted((root / "Assets").rglob("*.py")))


def _player_manifest_with_numpy() -> dict[str, object]:
    return {
        "python_runtime": {
            "implementation": "cpython",
            "version": "3.13.15",
            "abi": "cp313",
            "platform": "emscripten",
            "platform_version": "4.0.10",
            "architecture": "wasm32",
            "extension_linkage": "static-built-in",
            "required_imports": ["numpy"],
            "packages": [
                {
                    "name": "numpy",
                    "version": "2.2.5",
                    "imports": ["numpy"],
                    "python_abi": "cp313",
                    "platform": "emscripten",
                    "platform_version": "4.0.10",
                    "architecture": "wasm32",
                    "linkage": "static-built-in",
                    "source_url": "https://files.pythonhosted.org/packages/source/n/numpy/numpy-2.2.5.tar.gz",
                    "source_sha256": "a9c0d994680cd991b1cb772e8b297340085466a6fe964bc9d4e80f5e2f43c291",
                    "payload_hash_algorithm": "infernux-tree-sha256-v1",
                    "payload_sha256": "1" * 64,
                    "payload_bytes": 1,
                    "payload_files": 1,
                    "license": "BSD-3-Clause",
                }
            ],
        }
    }


def test_web_engine_python_staging_excludes_non_runtime_inputs(tmp_path: Path) -> None:
    ignored = _web_engine_python_ignore(
        str(tmp_path),
        [
            "runtime.py",
            "runtime.pyi",
            "native.pyd",
            "tests",
            "infernux.mcp.inxpkg",
            "game.obj",
        ],
    )

    assert ignored == {
        "runtime.pyi",
        "native.pyd",
        "tests",
        "infernux.mcp.inxpkg",
    }


@pytest.mark.parametrize(
    "relative",
    [
        "Infernux/tests/fixture.py",
        "Infernux/resources/infernux.mcp.inxpkg",
        "Infernux/resources/model.blend",
        "Infernux/resources/model.obj",
        "packaging/native.pyd",
    ],
)
def test_web_python_payload_rejects_non_runtime_files(
    tmp_path: Path, relative: str
) -> None:
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fixture")

    with pytest.raises(RuntimeError, match="non-runtime files"):
        _validate_web_python_payload(tmp_path)


def test_web_dependency_scan_rejects_native_numerical_import(tmp_path: Path) -> None:
    assets = tmp_path / "Assets" / "Scripts"
    assets.mkdir(parents=True)
    (assets / "GPU.py").write_text("import numpy as np\n", encoding="utf-8")

    with pytest.raises(ValueError, match="native numerical dependencies.*numpy"):
        _reject_unshipped_web_dependencies(_python_sources(tmp_path))


def test_web_dependency_scan_allows_engine_only_script(tmp_path: Path) -> None:
    assets = tmp_path / "Assets" / "Scripts"
    assets.mkdir(parents=True)
    (assets / "Gameplay.py").write_text(
        "import infernux as inx\n\nvalue = inx.vector3(0, 1, 0)\n",
        encoding="utf-8",
    )

    _reject_unshipped_web_dependencies(_python_sources(tmp_path))


def test_web_dependency_scan_allows_compute_runtime_without_gpu_declaration(
    tmp_path: Path,
) -> None:
    assets = tmp_path / "Assets" / "Scripts"
    assets.mkdir(parents=True)
    (assets / "Buffers.py").write_text(
        "from Infernux import compute\n\n"
        "def upload(values):\n"
        "    return compute.buffer(values)\n",
        encoding="utf-8",
    )

    _reject_unshipped_web_dependencies(_python_sources(tmp_path))


def test_web_dependency_scan_allows_numpy_only_from_inspected_runtime(tmp_path: Path) -> None:
    assets = tmp_path / "Assets" / "Scripts"
    assets.mkdir(parents=True)
    (assets / "GPU.py").write_text("import numpy as np\n", encoding="utf-8")

    _reject_unshipped_web_dependencies(
        _python_sources(tmp_path), _player_manifest_with_numpy()
    )


def test_web_dependency_scan_still_rejects_numba_when_numpy_is_present(tmp_path: Path) -> None:
    assets = tmp_path / "Assets" / "Scripts"
    assets.mkdir(parents=True)
    (assets / "GPU.py").write_text("import numpy\nimport numba\n", encoding="utf-8")

    with pytest.raises(ValueError, match="numba.*unsupported on the Web runtime"):
        _reject_unshipped_web_dependencies(
            _python_sources(tmp_path), _player_manifest_with_numpy()
        )


@pytest.mark.parametrize(
    "source",
    [
        (
            "import infernux as inx\n"
            "@inx.jit.compile\n"
            "def update(value):\n"
            "    return value\n"
        ),
        (
            "from Infernux import jit as runtime_jit\n"
            "@runtime_jit.compile(cache=True)\n"
            "def simulate(value):\n"
            "    return value\n"
        ),
        (
            "from Infernux.jit import compile as optimize\n"
            "@optimize(parallel_policy='required')\n"
            "def helper(value):\n"
            "    return value\n"
        ),
    ],
)
def test_web_dependency_scan_keeps_cpu_jit_decorators_for_plain_runtime(
    tmp_path: Path,
    source: str,
) -> None:
    assets = tmp_path / "Assets" / "Scripts"
    assets.mkdir(parents=True)
    (assets / "Compute.py").write_text(source, encoding="utf-8")

    _reject_unshipped_web_dependencies(
        _python_sources(tmp_path), _player_manifest_with_numpy()
    )


def test_web_cook_executes_public_cpu_jit_source_without_a_jit_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = (
        "import infernux as inx\n"
        "@inx.jit.compile(parallel_policy='required')\n"
        "def advance(value):\n"
        "    return value + 3\n\n"
        "def run():\n"
        "    inx.jit.warmup(advance, 4)\n"
        "    return advance(4)\n"
    )
    cooked = GameBuilder._cook_compute_source(
        SimpleNamespace(include_jit_runtime=False), source
    )
    script = tmp_path / "Assets" / "Scripts" / "Compute.py"
    script.parent.mkdir(parents=True)
    script.write_text(cooked, encoding="utf-8")
    _reject_unshipped_web_dependencies((script,))

    # An uncooked decorator or warmup call would fail in this no-JIT namespace.
    no_jit = ModuleType("infernux")
    no_jit.jit = SimpleNamespace(compile=None, warmup=None)
    monkeypatch.setitem(sys.modules, "infernux", no_jit)
    namespace: dict[str, object] = {}
    exec(compile(cooked, str(script), "exec"), namespace)
    assert namespace["run"]() == 7
    assert "@inx.jit.compile" not in cooked
    assert "inx.jit.warmup(" not in cooked


@pytest.mark.parametrize(
    ("source", "name"),
    [
        (
            "import infernux as inx\n"
            "@inx.compute.kernel\n"
            "def update(domain):\n"
            "    pass\n",
            "update",
        ),
        (
            "from Infernux.compute import function as gpu_function\n"
            "@gpu_function\n"
            "def helper(value):\n"
            "    return value\n",
            "helper",
        ),
        (
            "from Infernux import compute as gpu\n"
            "@gpu.kernel\n"
            "def integrate(domain):\n"
            "    pass\n",
            "integrate",
        ),
        (
            "import infernux as inx\n"
            "gpu = inx.compute\n"
            "dispatch = gpu.kernel\n"
            "@dispatch\n"
            "def assigned_alias(domain):\n"
            "    pass\n",
            "assigned_alias",
        ),
        (
            "from Infernux import compute\n"
            "api = compute\n"
            "helper_decorator: object = api.function\n"
            "@helper_decorator()\n"
            "def assigned_helper(value):\n"
            "    return value\n",
            "assigned_helper",
        ),
        (
            "import Infernux.compute as gpu\n"
            "kernel_alias = gpu.kernel\n"
            "class Kernels:\n"
            "    @kernel_alias\n"
            "    def nested(domain):\n"
            "        pass\n",
            "nested",
        ),
        (
            "from Infernux.compute import *\n"
            "@kernel\n"
            "def star_imported(domain):\n"
            "    pass\n",
            "star_imported",
        ),
        (
            "import infernux as inx\n"
            "decorator = ordinary\n"
            "if enabled:\n"
            "    decorator = inx.compute.kernel\n"
            "else:\n"
            "    marker = 1\n"
            "@decorator\n"
            "def conditional(domain):\n"
            "    pass\n",
            "conditional",
        ),
        (
            "import infernux as inx\n"
            "decorator = ordinary\n"
            "try:\n"
            "    marker = operation()\n"
            "except RuntimeError:\n"
            "    decorator = inx.compute.function\n"
            "@decorator\n"
            "def recovered(value):\n"
            "    return value\n",
            "recovered",
        ),
        (
            "import infernux as inx\n"
            "decorator = ordinary\n"
            "with acquire():\n"
            "    decorator = inx.compute.kernel\n"
            "@decorator\n"
            "def after_with(domain):\n"
            "    pass\n",
            "after_with",
        ),
        (
            "import infernux as inx\n"
            "decorator = ordinary\n"
            "for item in values:\n"
            "    decorator = inx.compute.kernel\n"
            "@decorator\n"
            "def after_loop(domain):\n"
            "    pass\n",
            "after_loop",
        ),
        (
            "import infernux as inx\n"
            "decorator = ordinary\n"
            "match mode:\n"
            "    case 'gpu':\n"
            "        decorator = inx.compute.function\n"
            "    case _:\n"
            "        marker = 1\n"
            "@decorator\n"
            "def matched(value):\n"
            "    return value\n",
            "matched",
        ),
    ],
)
def test_web_dependency_scan_rejects_gpu_declarations_without_kernel_compiler(
    tmp_path: Path,
    source: str,
    name: str,
) -> None:
    assets = tmp_path / "Assets" / "Scripts"
    assets.mkdir(parents=True)
    (assets / "Compute.py").write_text(source, encoding="utf-8")

    with pytest.raises(ValueError, match=rf"GPU compute declarations: {name}"):
        _reject_unshipped_web_dependencies(
            _python_sources(tmp_path), _player_manifest_with_numpy()
        )


def test_web_gpu_diagnostic_preserves_class_identity_location_and_rewrite(tmp_path: Path) -> None:
    assets = tmp_path / "Assets" / "Scripts"
    assets.mkdir(parents=True)
    source = assets / "Jelly.py"
    source.write_text(
        "import Infernux as inx\n"
        "class Jelly:\n"
        "    @staticmethod\n"
        "    @inx.compute.kernel\n"
        "    def step(domain):\n"
        "        pass\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as error:
        _reject_unshipped_web_dependencies(
            _python_sources(tmp_path), _player_manifest_with_numpy()
        )
    message = str(error.value)
    assert "Jelly.step" in message
    assert f"{source}:5:5" in message
    assert "Rewrite: remove @inx.compute.kernel/@inx.compute.function" in message
    assert "no Python-to-WebGPU kernel compiler" in message


def test_web_dependency_scan_uses_only_frozen_player_sources(tmp_path: Path) -> None:
    runtime = tmp_path / "Assets" / "Scripts" / "Gameplay.py"
    runtime.parent.mkdir(parents=True)
    runtime.write_text("import infernux\n", encoding="utf-8")
    editor = tmp_path / "Assets" / "Editor" / "Bake.py"
    editor.parent.mkdir(parents=True)
    editor.write_text(
        "import numba\n"
        "from Infernux.compute import kernel\n"
        "@kernel\n"
        "def bake(domain):\n"
        "    pass\n",
        encoding="utf-8",
    )

    _reject_unshipped_web_dependencies((runtime,), _player_manifest_with_numpy())


def test_web_dependency_scan_honors_definite_alias_replacement(tmp_path: Path) -> None:
    runtime = tmp_path / "Assets" / "Scripts" / "Ordinary.py"
    runtime.parent.mkdir(parents=True)
    runtime.write_text(
        "import infernux as inx\n"
        "decorator = inx.compute.kernel\n"
        "decorator = ordinary\n"
        "for item in values:\n"
        "    marker = item\n"
        "@decorator\n"
        "def ordinary_function(value):\n"
        "    return value\n",
        encoding="utf-8",
    )

    _reject_unshipped_web_dependencies((runtime,), _player_manifest_with_numpy())
