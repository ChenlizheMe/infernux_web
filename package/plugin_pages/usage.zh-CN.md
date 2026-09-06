# Web 平台

![构建流程](media/overview.png)

通过编译为 WebAssembly 的 CPython 3.13 和 WebGPU 渲染构建浏览器 Player。插件负责 Emscripten 构建集成、浏览器宿主、输入桥接、诊断和项目 HTML 模板集成。

## 构建前准备

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
