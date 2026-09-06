# Web Platform

![Build workflow](media/overview.png)

Build browser Players with CPython 3.13 compiled to WebAssembly and rendering through WebGPU. The package owns the Emscripten build integration, browser host, input bridges, diagnostics and project HTML template integration.

## Before building

Infernux 0.4.0, an engine source checkout with submodules, and the pinned Linux Web toolchain. Windows builds run through WSL2 (Ubuntu-22.04 by default). A WebGPU-capable browser is required; WebGL is not a fallback.

## Toolchain setup

The plugin is not a precompiled Web SDK. Set INFERNUX_SOURCE_ROOT to the engine checkout. In Linux or WSL, the engine's scripts/setup/build_web_toolchain.sh installs the pinned toolchain into a chosen directory. The current versions are Emscripten 4.0.10, CPython 3.13.15 and Emdawnwebgpu v20260423.175430; the shader compiler uses the pinned Dawn/Tint revision recorded in doctor.py.

Configure INFERNUX_EMSDK_ROOT, INFERNUX_WEB_CPYTHON_ROOT and INFERNUX_WEB_TINT for that installation. Windows may select its WSL distribution with INFERNUX_WEB_WSL_DISTRIBUTION. Use Linux paths for the toolchain inside WSL. Toolchain setup is separate from downloading this plugin.

## Export and serve

Select web-wasm32 in the build settings. Publish the whole generated directory, including infernux-player.html, JavaScript, WebAssembly and game data. Serve it over HTTP on localhost for testing, or HTTPS for deployment; do not open the page through file://. Browser permissions and device capabilities must allow WebGPU.

## Project Web template

Create ProjectSettings/WebTemplate/shell.html from package/editor/infernux_web/templates/host/shell.html. Keep the runtime markers and canvas integration intact while changing CSS, metadata and the surrounding page. Other template files are exported under web-template/ with relative directories preserved.

Once the template directory exists, shell.html is required. Rebuilding replaces generated output: edit project template sources, not the exported files. Gameplay UI uses Infernux Screen UI; the HTML shell hosts the game rather than implementing its UI as DOM elements.

## Troubleshooting

A visible target does not prove its toolchain is ready. Fix the build diagnostics for missing engine sources, Emscripten, CPython or shader tools before exporting. If the browser cannot initialize WebGPU, use a supported browser/device and check its GPU settings; there is no alternate WebGL rendering path.
