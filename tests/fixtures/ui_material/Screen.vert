ShaderInfo { Name "Screen" Capabilities [ScreenUI] }
#version 450
layout(location=0) in vec2 aPosition;
layout(location=1) in vec2 aUV;
layout(location=2) in vec4 aColor;
layout(push_constant) uniform ScreenUIConstants {
    vec2 scale;
    vec2 translate;
    float encodeSample;
    float _pad0;
    float _pad1;
    float _pad2;
    vec4 materialColor;
    float alphaClipThreshold;
    float alphaClipEnabled;
    vec2 _tailPadding;
} pc;
layout(location=0) out vec4 outColor;
layout(location=1) out vec2 outUV;
void main() {
    gl_Position = vec4(aPosition * pc.scale + pc.translate, 0.0, 1.0);
    outColor = aColor;
    outUV = aUV;
}
