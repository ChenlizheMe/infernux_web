# Web NumPy static runtime

`build_numpy_static_runtime.sh` builds the Web Player numerical runtime from the
official NumPy 2.2.5 source distribution. It pins CPython 3.13.15, Emscripten
4.0.10, the emsdk Git revision, and the build-only Cython 3.0.12 source. It does
not consume Pyodide wheels or dynamic Emscripten side modules. The host Ninja
executable is bootstrapped from the official Ninja 1.12.1 Git revision because
the pinned emsdk does not bundle Ninja. The builder also writes an isolated
`EM_CONFIG` containing only the pinned emsdk LLVM/Binaryen/Emscripten paths and
its pinned Node executable; it never consumes a user-level Emscripten config.

NumPy's Meson build needs one Python identity with two deliberate properties:
it must execute natively for build-time code generation while reporting the
target CPython ABI to `python.dependency()`. After CPython's cross build, the
builder therefore creates an isolated wrapper around the same-source native
CPython 3.13.15 build interpreter and injects only CPython's generated
Emscripten sysconfigdata through `_PYTHON_SYSCONFIGDATA_PATH`. The wrapper
clears `PYTHONHOME` and `PYTHONPATH`, and Meson's own `python_info.py` must
report the exact wasm platform, SOABI, extension suffix, pointer size, and
header directories before NumPy configuration starts. Its interpreter,
sysconfigdata, and wrapper identities are recorded in
`builds/cross-python-provenance.json`.

The target `python.js` is intentionally not the Meson Python program. Meson
1.5.2 treats the first item of a cross-file Python command array as the Python
executable, so a `[node, python.js]` entry probes Node alone. More importantly,
the wasm interpreter cannot serve as the native interpreter for NumPy's host
code generators. The cross file consequently names the generated native
wrapper as one executable path; no native file or dynamic-module fallback is
used.

The build root must be a new absolute directory on Linux:

```sh
build_numpy_static_runtime.sh \
  --root /home/x2l20/acceptance/web-python-cp313-em4010-numpy225 \
  --host-python /usr/bin/python3.12
```

The builder must remain at `native/python_runtime` inside the plugin source
tree. Before creating the build root or downloading anything, it requires its
compiler shim, payload packager, Node probe, and
`package/editor/infernux_web/native_payload.py` at their canonical relative
paths. A flattened upload is rejected immediately.
The build environment also sets `PYTHONDONTWRITEBYTECODE=1`, so importing the
payload verifier cannot mutate the audited source staging tree.

The builder converts NumPy extension link steps into deterministic archives,
requires the exact 13-module runtime closure, generates CPython built-in module
registration, and writes `runtime/runtime-manifest.json` beside the hashed
`runtime/payload` tree. A successful build ends by running a real Node-hosted
wasm probe for import, ndarray construction, a ufunc, matrix multiplication,
and `BuiltinImporter` identity. Any `.so` or `.wasm` file inside the package
payload is a hard failure.

The Web Player build consumes the result with explicit inputs:

```text
INFERNUX_WEB_HOST_PYTHON=/absolute/host/python
INFERNUX_WEB_NUMPY_PAYLOAD_ROOT=/.../runtime/payload
INFERNUX_WEB_PYTHON_RUNTIME_MANIFEST=/.../runtime/runtime-manifest.json
```

CMake recomputes the payload hash, byte count, and file count at configure time
and again on every build before linking or preloading it.
