#pragma once

#include <cstdint>
#include <limits>
#include <string>
#include <string_view>

namespace infernux::web
{
namespace detail
{
inline bool IsSpace(char value) noexcept
{
    return value == ' ' || value == '\t' || value == '\r' || value == '\n';
}

inline std::string_view Trim(std::string_view value) noexcept
{
    while (!value.empty() && IsSpace(value.front()))
        value.remove_prefix(1);
    while (!value.empty() && IsSpace(value.back()))
        value.remove_suffix(1);
    return value;
}

inline bool ParseAttribute(std::string_view source, size_t marker, std::string_view name, uint32_t &value,
                          size_t &end) noexcept
{
    size_t cursor = marker + name.size();
    while (cursor < source.size() && IsSpace(source[cursor]))
        ++cursor;
    if (cursor >= source.size() || source[cursor++] != '(')
        return false;
    while (cursor < source.size() && IsSpace(source[cursor]))
        ++cursor;
    if (cursor >= source.size() || source[cursor] < '0' || source[cursor] > '9')
        return false;
    uint32_t parsed = 0;
    while (cursor < source.size() && source[cursor] >= '0' && source[cursor] <= '9') {
        const uint32_t digit = static_cast<uint32_t>(source[cursor++] - '0');
        if (parsed > (std::numeric_limits<uint32_t>::max() - digit) / 10)
            return false;
        parsed = parsed * 10 + digit;
    }
    if (cursor < source.size() && source[cursor] == 'u')
        ++cursor;
    while (cursor < source.size() && IsSpace(source[cursor]))
        ++cursor;
    if (cursor >= source.size() || source[cursor++] != ')')
        return false;
    value = parsed;
    end = cursor;
    return true;
}

inline bool IsReadOnlyStorage(std::string_view variable) noexcept
{
    const size_t qualifierStart = variable.find('<');
    const size_t qualifierEnd = variable.find('>');
    if (qualifierStart == std::string_view::npos || qualifierEnd == std::string_view::npos ||
        qualifierEnd <= qualifierStart)
        return false;
    const auto qualifier = variable.substr(qualifierStart + 1, qualifierEnd - qualifierStart - 1);
    const size_t comma = qualifier.find(',');
    return comma != std::string_view::npos && Trim(qualifier.substr(0, comma)) == "storage" &&
           Trim(qualifier.substr(comma + 1)) == "read";
}
} // namespace detail

// The shared FullscreenRenderer builds set/group 0 with one resource per
// input. WebGPU splits combined samplers into reserved bindings 500+, and
// reserves binding 999 for push constants; neither is an input resource.
inline bool ValidateFullscreenShaderInputs(std::string_view source, uint32_t inputCount, uint32_t inputBufferMask,
                                           std::string &error)
{
    if (inputCount > 32 || (inputCount < 32 && (inputBufferMask >> inputCount) != 0)) {
        error = "fullscreen input buffer mask names a binding outside the graph inputs";
        return false;
    }

    uint32_t seenInputs = 0;
    size_t cursor = 0;
    while ((cursor = source.find("@group", cursor)) != std::string_view::npos) {
        uint32_t group = 0;
        size_t groupEnd = 0;
        if (!detail::ParseAttribute(source, cursor, "@group", group, groupEnd)) {
            cursor += 6;
            continue;
        }
        const size_t statementEnd = source.find(';', groupEnd);
        const size_t bindingMarker = source.find("@binding", groupEnd);
        const size_t nextGroup = source.find("@group", groupEnd);
        if (statementEnd == std::string_view::npos || bindingMarker == std::string_view::npos ||
            bindingMarker > statementEnd || (nextGroup != std::string_view::npos && nextGroup < bindingMarker)) {
            cursor = groupEnd;
            continue;
        }
        uint32_t binding = 0;
        size_t bindingEnd = 0;
        if (!detail::ParseAttribute(source, bindingMarker, "@binding", binding, bindingEnd) ||
            bindingEnd >= statementEnd) {
            cursor = statementEnd + 1;
            continue;
        }
        cursor = statementEnd + 1;
        if (group != 0 || binding >= 500)
            continue;

        const std::string_view declaration = source.substr(bindingEnd, statementEnd - bindingEnd);
        const size_t varMarker = declaration.find("var");
        const size_t colon = declaration.find(':');
        if (varMarker == std::string_view::npos || colon == std::string_view::npos || varMarker >= colon) {
            error = "fullscreen shader has an invalid group 0 input declaration at binding " +
                    std::to_string(binding);
            return false;
        }
        const std::string_view variable = declaration.substr(varMarker, colon - varMarker);
        const bool storageBuffer = detail::IsReadOnlyStorage(variable);
        const auto type = detail::Trim(declaration.substr(colon + 1));
        const bool sampledTexture = type.compare(0, 8, "texture_") == 0 &&
                                    type.compare(0, 16, "texture_storage_") != 0;
        const bool expectsBuffer = binding < 32 && (inputBufferMask & (1u << binding)) != 0;
        if (binding >= inputCount || (expectsBuffer ? !storageBuffer : !sampledTexture)) {
            error = "fullscreen shader group 0 binding " + std::to_string(binding) +
                    " does not match the graph's storage-buffer/texture inputs";
            return false;
        }
        const uint32_t bit = 1u << binding;
        if ((seenInputs & bit) != 0) {
            error = "fullscreen shader declares group 0 binding " + std::to_string(binding) + " more than once";
            return false;
        }
        seenInputs |= bit;
    }
    const uint32_t expectedInputs = inputCount == 32 ? std::numeric_limits<uint32_t>::max()
                                                     : (1u << inputCount) - 1u;
    if (seenInputs != expectedInputs) {
        error = "fullscreen shader must declare each graph input binding exactly once";
        return false;
    }
    error.clear();
    return true;
}
} // namespace infernux::web
