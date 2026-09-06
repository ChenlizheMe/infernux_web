"""Web target and its staged exporter implementation."""

from __future__ import annotations

import compileall
import hashlib
import importlib.util
import json
import os
import py_compile
import re
import shutil
import sys
import time
from pathlib import Path

from Infernux.engine.build import (
    BuildArtifact,
    BuildDiagnostic,
    BuildPlan,
    BuildRequest,
    BuildResult,
    BuildStep,
    BuildTarget,
    CapabilityReport,
    DiagnosticSeverity,
    PlatformCapabilities,
    PlatformExporter,
)

from .doctor import inspect_web_toolchain
from .capabilities import (
    WEBGPU_CAPABILITY_FILENAME,
    validate_webgpu_capability_inventory,
    webgpu_capability_inventory,
)


_WEB_CAPABILITIES = PlatformCapabilities(
    graphics_api="webgpu",
    threads=False,
    dynamic_loading=False,
    filesystem=True,
    network=False,
    audio=True,
    pointer_input=True,
    text_input=True,
    gamepad_input=True,
    python_native_modules=False,
    numba=False,
    persistent_storage=False,
    features=frozenset(
        {
            "browser-lifecycle",
            "css-pixel-viewport",
            "dom-text-input",
            "gesture-gated-webaudio",
            "multi-pointer",
            "safe-area",
            "webgpu-capability-inventory",
        }
    ),
)

_PROJECT_WEB_TEMPLATE = Path("ProjectSettings") / "WebTemplate"
_WEB_SHELL_REQUIRED_MARKERS = (
    "{{{ SCRIPT }}}",
    "@INFERNUX_WEB_ASSET_REVISION@",
    "@INFERNUX_WEB_DISPLAY_MODE@",
    "@INFERNUX_WEB_CANVAS_WIDTH@",
    "@INFERNUX_WEB_CANVAS_HEIGHT@",
)


class WebPlatformExporter(PlatformExporter):
    @property
    def exporter_id(self) -> str:
        return "infernux/platform-web"

    def targets(self):
        return (
            BuildTarget(
                "web-wasm32",
                "Web WebAssembly",
                "web",
                "wasm32",
                _WEB_CAPABILITIES,
            ),
        )

    def doctor(self, request: BuildRequest) -> CapabilityReport:
        return inspect_web_toolchain(request.target)

    def create_plan(self, request: BuildRequest) -> BuildPlan:
        return BuildPlan(
            request.target,
            (
                BuildStep("cook", "Cook project content", "cook"),
                BuildStep(
                    "shaders",
                    "Translate portable GLSL shaders to validated WGSL",
                    "compile",
                ),
                BuildStep("imports", "Analyze browser Python imports", "analyze"),
                BuildStep("runtime", "Stage precompiled WebGPU and CPython runtime", "package"),
                BuildStep(
                    "package",
                    "Publish HTML, JavaScript, WebAssembly, and content",
                    "package",
                ),
                BuildStep("audit", "Audit browser package and server contract", "audit"),
            ),
            {
                "architecture": "wasm32",
                "graphics_api": "webgpu",
                "python": "3.13",
            },
        )

    def execute(self, request: BuildRequest, plan: BuildPlan) -> BuildResult:
        started = time.perf_counter()
        capability_inventory: dict[str, object] = {}
        report = self.doctor(request)
        if not report.available:
            return BuildResult(
                request.target,
                False,
                diagnostics=report.diagnostics,
                manifest={"toolchain": dict(report.details)},
                elapsed_seconds=time.perf_counter() - started,
            )
        details = dict(report.details)
        import Infernux

        source_package = Path(Infernux.__file__).resolve().parent
        staging = _web_staging_directory(request)
        logs: tuple[str, ...] = ()
        try:
            from Infernux.engine.platform_content_cook import (
                build_settings_for_request,
            )

            build_settings = build_settings_for_request(request)
            presentation = {
                "display_mode": str(build_settings["display_mode"]),
                "window_width": int(build_settings["window_width"]),
                "window_height": int(build_settings["window_height"]),
            }
            default_shell = (
                Path(__file__).resolve().parent / "templates" / "host" / "shell.html"
            )
            web_shell, project_web_template = _resolve_web_template(
                request,
                default_shell,
            )
            request.report("prepare", 0, 1, "Preparing Web Player staging")
            _prepare_web_staging(staging)
            game_name, player_assets = _cook_web_player_assets(request, staging)
            _stage_web_branding(player_assets, source_package, game_name)
            _stage_engine_python_package(request, player_assets, source_package)
            _stage_web_shader_sources(request, staging, player_assets, source_package)
            capability_inventory = _stage_webgpu_capability_inventory(player_assets)
            logs = _assemble_web_host(
                request,
                staging,
                player_assets,
                details,
                source_package,
                presentation,
                web_shell,
                project_web_template,
            )
            request.report("prepare", 1, 1, "Cooked Web Player host ready")
        except (OSError, RuntimeError, ValueError) as error:
            return BuildResult(
                request.target,
                False,
                diagnostics=(
                    BuildDiagnostic(
                        DiagnosticSeverity.ERROR,
                        "web.player.stage-failed",
                        str(error),
                        source=self.exporter_id,
                    ),
                ),
                manifest={
                    "exporter": self.exporter_id,
                    "abi": "wasm32",
                    "graphics_api": "webgpu",
                    "python": "3.13",
                    "scope": "staging-failed",
                    "staging": str(staging),
                },
                logs=logs,
                elapsed_seconds=time.perf_counter() - started,
            )

        try:
            artifacts, asset_revision = _publish_web_player(
                request,
                staging / "host-build",
                project_web_template,
            )
        except (OSError, RuntimeError, ValueError) as error:
            return BuildResult(
                request.target,
                False,
                diagnostics=(
                    BuildDiagnostic(
                        DiagnosticSeverity.ERROR,
                        "web.player.publish-failed",
                        str(error),
                        source=self.exporter_id,
                    ),
                ),
                manifest={
                    "exporter": self.exporter_id,
                    "abi": "wasm32",
                    "graphics_api": "webgpu",
                    "python": "3.13",
                    "scope": "publish-failed",
                    "game": game_name,
                    "staging": str(staging),
                },
                logs=logs,
                elapsed_seconds=time.perf_counter() - started,
            )

        return BuildResult(
            request.target,
            True,
            artifacts=artifacts,
            manifest={
                "exporter": self.exporter_id,
                "abi": "wasm32",
                "graphics_api": "webgpu",
                "python": "3.13",
                "scope": "cooked-player",
                "game": game_name,
                "asset_revision": asset_revision,
                "entry_point": "infernux-player.html",
                "presentation": presentation,
                "web_template": (
                    "project" if project_web_template is not None else "default"
                ),
                "webgpu_capabilities": {
                    "path": WEBGPU_CAPABILITY_FILENAME,
                    "schema": capability_inventory["$schema"],
                    "open_parity_gates": sorted(
                        str(feature["id"])
                        for feature in capability_inventory["features"]
                        if feature["parity_gate"] == "open"
                    ),
                },
            },
            logs=logs,
            elapsed_seconds=time.perf_counter() - started,
        )


def _publish_web_player(
    request: BuildRequest,
    host_build: Path,
    project_web_template: Path | None,
) -> tuple[tuple[BuildArtifact, ...], str]:
    entry_point = host_build / "infernux-player.html"
    if not entry_point.is_file():
        raise RuntimeError("Web host build has no infernux-player.html entry point")
    html = entry_point.read_text(encoding="utf-8")
    match = re.search(r"assetRevision\s*=\s*['\"]([0-9a-f]{24})['\"]", html)
    if match is None:
        raise RuntimeError("Web host entry point has no valid asset revision")
    revision = match.group(1)
    names = (
        "infernux-player.html",
        f"infernux-player.{revision}.js",
        f"infernux-player.{revision}.wasm",
        f"infernux-player.{revision}.data",
        f"infernux-player.{revision}.inxpkg",
        "infernux-logo.png",
        "infernux-favicon.png",
        "infernux-icon-192.png",
        "infernux-icon-512.png",
        "infernux.webmanifest",
        "infernux-branding.js",
        WEBGPU_CAPABILITY_FILENAME,
    )
    missing = [name for name in names if not (host_build / name).is_file()]
    if missing:
        raise RuntimeError(
            "Web host publication is incomplete: " + ", ".join(missing)
        )
    capability_path = host_build / WEBGPU_CAPABILITY_FILENAME
    try:
        capability_document = json.loads(capability_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"WebGPU capability inventory is unreadable: {error}"
        ) from error
    if not isinstance(capability_document, dict):
        raise RuntimeError("WebGPU capability inventory must be a JSON object")
    try:
        validate_webgpu_capability_inventory(capability_document)
    except ValueError as error:
        raise RuntimeError(str(error)) from error
    if names[1] not in html:
        raise RuntimeError(f"Web host entry point does not reference {names[1]}")
    for suffix in ("wasm", "data"):
        logical_name = f"infernux-runtime.{suffix}"
        versioned_expression = f"infernux-player.${{assetRevision}}.{suffix}"
        if logical_name not in html or versioned_expression not in html:
            raise RuntimeError(
                f"Web host entry point does not version-map {logical_name}"
            )

    output_root = Path(request.output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    for stale in output_root.glob("infernux-player.*"):
        if stale.is_file() and stale.name not in names:
            stale.unlink()

    artifacts = []
    for name in names:
        source = host_build / name
        destination = output_root / name
        temporary = output_root / f".{name}.tmp"
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
        artifacts.append(
            BuildArtifact(
                str(destination),
                destination.suffix.lstrip("."),
                size=destination.stat().st_size,
            )
        )
    template_output = output_root / "web-template"
    template_temporary = output_root / ".web-template.tmp"
    if template_temporary.exists():
        shutil.rmtree(template_temporary)
    if project_web_template is not None:
        template_temporary.mkdir(parents=True)
        for source in sorted(project_web_template.rglob("*")):
            if source.is_symlink():
                raise RuntimeError(
                    f"Project Web template cannot contain symbolic links: {source}"
                )
            if not source.is_file():
                continue
            relative = source.relative_to(project_web_template)
            if relative == Path("shell.html"):
                continue
            destination = template_temporary / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        if template_output.exists():
            shutil.rmtree(template_output)
        os.replace(template_temporary, template_output)
        for destination in sorted(template_output.rglob("*")):
            if not destination.is_file():
                continue
            artifacts.append(
                BuildArtifact(
                    str(destination),
                    destination.suffix.lstrip(".") or "file",
                    size=destination.stat().st_size,
                )
            )
    elif template_output.exists():
        shutil.rmtree(template_output)
    request.report("package", 1, 1, "Web Player package published")
    request.report("audit", 1, 1, "Web Player browser contract verified")
    return tuple(artifacts), revision


def _resolve_web_template(
    request: BuildRequest,
    default_shell: Path,
) -> tuple[Path, Path | None]:
    template_root = Path(request.project_root).resolve() / _PROJECT_WEB_TEMPLATE
    if not template_root.exists():
        return default_shell.resolve(), None
    if not template_root.is_dir():
        raise ValueError(
            f"Project Web template must be a directory: {template_root}"
        )
    shell = template_root / "shell.html"
    if not shell.is_file():
        raise ValueError(
            f"Project Web template is missing shell.html: {template_root}"
        )
    if shell.is_symlink():
        raise ValueError("Project Web template shell.html cannot be a symbolic link")
    document = shell.read_text(encoding="utf-8")
    missing = [
        marker for marker in _WEB_SHELL_REQUIRED_MARKERS if marker not in document
    ]
    if not re.search(r"\bid\s*=\s*(['\"])canvas\1", document):
        missing.append('id="canvas"')
    if missing:
        raise ValueError(
            "Project Web template shell.html is missing required markers: "
            + ", ".join(missing)
        )
    return shell.resolve(), template_root.resolve()


def _stage_webgpu_capability_inventory(
    player_assets: Path,
) -> dict[str, object]:
    document = webgpu_capability_inventory()
    validate_webgpu_capability_inventory(document)
    destination = player_assets / WEBGPU_CAPABILITY_FILENAME
    destination.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return document


def _prepare_web_staging(staging: Path) -> None:
    """Refresh generated project content and assembly output."""

    staging.mkdir(parents=True, exist_ok=True)
    for name in (".infernux-player-cook", "player-assets", "shader-cook", "host-build"):
        shutil.rmtree(staging / name, ignore_errors=True)


def _web_build_cache_root(request: BuildRequest) -> Path:
    configured = str(
        request.profile.options.get("build_cache_root", "") or ""
    ).strip()
    if not configured:
        configured = os.environ.get("INFERNUX_BUILD_CACHE_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(request.project_root).resolve() / "Cache" / "Build"


def _web_staging_directory(request: BuildRequest) -> Path:
    return _web_build_cache_root(request) / "WebHost" / str(request.target)


def _cook_web_player_assets(
    request: BuildRequest,
    staging: Path,
) -> tuple[str, Path]:
    from Infernux.engine.platform_content_cook import cook_platform_content

    cook_root = staging / ".infernux-player-cook"
    cook_root.mkdir(parents=True)
    cooked = cook_platform_content(
        request,
        cook_root,
        platform_host={
            "identity": "webgpu-cpython-wasm-player-host",
            "entry_point": "infernux-player.html",
            "platform": "web",
            "architecture": "wasm32",
        },
    )
    player_assets = staging / "player-assets"
    player_assets.mkdir(parents=True)
    shutil.copytree(
        cooked.data_directory,
        player_assets / cooked.data_directory.name,
    )
    return cooked.game_name, player_assets


def _stage_web_branding(
    player_assets: Path,
    source_package: Path,
    game_name: str,
) -> Path:
    """Create browser metadata from the shared cooked Player branding."""

    from Infernux.engine.platform_content_cook import read_cooked_player_icon

    data_roots = sorted(path for path in player_assets.glob("*_Data") if path.is_dir())
    if len(data_roots) != 1:
        raise ValueError("Web Player branding requires exactly one cooked *_Data directory")
    source_icon = read_cooked_player_icon(
        data_roots[0],
        default_icon=(
            source_package
            / "resources"
            / "icons"
            / "icon.png"
        ),
    )
    try:
        from PIL import Image, ImageOps
    except ImportError as error:
        raise ValueError("Pillow is required to generate Web application icons") from error
    try:
        from io import BytesIO

        with Image.open(BytesIO(source_icon)) as opened:
            source = opened.convert("RGBA")
    except (OSError, ValueError) as error:
        raise ValueError("Cooked Web application icon is unreadable") from error

    branding = player_assets / "web-branding"
    shutil.rmtree(branding, ignore_errors=True)
    branding.mkdir(parents=True)
    for name, size in (
        ("infernux-favicon.png", 32),
        ("infernux-icon-192.png", 192),
        ("infernux-icon-512.png", 512),
    ):
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        contained = ImageOps.contain(
            source,
            (size, size),
            method=Image.Resampling.LANCZOS,
        )
        canvas.alpha_composite(
            contained,
            ((size - contained.width) // 2, (size - contained.height) // 2),
        )
        canvas.save(branding / name, format="PNG", optimize=True)

    manifest = {
        "name": game_name,
        "short_name": game_name,
        "display": "fullscreen",
        "background_color": "#111214",
        "theme_color": "#111214",
        "icons": [
            {
                "src": "infernux-icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
            },
            {
                "src": "infernux-icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
            },
        ],
    }
    (branding / "infernux.webmanifest").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    branding_document = json.dumps(
        {"game_name": game_name},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    (branding / "infernux-branding.js").write_text(
        "globalThis.InfernuxBranding = Object.freeze("
        + branding_document
        + ");\n"
        "document.title = globalThis.InfernuxBranding.game_name;\n",
        encoding="utf-8",
        newline="\n",
    )
    return branding


def _stage_engine_python_package(
    request: BuildRequest,
    player_assets: Path,
    source_package: Path,
) -> None:
    if not (source_package / "engine" / "platform_player_bootstrap.py").is_file():
        raise ValueError(f"Infernux Player Python sources are incomplete: {source_package}")
    site_packages = player_assets / "python" / "site-packages"
    destination = site_packages / "Infernux"
    request.report("analyze", 0, 2, "Staging Infernux Web Player modules")
    shutil.copytree(
        source_package,
        destination,
        ignore=shutil.ignore_patterns(
            "__pycache__",
            "*.pyc",
            "*.pyi",
            "*.pyd",
            "*.dll",
            "*.dylib",
            "*.so",
            "*.lib",
            "*.exp",
            "*.obj",
            "_runtime_modules",
            "_runtime_packs",
            "official_packages",
            "player_runtime",
            "project_templates",
            "test",
        ),
    )
    public_api = source_package.parent / "infernux.py"
    if not public_api.is_file():
        raise ValueError(f"Infernux public Python API is missing: {public_api}")
    shutil.copy2(public_api, site_packages / public_api.name)
    packaging_spec = importlib.util.find_spec("packaging")
    packaging_source = (
        Path(str(packaging_spec.origin)).resolve().parent
        if packaging_spec is not None and packaging_spec.origin
        else None
    )
    if packaging_source is None or not (packaging_source / "__init__.py").is_file():
        raise ValueError("The Web Player staging environment has no packaging module")
    shutil.copytree(
        packaging_source,
        site_packages / "packaging",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyi"),
    )
    if sys.version_info[:2] != (3, 13):
        raise RuntimeError(
            "Web Player Python staging requires the engine's Python 3.13 runtime"
        )
    if not compileall.compile_dir(
        site_packages,
        quiet=1,
        optimize=0,
        invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
    ):
        raise RuntimeError("Web Player engine Python bytecode compilation failed")
    request.report("analyze", 2, 2, "Web Player Python modules staged")


def _stage_web_shader_sources(
    request: BuildRequest,
    staging: Path,
    player_assets: Path,
    source_package: Path,
) -> None:
    """Generate the shared renderer's GLSL inputs before WGSL translation."""

    from Infernux.lib import _Infernux as native

    vertex_path = (
        source_package
        / "resources"
        / "shaders"
        / "fullscreen_triangle.vert"
    )
    if not vertex_path.is_file():
        raise ValueError(f"Infernux fullscreen shader is missing: {vertex_path}")
    request.report("shaders", 0, 2, "Preparing shared fullscreen shader")
    generated_vertex = native._prepare_authored_shader_glsl(
        vertex_path.read_text(encoding="utf-8"),
        str(vertex_path),
    )
    generated_fragment = """#version 450
layout(location = 0) in vec2 inUV;
layout(location = 0) out vec4 outColor;
void main() {
    outColor = vec4(inUV.x, inUV.y, 0.20 + 0.12 * inUV.x, 1.0);
}
"""
    shader_root = staging / "shader-cook"
    shader_root.mkdir(parents=True, exist_ok=True)
    (shader_root / "fullscreen_triangle.vert").write_text(
        generated_vertex,
        encoding="utf-8",
        newline="\n",
    )
    (shader_root / "web_host.frag").write_text(
        generated_fragment,
        encoding="utf-8",
        newline="\n",
    )
    shader_entries = [
        {
            "name": "Fullscreen Triangle",
            "stage": "vertex",
            "source": "fullscreen_triangle.vert",
        },
        {
            "name": "Web Host",
            "stage": "fragment",
            "source": "web_host.frag",
        },
    ]
    particle_kernels: dict[str, dict[str, object]] = {}
    data_roots = sorted(player_assets.glob("*_Data"))
    if len(data_roots) != 1:
        raise ValueError(
            "Web Player shader cook requires exactly one staged *_Data directory"
        )
    # Particle AOT artifacts are build inputs, not loose Player files. The
    # generic cooker seals runtime content into Content.inxpkg before Web
    # shader translation runs, so consume the project's current artifact
    # registry and stage only validated WGSL plus its compact catalog.
    particle_root = (
        Path(request.project_root).resolve()
        / "Library"
        / "Artifacts"
        / "Particle"
    )
    if particle_root.is_dir():
        for artifact_path in sorted(particle_root.glob("*.inxparticle")):
            try:
                artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise ValueError(
                    f"Web Particle artifact is unreadable: {artifact_path.name}: {error}"
                ) from error
            emitters = artifact.get("gpu_glsl", {}).get("emitters")
            if not isinstance(emitters, list):
                raise ValueError(
                    f"Web Particle artifact has no GLSL emitters: {artifact_path.name}"
                )
            for emitter in emitters:
                if not isinstance(emitter, dict):
                    raise ValueError("Web Particle emitter metadata must be an object")
                kernel_hash = str(emitter.get("kernel_hash", ""))
                stable_id = str(emitter.get("stable_id", ""))
                stages = emitter.get("stages")
                data_layout = emitter.get("data_interface_layout")
                if (
                    not re.fullmatch(r"[0-9a-f]{64}", kernel_hash)
                    or not stable_id
                    or not isinstance(stages, dict)
                ):
                    raise ValueError("Web Particle emitter identity is invalid")
                if emitter.get("collision_enabled") or emitter.get("continuation") is not None:
                    raise ValueError(
                        f"WebGPU Particle emitter {stable_id} uses collision or continuation, "
                        "which is not portable yet"
                    )
                if not isinstance(data_layout, dict) or any(
                    data_layout.get(name)
                    for name in (
                        "mesh_interfaces",
                        "texture2d_parameters",
                        "volume_interfaces",
                    )
                ):
                    raise ValueError(
                        f"WebGPU Particle emitter {stable_id} uses a data interface "
                        "which is not portable yet"
                    )
                expected_stages = {
                    "bootstrap",
                    "init",
                    "update",
                    "update_rendering_fused",
                    "contact_prepare",
                    "contact_solve",
                    "contact_dispatch",
                    "render_reset",
                    "rendering",
                }
                if set(stages) != expected_stages or any(
                    not isinstance(stages[name], str) or not stages[name]
                    for name in expected_stages
                ):
                    raise ValueError(
                        f"WebGPU Particle emitter {stable_id} has incomplete compute stages"
                    )
                existing = particle_kernels.get(kernel_hash)
                kernel_record = {
                    "kernel_hash": kernel_hash,
                    "stable_ids": [stable_id],
                    "state_stride": int(emitter.get("state_stride", 0)),
                    "event_type_count": int(emitter.get("event_type_count", 0)),
                    "update_render_fusion": emitter.get("update_render_fusion"),
                    "stages": {},
                }
                if existing is not None:
                    comparable = {
                        key: value
                        for key, value in existing.items()
                        if key not in {"stable_ids", "stages"}
                    }
                    expected = {
                        key: value
                        for key, value in kernel_record.items()
                        if key not in {"stable_ids", "stages"}
                    }
                    if comparable != expected:
                        raise ValueError(
                            f"Conflicting Web Particle kernel identity: {kernel_hash}"
                        )
                    stable_ids = existing["stable_ids"]
                    if stable_id not in stable_ids:
                        stable_ids.append(stable_id)
                        stable_ids.sort()
                    continue
                for stage_name in sorted(expected_stages):
                    source_name = f"particle-{kernel_hash}-{stage_name}.comp"
                    (shader_root / source_name).write_text(
                        stages[stage_name], encoding="utf-8", newline="\n"
                    )
                    shader_name = f"Particle/{kernel_hash}/{stage_name}"
                    shader_entries.append(
                        {
                            "name": shader_name,
                            "stage": "compute",
                            "source": source_name,
                        }
                    )
                    kernel_record["stages"][stage_name] = shader_name
                particle_kernels[kernel_hash] = kernel_record

    manifest = {
        "$schema": "infernux.web_shader_cook",
        "shaders": shader_entries,
    }
    (shader_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    particle_catalog = {
        "$schema": "infernux.web_particle_catalog",
        "kernels": sorted(
            particle_kernels.values(), key=lambda item: str(item["kernel_hash"])
        ),
    }
    (player_assets / "web-particles").mkdir(parents=True, exist_ok=True)
    (player_assets / "web-particles" / "catalog.json").write_text(
        json.dumps(
            particle_catalog, ensure_ascii=False, indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    request.report("shaders", 1, 2, "Shared fullscreen GLSL prepared")


def _assemble_web_host(
    request: BuildRequest,
    staging: Path,
    player_assets: Path,
    details: dict[str, object],
    source_package: Path,
    presentation: dict[str, object],
    web_shell: Path,
    project_web_template: Path | None,
) -> tuple[str, ...]:
    """Assemble project content around the plugin's immutable native payload."""
    from Infernux.engine.player_package_native import write_pack
    from .shader_pipeline import compile_shader_manifest

    # InxPack carries bytes, not POSIX modes. Restore execute permission only
    # for the two declared native tools when consuming an installed package.
    if os.name != "nt":
        for name in ("glslang", "tint"):
            tool = Path(str(details[name]))
            tool.chmod(tool.stat().st_mode | 0o111)
    compile_shader_manifest(
        staging / "shader-cook" / "manifest.json",
        player_assets / "web-shaders",
        glslang=str(details["glslang"]),
        tint=str(details["tint"]),
    )
    request.report("shaders", 2, 2, "Validated WGSL shader catalog ready")
    runtime = Path(str(details["player_root"]))
    revision = _web_asset_revision(
        staging, player_assets, runtime, presentation=presentation,
        project_template_root=project_web_template,
    )
    build_root = staging / "host-build"
    build_root.mkdir(parents=True)
    for suffix in ("js", "wasm", "data"):
        shutil.copy2(runtime / f"infernux-runtime.{suffix}",
                     build_root / f"infernux-player.{revision}.{suffix}")
    write_pack(
        [(path.relative_to(player_assets).as_posix(), path)
         for path in sorted(player_assets.rglob("*")) if path.is_file()],
        build_root / f"infernux-player.{revision}.inxpkg",
        profile=request.profile.configuration.value,
    )
    for path in (player_assets / "web-branding").iterdir():
        if path.is_file():
            shutil.copy2(path, build_root / path.name)
    shutil.copy2(source_package / "resources/icons/icon.png",
                 build_root / "infernux-logo.png")
    shutil.copy2(player_assets / WEBGPU_CAPABILITY_FILENAME,
                 build_root / WEBGPU_CAPABILITY_FILENAME)
    document = web_shell.read_text(encoding="utf-8")
    replacements = {
        "@INFERNUX_WEB_ASSET_REVISION@": revision,
        "@INFERNUX_WEB_DISPLAY_MODE@": str(presentation["display_mode"]),
        "@INFERNUX_WEB_CANVAS_WIDTH@": str(presentation["window_width"]),
        "@INFERNUX_WEB_CANVAS_HEIGHT@": str(presentation["window_height"]),
    }
    for marker, value in replacements.items():
        document = document.replace(marker, value)
    # This loader uses the same InxPack format as desktop content. C++ unpacks
    # into browser memory before starting Python; the web server never exposes
    # the project's directory tree.
    loader = (Path(__file__).parent / "templates" / "load_content.js").read_text(
        encoding="utf-8"
    ).replace("@INFERNUX_WEB_ASSET_REVISION@", revision)
    loader = loader.replace("@INFERNUX_WEB_PRESENTATION@", json.dumps({
        "mode": presentation["display_mode"],
        "width": presentation["window_width"],
        "height": presentation["window_height"],
    }))
    script = (f"<script>{loader}</script>\n"
              f'<script src="infernux-player.{revision}.js"></script>')
    (build_root / "infernux-player.html").write_text(
        document.replace("{{{ SCRIPT }}}", script), encoding="utf-8", newline="\n"
    )
    request.report("runtime", 1, 1, "Precompiled Web Player assembled")
    return ()


def _web_asset_revision(
    staging: Path,
    player_assets: Path,
    host_template_source: Path,
    *,
    presentation: dict[str, object],
    project_template_root: Path | None = None,
) -> str:
    """Hash every staged byte that can change the browser asset bundle."""

    digest = hashlib.sha256()
    digest.update(
        json.dumps(
            presentation,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )
    digest.update(b"\0")
    roots = [
        ("player", player_assets),
        ("runtime", host_template_source),
        ("templates", Path(__file__).parent / "templates"),
        ("shaders", staging / "shader-cook"),
    ]
    if project_template_root is not None:
        roots.append(("project-template", project_template_root))
    files: list[tuple[str, Path]] = []
    for label, root in roots:
        if not root.is_dir():
            raise RuntimeError(f"Web asset revision input is missing: {root}")
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            files.append((f"{label}/{path.relative_to(root).as_posix()}", path))
    for relative, path in sorted(files, key=lambda item: item[0]):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()[:24]


__all__ = ["WebPlatformExporter"]
