# Infernux Web Platform

[简体中文](README.zh-CN.md) · [Releases](https://github.com/ChenlizheMe/infernux_web/releases) · [Infernux](https://github.com/ChenlizheMe/Infernux)

![Web build workflow](package/plugin_pages/media/overview.png)

Build browser Players with CPython 3.13 compiled to WebAssembly and rendering through WebGPU. The package owns the Emscripten build integration, browser host, input bridges, diagnostics and project HTML template integration.

## At a glance

| Item | Value |
| --- | --- |
| Package | `infernux/platform-web` |
| Plugin version | 0.1.0 |
| Engine compatibility | >=0.4.0,<0.5 |
| Target | `web-wasm32` |
| Build host | Linux or Windows + WSL2 |
| Rendering | WebAssembly / WebGPU |

## Install

1. Open your project in Infernux 0.4.0 and open the Plugins panel.
2. Select Infernux Web Platform in the official list, then import and enable it.
3. Open the build settings and select the target. Resolve the reported prerequisites before exporting.

If your editor's bundled catalog predates this repository, add `https://github.com/ChenlizheMe/infernux_web` as a GitHub plugin source, or import `infernux.platform-web.inxpkg` from [Releases](https://github.com/ChenlizheMe/infernux_web/releases/latest). GitHub's automatic source ZIP is the author repository, not the installable plugin artifact.

## Requirements

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

## Develop and package

Only `package/` becomes the InxPackage payload. The outer README, SVG illustration sources, release automation and build scripts remain repository files. In-editor documentation is separate, under `package/plugin_pages/`.

```text
package/
  inx_package.json
  editor/infernux_web/
  plugin_pages/
package.py
release.py
README.md
README.zh-CN.md
```

Run `python package.py dist/infernux.platform-web.inxpkg` to package locally. This standalone script uses only Python's standard library and does not import Infernux. Build outside package/, then place the files to ship inside package/ before packaging.

Maintainers run `python release.py v0.1.0` to create the archive and its release manifest. Pushing a matching version tag publishes both files through GitHub Actions. The editor uses that manifest to select a compatible release.

## License

[MIT](LICENSE). Third-party SDKs and the engine runtime keep their own licenses; they are not relicensed by this plugin.
