# Infernux Web Platform

[简体中文](README.zh-CN.md) · [Releases](https://github.com/ChenlizheMe/infernux_web/releases) · [Infernux](https://github.com/ChenlizheMe/Infernux)

![Web build workflow](package/plugin_pages/media/overview.png)

Build browser Players with CPython 3.13 compiled to WebAssembly and rendering through WebGPU. The package includes precompiled WASM/JavaScript, CPython data and native Windows/Linux shader tools, alongside the browser host, input bridges and project HTML templates.

## At a glance

| Item | Value |
| --- | --- |
| Package | `infernux/platform-web` |
| Plugin version | 0.2.0 |
| Engine compatibility | ==0.4.0 |
| Target | `web-wasm32` |
| Build host | Windows x64 / Linux x64 |
| Rendering | WebAssembly / WebGPU |

## Install

1. Open your project in Infernux 0.4.0 and open the Plugins panel.
2. Select Infernux Web Platform in the official list, then import and enable it.
3. Open the build settings and select the target. Resolve the reported prerequisites before exporting.

If your editor's bundled catalog predates this repository, add `https://github.com/ChenlizheMe/infernux_web` as a GitHub plugin source, or import `infernux.platform-web.inxpkg` from [Releases](https://github.com/ChenlizheMe/infernux_web/releases/latest). GitHub's automatic source ZIP is the author repository, not the installable plugin artifact.

## Requirements

Infernux 0.4.0 on Windows x64 or Linux x64, and a WebGPU-capable browser. Ordinary exports require no engine sources, Git submodules, CMake, WSL or Emscripten.

## Included payload

`editor/infernux_web/player/` contains the precompiled runtime and CPython data. `tools/windows-x64/` and `tools/linux-x64/` contain glslang and Tint. Installing this plugin supplies the Web build payload; no separate Web SDK download is required.

Export cooks project content, translates GLSL to WGSL, writes an `.inxpkg` and assembles the web page. It does not rebuild the engine. Browser startup loads the binary package into memory instead of publishing Assets, Library or the project source tree as HTTP directories.

## Export and serve

Select web-wasm32 in the build settings. Publish the whole generated directory, including infernux-player.html, JavaScript, WebAssembly and game data. Serve it over HTTP on localhost for testing, or HTTPS for deployment; do not open the page through file://. Browser permissions and device capabilities must allow WebGPU.

## Project Web template

Create ProjectSettings/WebTemplate/shell.html from package/editor/infernux_web/templates/host/shell.html. Keep the runtime markers and canvas integration intact while changing CSS, metadata and the surrounding page. Other template files are exported under web-template/ with relative directories preserved.

Once the template directory exists, shell.html is required. Rebuilding replaces generated output: edit project template sources, not the exported files. Gameplay UI uses Infernux Screen UI; the HTML shell hosts the game rather than implementing its UI as DOM elements.

## Troubleshooting

If the payload is missing or incompatible, explicitly select a complete `.inxpkg` matching the engine version. Do not install GitHub's source archive as a runtime payload. If the browser cannot initialize WebGPU, use a supported browser/device and check its GPU settings; there is no alternate WebGL rendering path.

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

Run `python package.py dist/infernux.platform-web.inxpkg` to package locally. This standalone script uses only Python's standard library and does not require an engine installation. Build outside package/, then place the files to ship inside package/ before packaging.

Maintainers build from the outer `native/` directory: CMake targets `prebuild_web_player` and `prebuild_web_tools` publish directly into the plugin. Ordinary users never run those builds. Run `python release.py v0.2.0` to create the archive and its release manifest. Pushing a matching version tag publishes both files through GitHub Actions. The editor uses that manifest to select a compatible release.

## License

[MIT](LICENSE). Third-party SDKs and the engine runtime keep their own licenses; they are not relicensed by this plugin.
