# Infernux Web 平台插件

[English](README.md) · [发布制品](https://github.com/ChenlizheMe/infernux_web/releases) · [Infernux](https://github.com/ChenlizheMe/Infernux)

![Web 构建流程](package/plugin_pages/media/overview.png)

通过编译为 WebAssembly 的 CPython 3.13 和 WebGPU 渲染构建浏览器 Player。插件负责 Emscripten 构建集成、浏览器宿主、输入桥接、诊断和项目 HTML 模板集成。

## 基本信息

| 项目 | 内容 |
| --- | --- |
| 包标识 | `infernux/platform-web` |
| 插件版本 | 0.1.0 |
| 引擎兼容范围 | >=0.4.0,<0.5 |
| 构建目标 | `web-wasm32` |
| 构建宿主 | Linux or Windows + WSL2 |

## 安装

1. 在 Infernux 0.4.0 中打开项目，进入插件面板。
2. 在官方列表选择 Infernux Web Platform，导入并启用。
3. 打开构建设置，选择目标，按诊断补齐依赖后导出。

如果编辑器仍使用旧版内置目录，可以手动添加 GitHub 源 `https://github.com/ChenlizheMe/infernux_web`，或从 [Releases](https://github.com/ChenlizheMe/infernux_web/releases/latest) 下载 `infernux.platform-web.inxpkg` 后导入。GitHub 自动生成的源码 ZIP 是作者仓库，不是插件安装制品。

## 环境要求

Infernux 0.4.0、包含子模块的引擎源码，以及固定版本的 Linux Web 工具链。Windows 通过 WSL2 构建，默认发行版为 Ubuntu-22.04。浏览器必须支持 WebGPU，不以 WebGL 兜底。

## 工具链安装

此插件不是预编译 Web SDK。用 INFERNUX_SOURCE_ROOT 指向引擎源码，在 Linux 或 WSL 中运行引擎的 scripts/setup/build_web_toolchain.sh，将固定工具链安装到指定目录。当前版本为 Emscripten 4.0.10、CPython 3.13.15 和 Emdawnwebgpu v20260423.175430；着色器编译使用 doctor.py 记录的固定 Dawn/Tint 提交。

配置 INFERNUX_EMSDK_ROOT、INFERNUX_WEB_CPYTHON_ROOT、INFERNUX_WEB_TINT。Windows 可通过 INFERNUX_WEB_WSL_DISTRIBUTION 选择 WSL 发行版，WSL 内工具链须使用 Linux 路径。工具链准备与下载此插件是两件事。

## 导出与访问

构建设置中选择 web-wasm32。发布整个输出目录，包括 infernux-player.html、JavaScript、WebAssembly 和游戏数据。本机测试使用 localhost HTTP，部署使用 HTTPS，不要通过 file:// 打开页面。浏览器权限和设备能力必须允许 WebGPU。

## 项目 Web 模板

将 package/editor/infernux_web/templates/host/shell.html 复制为项目 ProjectSettings/WebTemplate/shell.html。可以调整样式、元数据和外围页面，但须保留运行时标记与画布集成。其他模板资源导出到 web-template/，保持相对目录关系。

模板目录一旦存在就必须包含 shell.html。重新构建会替换生成内容，应编辑项目模板源文件而不是导出文件。游戏 UI 使用 Infernux Screen UI，HTML 是页面宿主，不是游戏的 DOM 渲染层。

## 排错

构建目标可见不等于工具链已就绪。先解决引擎源码、Emscripten、CPython、着色器工具缺失诊断。浏览器无法初始化 WebGPU 时，检查浏览器、设备支持和 GPU 设置；不存在 WebGL 渲染兜底。

## 开发与打包

只有 `package/` 内的内容进入 InxPackage。外层 README、SVG 配图源文件、发布流程和构建脚本属于仓库，不进入插件。引擎内文档独立位于 `package/plugin_pages/`。

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

运行 `python package.py dist/infernux.platform-web.inxpkg` 本地打包。脚本仅使用 Python 标准库，不需要导入或安装 Infernux。在外层进行构建，最后将需要交付的文件放进 package/ 即可。

维护者运行 `python release.py v0.1.0` 生成插件和发布清单；推送与插件版本一致的标签后，由 GitHub Actions 打包并上传两个文件。编辑器根据发布清单选择兼容版本。

## 许可证

[MIT](LICENSE)。第三方 SDK 和引擎运行时各自遵守原有许可证，不因本插件而改变。
