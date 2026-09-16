"""Web exporter policy tests."""

from pathlib import Path

import pytest

from infernux_web.exporter import _reject_unshipped_web_dependencies


def test_web_dependency_scan_rejects_native_numerical_import(tmp_path: Path) -> None:
    assets = tmp_path / "Assets" / "Scripts"
    assets.mkdir(parents=True)
    (assets / "GPU.py").write_text("import numpy as np\n", encoding="utf-8")

    with pytest.raises(ValueError, match="native numerical dependencies.*numpy"):
        _reject_unshipped_web_dependencies(tmp_path)


def test_web_dependency_scan_allows_engine_only_script(tmp_path: Path) -> None:
    assets = tmp_path / "Assets" / "Scripts"
    assets.mkdir(parents=True)
    (assets / "Gameplay.py").write_text(
        "import infernux as inx\n\nvalue = inx.vector3(0, 1, 0)\n",
        encoding="utf-8",
    )

    _reject_unshipped_web_dependencies(tmp_path)
