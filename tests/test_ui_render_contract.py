"""The Web UI backend must consume, not merely accept, runtime UI packets."""

import ast
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def test_python_bridge_submits_guid_generation_and_world_transform(monkeypatch):
    source = (ROOT / "native/bootstrap.py").read_text(encoding="utf-8")
    cls = next(
        node for node in ast.parse(source).body
        if isinstance(node, ast.ClassDef) and node.name == "_WebScreenUIRenderer"
    )
    calls = []
    host = ModuleType("_InfernuxWebHost")
    host.screen_ui_set_material_binding = lambda *args: calls.append(("material", args))
    host.screen_ui_begin_world_element = lambda *args: calls.append(("world", args))
    host.screen_ui_end_world_element = lambda: calls.append(("end", ()))
    monkeypatch.setitem(__import__("sys").modules, "_InfernuxWebHost", host)
    namespace = {"Any": Any}
    exec(compile(ast.Module([cls], type_ignores=[]), "bootstrap.py", "exec"), namespace)
    renderer = namespace["_WebScreenUIRenderer"]()
    transform = SimpleNamespace(local_to_world_matrix=lambda: range(16))
    obj = SimpleNamespace(transform=transform, layer=6)
    renderer.set_material_binding(2, "a" * 32, 11, "ui|shader=fixture", (0.2, 0.4, 0.6, 0.8), True, 0.35)
    renderer.begin_world_object(obj, 50.0, 25.0, True, False, True, 9)
    renderer.end_world_element()

    assert calls[0] == ("material", (2, "a" * 32, 11, "ui|shader=fixture",
                                      (0.2, 0.4, 0.6, 0.8), True, 0.35))
    assert calls[1] == ("world", (tuple(range(16)), 50.0, 25.0, 6, True, False, True, 9))
    assert calls[2] == ("end", ())


def test_native_world_draw_is_depth_aware_and_material_shader_is_consumed():
    renderer = (ROOT / "native/WebScreenUIRenderer.cpp").read_text(encoding="utf-8")
    frame = (ROOT / "native/main.cpp").read_text(encoding="utf-8")

    assert "m_worldDepthPipeline" in renderer
    assert "m_worldTopPipeline" in renderer
    assert "cullingMask & (1u << span.layer)" in renderer
    assert "std::stable_sort(draws.begin(), draws.end()" in renderer
    assert "ResolveMaterialPipeline(draw.binding, true, draw.top)" in renderer
    assert "ResolveMaterialPipeline(binding, false, false)" in renderer
    assert 'InfernuxWebFindShaderSource(vertex.shaderId, "vertex"' in renderer
    assert 'InfernuxWebFindShaderSource(fragment.shaderId, "fragment"' in renderer
    assert "g_screenUIRenderer.RenderWorld(pass" in frame
    assert frame.index("g_screenUIRenderer.RenderWorld(pass") < frame.index("pass.End();", frame.index("g_screenUIRenderer.RenderWorld(pass"))


def test_browser_ui_input_uses_shared_world_projection():
    bootstrap = (ROOT / "native/bootstrap.py").read_text(encoding="utf-8")
    event_section = bootstrap.split("def _process_screen_ui_events", 1)[1].split(
        "def infernux_web_tick", 1
    )[0]
    assert "collect_runtime_ui_input_surfaces(scene, persistent_scene)" in event_section
    assert "map_runtime_ui_pointer(" in event_section
    assert "scene.effective_game_camera" in event_section
    assert "_screen_ui_event_processor.process_pointers(" in event_section
