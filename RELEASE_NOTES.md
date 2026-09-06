# Infernux Web Platform 0.2.0

Official platform package for Infernux 0.4.0.

- Ships a precompiled WebGPU/CPython WASM runtime and native Windows/Linux shader tools.
- Ordinary exports cook assets and assemble browser files without engine sources, CMake, WSL or Emscripten.
- Separates project content into an InxPackage loaded before Python starts; no project directory tree is published.
- Windowed/fullscreen presentation is selected at runtime without relinking.
- Includes English and Simplified Chinese documentation with a build workflow illustration.
- Ships an installable InxPackage and the engine's compatible-release manifest.

## Requirements

Infernux 0.4.0 on Windows x64 or Linux x64. A WebGPU-capable browser is required; WebGL is not a fallback.

Download the .inxpkg asset to install the plugin. The automatic source archives are for plugin development. See the README for setup, output and troubleshooting details.
