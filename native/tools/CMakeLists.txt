cmake_minimum_required(VERSION 3.25)
project(InfernuxWebShaderTools LANGUAGES C CXX)

# Release engineering only. Editors execute the published native tools directly.
include(ExternalProject)
set(INFERNUX_DAWN_SOURCE "" CACHE PATH "Pinned Dawn source with fetched dependencies")
set(INFERNUX_ENGINE_SOURCE_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../../../.." CACHE PATH
    "Matching engine checkout providing glslang")
if(WIN32)
    set(_host windows-x64)
elseif(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    set(_host linux-x64)
else()
    message(FATAL_ERROR "Web shader tools support Windows and Linux x64 hosts")
endif()
if(NOT EXISTS "${INFERNUX_DAWN_SOURCE}/CMakeLists.txt")
    message(FATAL_ERROR "INFERNUX_DAWN_SOURCE must contain the pinned Dawn source")
endif()
set(_tools "${CMAKE_CURRENT_SOURCE_DIR}/../../package/editor/infernux_web/tools/${_host}")
set(_common_args
    -DCMAKE_BUILD_TYPE=Release
    -DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded
    -DCMAKE_POLICY_DEFAULT_CMP0091=NEW
    -DBUILD_SHARED_LIBS=OFF)
ExternalProject_Add(web_tint
    SOURCE_DIR "${INFERNUX_DAWN_SOURCE}"
    BINARY_DIR "${CMAKE_CURRENT_BINARY_DIR}/tint"
    DOWNLOAD_COMMAND ""
    CMAKE_GENERATOR Ninja
    CMAKE_ARGS ${_common_args}
        -DDAWN_FETCH_DEPENDENCIES=OFF
        -DDAWN_BUILD_BENCHMARKS=OFF -DDAWN_BUILD_FUZZERS=OFF
        -DDAWN_BUILD_NODE_BINDINGS=OFF -DDAWN_BUILD_SAMPLES=OFF -DDAWN_BUILD_TESTS=OFF
        -DDAWN_ENABLE_D3D11=OFF -DDAWN_ENABLE_D3D12=OFF -DDAWN_ENABLE_DESKTOP_GL=OFF
        -DDAWN_ENABLE_METAL=OFF -DDAWN_ENABLE_NULL=OFF -DDAWN_ENABLE_OPENGLES=OFF
        -DDAWN_ENABLE_VULKAN=OFF -DDAWN_USE_GLFW=OFF -DDAWN_USE_WAYLAND=OFF -DDAWN_USE_X11=OFF
        -DTINT_BUILD_BENCHMARKS=OFF -DTINT_BUILD_CMD_TOOLS=ON -DTINT_BUILD_FUZZERS=OFF
        -DTINT_BUILD_GLSL_READER=OFF -DTINT_BUILD_GLSL_WRITER=OFF
        -DTINT_BUILD_HLSL_WRITER=OFF -DTINT_BUILD_MSL_WRITER=OFF
        -DTINT_BUILD_SPV_READER=ON -DTINT_BUILD_SPV_WRITER=OFF
        -DTINT_BUILD_TESTS=OFF -DTINT_BUILD_TINTD=OFF
        -DTINT_BUILD_WGSL_READER=ON -DTINT_BUILD_WGSL_WRITER=ON
    BUILD_COMMAND "${CMAKE_COMMAND}" --build <BINARY_DIR> --target tint_cmd_tint_cmd --parallel 2
    BUILD_ALWAYS TRUE
    INSTALL_COMMAND "${CMAKE_COMMAND}" -E make_directory "${_tools}"
        COMMAND "${CMAKE_COMMAND}" -E copy_if_different
            "<BINARY_DIR>/tint${CMAKE_EXECUTABLE_SUFFIX}" "${_tools}"
)
ExternalProject_Add(web_glslang
    SOURCE_DIR "${INFERNUX_ENGINE_SOURCE_ROOT}/external/glslang"
    BINARY_DIR "${CMAKE_CURRENT_BINARY_DIR}/glslang"
    DOWNLOAD_COMMAND ""
    CMAKE_GENERATOR Ninja
    CMAKE_ARGS ${_common_args}
        -DCMAKE_RUNTIME_OUTPUT_DIRECTORY=${CMAKE_CURRENT_BINARY_DIR}/bin
        -DENABLE_GLSLANG_BINARIES=ON -DENABLE_SPIRV=ON
        -DENABLE_OPT=OFF -DENABLE_HLSL=OFF -DBUILD_TESTING=OFF -DGLSLANG_TESTS=OFF
    BUILD_COMMAND "${CMAKE_COMMAND}" --build <BINARY_DIR> --target glslang-standalone --parallel 2
    BUILD_ALWAYS TRUE
    INSTALL_COMMAND "${CMAKE_COMMAND}" -E make_directory "${_tools}"
        COMMAND "${CMAKE_COMMAND}" -E copy_if_different
            "${CMAKE_CURRENT_BINARY_DIR}/bin/glslang${CMAKE_EXECUTABLE_SUFFIX}"
            "${_tools}/glslangValidator${CMAKE_EXECUTABLE_SUFFIX}"
)
add_custom_target(prebuild_web_tools DEPENDS web_tint web_glslang)
