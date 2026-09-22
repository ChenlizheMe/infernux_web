#pragma once

#include <function/renderer/InxRenderStruct.h>

#include <cstddef>
#include <cstdint>
#include <vector>

namespace infernux::web
{

/// Draw-local location in one of the two WebGPU index streams.  Keeping the
/// format in the range makes a mesh format change select a different buffer
/// instead of reusing bytes published under the previous interpretation.
struct WebPackedIndexRange
{
    MeshIndexFormat format = MeshIndexFormat::UInt32;
    uint32_t firstIndex = 0;
    uint32_t indexCount = 0;
    int32_t baseVertex = 0;
};

struct WebPackedIndexStreams
{
    std::vector<uint16_t> uint16Indices;
    std::vector<uint32_t> uint32Indices;
};

/// Validate and append one draw to the format-specific GPU stream.
///
/// Source indices remain authoritative uint32_t values.  The global vertex
/// rebase is carried by DrawIndexed(baseVertex), so a UInt16 mesh stays UInt16
/// even when preceding draws make its global vertex offset exceed 65535.
/// Validation and capacity reservation complete before either stream changes;
/// malformed ranges and overflows therefore reject the draw atomically.
WebPackedIndexRange PackWebIndexRange(WebPackedIndexStreams &streams, MeshIndexFormat requestedFormat,
                                      size_t vertexBase, size_t vertexCount,
                                      const std::vector<uint32_t> &authoritativeIndices, size_t indexStart,
                                      size_t indexCount);

} // namespace infernux::web
