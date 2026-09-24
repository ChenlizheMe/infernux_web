"""UI shader cook resolves project assets by GUID and keeps stage domains."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from infernux_web.exporter import _stage_web_ui_shader_sources


def _shader(assets: Path, name: str, guid: str, domain: str) -> None:
    path = assets / name
    path.write_text(f"ShaderInfo {{ Name \"{path.stem}\" }}\n", encoding="utf-8")
    path.with_suffix(path.suffix + ".meta").write_text(
        json.dumps({"metadata": {
            "guid": {"value": guid},
            "file_path": {"value": "C:/obsolete/project/shader"},
            "shader_id": {"value": path.stem},
            "shader_capabilities": {"value": json.dumps([domain])},
            "properties": {"value": "[]"},
        }}), encoding="utf-8"
    )


def test_ui_shader_cook_uses_companion_source_and_guid(tmp_path):
    assets = tmp_path / "Assets"
    assets.mkdir()
    _shader(assets, "Screen.vert", "a" * 32, "ScreenUI")
    _shader(assets, "Screen.frag", "b" * 32, "ScreenUI")
    (assets / "Screen.mat").write_text(json.dumps({"shaders": {
        "vertex": {"guid": "a" * 32, "shader_id": "Screen"},
        "fragment": {"guid": "b" * 32, "shader_id": "Screen"},
    }}), encoding="utf-8")
    cook = tmp_path / "cook"
    cook.mkdir()
    entries = []
    prepared = []
    native = SimpleNamespace(_prepare_authored_shader_glsl=lambda source, path:
                             prepared.append(path) or source)

    _stage_web_ui_shader_sources(SimpleNamespace(project_root=tmp_path), cook, entries, native)

    assert {(entry["name"], entry["stage"]) for entry in entries} == {
        ("Screen", "vertex"), ("Screen", "fragment")
    }
    assert all(Path(path).parent == assets for path in prepared)
    assert (cook / ("ui-" + "a" * 32 + ".vert")).is_file()


def test_ui_shader_cook_rejects_cross_domain_material(tmp_path):
    assets = tmp_path / "Assets"
    assets.mkdir()
    _shader(assets, "Screen.vert", "a" * 32, "ScreenUI")
    _shader(assets, "World.frag", "b" * 32, "WorldUI")
    (assets / "Broken.mat").write_text(json.dumps({"shaders": {
        "vertex": {"guid": "a" * 32, "shader_id": "Screen"},
        "fragment": {"guid": "b" * 32, "shader_id": "World"},
    }}), encoding="utf-8")
    cook = tmp_path / "cook"
    cook.mkdir()

    with pytest.raises(ValueError, match="domains disagree"):
        _stage_web_ui_shader_sources(
            SimpleNamespace(project_root=tmp_path), cook, [],
            SimpleNamespace(_prepare_authored_shader_glsl=lambda source, path: source),
        )


def test_ui_shader_cook_rejects_unimplemented_descriptor_properties(tmp_path):
    assets = tmp_path / "Assets"
    assets.mkdir()
    _shader(assets, "Screen.vert", "a" * 32, "ScreenUI")
    _shader(assets, "Screen.frag", "b" * 32, "ScreenUI")
    fragment_meta = assets / "Screen.frag.meta"
    document = json.loads(fragment_meta.read_text(encoding="utf-8"))
    document["metadata"]["properties"]["value"] = json.dumps([
        {"name": "extraColor", "type": "Color"}
    ])
    fragment_meta.write_text(json.dumps(document), encoding="utf-8")
    (assets / "Custom.mat").write_text(json.dumps({"shaders": {
        "vertex": {"guid": "a" * 32, "shader_id": "Screen"},
        "fragment": {"guid": "b" * 32, "shader_id": "Screen"},
    }}), encoding="utf-8")
    cook = tmp_path / "cook"
    cook.mkdir()

    with pytest.raises(ValueError, match="material descriptor ABI"):
        _stage_web_ui_shader_sources(
            SimpleNamespace(project_root=tmp_path), cook, [],
            SimpleNamespace(_prepare_authored_shader_glsl=lambda source, path: source),
        )
