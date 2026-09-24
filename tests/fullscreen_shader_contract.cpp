#include "../native/WebFullscreenShaderContract.h"
#include "../../../../cpp/infernux/function/renderer/rhi/RhiDescriptors.h"

#include <iostream>
#include <string>
#include <string_view>

static_assert(!infernux::rhi::ShaderModuleDesc::FromWgsl("", 0).widenReadOnlyStorage);
static_assert(infernux::rhi::ShaderModuleDesc::FromWgsl("", 0, true).widenReadOnlyStorage);
static_assert(!infernux::rhi::BindingLayoutEntry{}.readOnlyStorage);

namespace
{
bool Check(std::string_view source, uint32_t count, uint32_t mask, bool expected, std::string_view label)
{
    std::string error;
    const bool result = infernux::web::ValidateFullscreenShaderInputs(source, count, mask, error);
    if (result == expected && (result || !error.empty()))
        return true;
    std::cerr << label << ": expected " << expected << ", got " << result << ", error=" << error << '\n';
    return false;
}
} // namespace

int main()
{
    constexpr std::string_view texture =
        "@group(0u) @binding(0u) var color: texture_2d<f32>;\n"
        "@group(0u) @binding(500u) var color_sampler: sampler;\n";
    constexpr std::string_view storage =
        "@group(0) @binding(0) var<storage, read> values: array<u32>;\n";
    constexpr std::string_view mixed =
        "@group(0u) @binding(0u) var<storage, read> values: array<u32>;\n"
        "@group(0u) @binding(1u) var depth: texture_depth_2d;\n"
        "@group(0u) @binding(501u) var depth_sampler: sampler_comparison;\n"
        "@group(0u) @binding(999u) var<uniform> push: PushConstants;\n";
    constexpr std::string_view uniform =
        "@group(0) @binding(0) var<uniform> values: Params;\n";
    constexpr std::string_view storageTexture =
        "@group(0) @binding(0) var image: texture_storage_2d<rgba8unorm, write>;\n";
    constexpr std::string_view writableStorage =
        "@group(0) @binding(0) var<storage, read_write> values: array<u32>;\n";
    constexpr std::string_view duplicate =
        "@group(0) @binding(0) var first: texture_2d<f32>;\n"
        "@group(0) @binding(0) var second: texture_2d<f32>;\n";

    return Check(texture, 1, 0, true, "texture and reserved sampler") &&
                   Check(storage, 1, 1, true, "storage buffer") &&
                   Check(mixed, 2, 1, true, "mixed buffer and depth texture") &&
                   Check(storage, 1, 0, false, "storage declared for a texture input") &&
                   Check(texture, 1, 1, false, "texture declared for a buffer input") &&
                   Check(uniform, 1, 0, false, "uniform is not a texture") &&
                   Check(storageTexture, 1, 0, false, "storage image is not a sampled texture") &&
                   Check(writableStorage, 1, 1, false, "fullscreen buffer input must be read-only") &&
                   Check(texture, 2, 0, false, "missing second texture input") &&
                   Check("", 1, 1, false, "missing only buffer input") &&
                   Check(duplicate, 1, 0, false, "duplicate input binding") &&
                   Check(storage, 0, 0, false, "shader binding exceeds input count") &&
                   Check(storage, 1, 2, false, "mask exceeds input count") &&
                   Check("", 0, 0, true, "no inputs")
               ? 0
               : 1;
}
