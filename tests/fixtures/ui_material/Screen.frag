ShaderInfo { Name "Screen" Capabilities [ScreenUI] }
#version 450
layout(location=0) in vec4 inColor;
layout(location=1) in vec2 inUV;
layout(set=0,binding=0) uniform sampler2D uiTexture;
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
void main() {
    outColor = texture(uiTexture, inUV) * inColor * pc.materialColor * vec4(1.0, 0.1, 0.9, 1.0);
    if (pc.alphaClipEnabled > 0.5 && outColor.a < pc.alphaClipThreshold)
        discard;
}
