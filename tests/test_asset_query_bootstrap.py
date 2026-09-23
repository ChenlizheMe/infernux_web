"""Web Player asset-query lifecycle contracts."""

import ast
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_web_catalog_schema_is_rejected_before_package_extraction() -> None:
    source = (ROOT / "native/bootstrap.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {
        "_RUNTIME_ASSET_CATALOG_SCHEMA",
        "_RUNTIME_ASSET_CATALOG_FIELDS",
        "_RUNTIME_PACKAGE_FIELDS",
    }
    nodes = [
        node
        for node in tree.body
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id in names for target in node.targets)
        )
        or (isinstance(node, ast.FunctionDef) and node.name == "_validate_runtime_asset_catalog")
    ]
    namespace = {"Any": Any}
    exec(compile(ast.Module(nodes, type_ignores=[]), "bootstrap.py", "exec"), namespace)
    validate = namespace["_validate_runtime_asset_catalog"]
    package = {
        "path": "Content.inxpkg",
        "archive_bytes": 1,
        "file_count": 1,
        "raw_bytes": 1,
        "stored_bytes": 1,
        "codec": "zstd",
    }
    catalog = {
        "$schema": "infernux.runtime_asset_catalog",
        "player_host": {},
        "packages": [package],
        "artifacts": [],
    }

    assert validate(catalog) == [package]
    for mutation in (
        lambda value: value.update({"$schema": "legacy"}),
        lambda value: value.update({"legacy": True}),
        lambda value: value["packages"][0].update({"legacy": True}),
    ):
        invalid = {
            **catalog,
            "packages": [dict(package)],
        }
        mutation(invalid)
        with pytest.raises(RuntimeError, match="unsupported schema"):
            validate(invalid)


def test_web_bootstrap_binds_guid_asset_api_to_player_memfs() -> None:
    source = (ROOT / "native/bootstrap.py").read_text(encoding="utf-8")
    extraction = source[
        source.index("def _prepare_cooked_player_content()") : source.index(
            "def _install_runtime_lifecycle_bridge("
        )
    ]
    public_api = source[
        source.index("def _install_platform_runtime_api(") : source.index(
            "def _install_runtime_lifecycle_bridge("
        )
    ]
    asset_contract = source[
        source.index("def _prepare_player_asset_contract()") : source.index(
            "def _prepare_player_runtime()"
        )
    ]
    runtime = source[
        source.index("def _prepare_player_runtime()") : source.index(
            "class _WebSplashPlayer"
        )
    ]

    assert '"AssetFile": assets_module.AssetFile' in public_api
    assert '"AssetManager": assets_module.AssetManager' in public_api
    assert '"SandboxPath": sandbox_files_module.SandboxPath' in public_api
    assert 'import_module("Infernux.version")' not in public_api
    assert "package.__version__" not in public_api
    assert '"__version__"' not in public_api
    assert '_loose_root = os.path.join(_persistent_root, "loose")' in asset_contract
    assert 'os.environ["_INFERNUX_PLAYER_INSTALL_ROOT"] = _loose_root' in asset_contract
    assert 'os.environ["_INFERNUX_PLAYER_INSTALL_ROOT"] = _player_root' not in asset_contract
    assert extraction.index("_validate_runtime_asset_catalog(catalog)") < extraction.index(
        "extract_package(package, data_root)"
    )
    assert 'scene_guids = build_manifest_document.get("scene_guids")' in asset_contract
    assert 'records_document.get("$schema") != "infernux.runtime_asset_records"' in asset_contract
    assert 'set(records_document) != {"$schema", "entries"}' in asset_contract
    assert "runtime_catalog.resolve_scene(scene_guids[0])" in asset_contract
    assert "BuildSettings.json" not in asset_contract
    assert 'Application._bind_engine(session, "player")' in runtime
    assert "AssetManager.initialize(session)" in runtime
    assert runtime.index('Application._bind_engine(session, "player")') < runtime.index(
        "AssetManager.initialize(session)"
    )
    assert runtime.index("AssetManager.initialize(session)") < runtime.index(
        "session.configure_runtime_contract("
    )
    assert runtime.index("session.configure_runtime_contract(") < runtime.index(
        "PluginManager.startup("
    )
    assert "session.load_scene(scene_path)" not in runtime
    assert "session.load_scene(_player_initial_scene_path)" not in runtime
    assert runtime.index("session.configure_runtime_contract(") < runtime.index(
        "session.load_scene(scene_guid)"
    )
