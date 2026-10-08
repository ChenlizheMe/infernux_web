#pragma once

#include <SDL3/SDL_scancode.h>
#include <string_view>

namespace infernux::web
{

// KeyboardEvent.code identifies the physical key, independently of layout,
// Shift and NumLock. Text composition follows the separate text-input path.
inline int BrowserCodeToScancode(std::string_view code) noexcept
{
    if (code.size() == 4 && code.substr(0, 3) == "Key" && code[3] >= 'A' && code[3] <= 'Z')
        return SDL_SCANCODE_A + (code[3] - 'A');
    if (code.size() == 6 && code.substr(0, 5) == "Digit" && code[5] >= '1' && code[5] <= '9')
        return SDL_SCANCODE_1 + (code[5] - '1');
    if (code.size() == 7 && code.substr(0, 6) == "Numpad" && code[6] >= '1' && code[6] <= '9')
        return SDL_SCANCODE_KP_1 + (code[6] - '1');
    if ((code.size() == 2 || code.size() == 3) && code[0] == 'F' && code[1] >= '1' && code[1] <= '9') {
        int number = code[1] - '0';
        if (code.size() == 3) {
            if (code[2] < '0' || code[2] > '9')
                return -1;
            number = number * 10 + code[2] - '0';
        }
        if (number <= 12)
            return SDL_SCANCODE_F1 + number - 1;
        if (number <= 24)
            return SDL_SCANCODE_F13 + number - 13;
        return -1;
    }
    struct Mapping
    {
        std::string_view code;
        SDL_Scancode scancode;
    };
    static constexpr Mapping keys[] = {
        {"Digit0", SDL_SCANCODE_0},
        {"Enter", SDL_SCANCODE_RETURN},
        {"Escape", SDL_SCANCODE_ESCAPE},
        {"Backspace", SDL_SCANCODE_BACKSPACE},
        {"Tab", SDL_SCANCODE_TAB},
        {"Space", SDL_SCANCODE_SPACE},
        {"Minus", SDL_SCANCODE_MINUS},
        {"Equal", SDL_SCANCODE_EQUALS},
        {"BracketLeft", SDL_SCANCODE_LEFTBRACKET},
        {"BracketRight", SDL_SCANCODE_RIGHTBRACKET},
        {"Backslash", SDL_SCANCODE_BACKSLASH},
        {"Semicolon", SDL_SCANCODE_SEMICOLON},
        {"Quote", SDL_SCANCODE_APOSTROPHE},
        {"Backquote", SDL_SCANCODE_GRAVE},
        {"Comma", SDL_SCANCODE_COMMA},
        {"Period", SDL_SCANCODE_PERIOD},
        {"Slash", SDL_SCANCODE_SLASH},
        {"CapsLock", SDL_SCANCODE_CAPSLOCK},
        {"PrintScreen", SDL_SCANCODE_PRINTSCREEN},
        {"ScrollLock", SDL_SCANCODE_SCROLLLOCK},
        {"Pause", SDL_SCANCODE_PAUSE},
        {"Insert", SDL_SCANCODE_INSERT},
        {"Home", SDL_SCANCODE_HOME},
        {"PageUp", SDL_SCANCODE_PAGEUP},
        {"Delete", SDL_SCANCODE_DELETE},
        {"End", SDL_SCANCODE_END},
        {"PageDown", SDL_SCANCODE_PAGEDOWN},
        {"ArrowRight", SDL_SCANCODE_RIGHT},
        {"ArrowLeft", SDL_SCANCODE_LEFT},
        {"ArrowDown", SDL_SCANCODE_DOWN},
        {"ArrowUp", SDL_SCANCODE_UP},
        {"NumLock", SDL_SCANCODE_NUMLOCKCLEAR},
        {"NumpadDivide", SDL_SCANCODE_KP_DIVIDE},
        {"NumpadMultiply", SDL_SCANCODE_KP_MULTIPLY},
        {"NumpadSubtract", SDL_SCANCODE_KP_MINUS},
        {"NumpadAdd", SDL_SCANCODE_KP_PLUS},
        {"NumpadEnter", SDL_SCANCODE_KP_ENTER},
        {"Numpad0", SDL_SCANCODE_KP_0},
        {"NumpadDecimal", SDL_SCANCODE_KP_PERIOD},
        {"NumpadEqual", SDL_SCANCODE_KP_EQUALS},
        {"NumpadComma", SDL_SCANCODE_KP_COMMA},
        {"ContextMenu", SDL_SCANCODE_APPLICATION},
        {"ControlLeft", SDL_SCANCODE_LCTRL},
        {"ShiftLeft", SDL_SCANCODE_LSHIFT},
        {"AltLeft", SDL_SCANCODE_LALT},
        {"MetaLeft", SDL_SCANCODE_LGUI},
        {"ControlRight", SDL_SCANCODE_RCTRL},
        {"ShiftRight", SDL_SCANCODE_RSHIFT},
        {"AltRight", SDL_SCANCODE_RALT},
        {"MetaRight", SDL_SCANCODE_RGUI},
        {"IntlBackslash", SDL_SCANCODE_NONUSBACKSLASH},
        {"IntlRo", SDL_SCANCODE_INTERNATIONAL1},
        {"IntlYen", SDL_SCANCODE_INTERNATIONAL3},
        {"Convert", SDL_SCANCODE_INTERNATIONAL4},
        {"NonConvert", SDL_SCANCODE_INTERNATIONAL5},
        {"KanaMode", SDL_SCANCODE_INTERNATIONAL2},
        {"Lang1", SDL_SCANCODE_LANG1},
        {"Lang2", SDL_SCANCODE_LANG2},
        {"Lang3", SDL_SCANCODE_LANG3},
        {"Lang4", SDL_SCANCODE_LANG4},
        {"Lang5", SDL_SCANCODE_LANG5},
        {"BrowserBack", SDL_SCANCODE_AC_BACK},
    };
    for (const auto &key : keys) {
        if (key.code == code)
            return key.scancode;
    }
    return -1;
}

} // namespace infernux::web
