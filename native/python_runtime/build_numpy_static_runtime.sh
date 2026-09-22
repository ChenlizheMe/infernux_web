#!/usr/bin/env bash
set -euo pipefail

CPYTHON_VERSION="3.13.15"
CPYTHON_URL="https://www.python.org/ftp/python/3.13.15/Python-3.13.15.tar.xz"
CPYTHON_SHA256="1e66a7945a48390ee4c2a4268a0e4185884059a13c4aab6d148aa208deea4a76"
NUMPY_VERSION="2.2.5"
NUMPY_URL="https://files.pythonhosted.org/packages/source/n/numpy/numpy-2.2.5.tar.gz"
NUMPY_SHA256="a9c0d994680cd991b1cb772e8b297340085466a6fe964bc9d4e80f5e2f43c291"
EMSCRIPTEN_VERSION="4.0.10"
EMSDK_REVISION="e5bd3d0874e302a18f13c5b41f5bacf9a40c8e59"
CYTHON_VERSION="3.0.12"
CYTHON_URL="https://files.pythonhosted.org/packages/5a/25/886e197c97a4b8e254173002cdc141441e878ff29aaa7d9ba560cd6e4866/cython-3.0.12.tar.gz"
CYTHON_SHA256="b988bb297ce76c671e28c97d017b95411010f7c77fa6623dd0bb47eed1aee1bc"
NINJA_VERSION="1.12.1"
NINJA_REVISION="2daa09ba270b0a43e1929d29b073348aa985dfaa"

usage() {
    echo "Usage: $0 --root ABSOLUTE_NEW_DIR --host-python ABSOLUTE_PYTHON" >&2
}

root=""
host_python=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --root) root="$2"; shift 2 ;;
        --host-python) host_python="$2"; shift 2 ;;
        *) usage; exit 2 ;;
    esac
done
if [[ "$(uname -s)" != "Linux" || -z "$root" || -z "$host_python" ]]; then
    usage
    exit 2
fi
if [[ "$root" != /* || "$host_python" != /* ]]; then
    echo "All input paths must be absolute" >&2
    exit 2
fi
if [[ -e "$root" ]]; then
    echo "Isolated build root must not already exist: $root" >&2
    exit 2
fi
for command in c++ curl git sha256sum; do
    command -v "$command" >/dev/null 2>&1 || { echo "Required command is unavailable: $command" >&2; exit 2; }
done
[[ -x "$host_python" ]] || { echo "Host Python is not executable" >&2; exit 2; }
export MAKEFLAGS="-j2"
export CMAKE_BUILD_PARALLEL_LEVEL="2"
export PYTHONDONTWRITEBYTECODE="1"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
plugin_root="$(cd "$script_dir/../.." && pwd)"
compiler="$script_dir/numpy_static_compiler.py"
packager="$script_dir/prepare_numpy_static_payload.py"
probe_source="$script_dir/NumpyStaticProbe.cpp"
native_payload="$plugin_root/package/editor/infernux_web/native_payload.py"
for source_input in "$compiler" "$packager" "$probe_source" "$native_payload"; do
    [[ -f "$source_input" ]] || {
        echo "Required source-layout input is missing: $source_input" >&2
        exit 2
    }
done
mkdir "$root"
downloads="$root/downloads"
sources="$root/sources"
builds="$root/builds"
records="$root/numpy-link-records"
install_root="$root/numpy-install"
runtime_root="$root/runtime"
mkdir "$downloads" "$sources" "$builds" "$records" "$install_root"

fetch() {
    local url="$1" sha="$2" destination="$3"
    curl --fail --location --proto '=https' --tlsv1.2 --retry 5 --retry-all-errors \
        --output "$destination" "$url"
    echo "$sha  $destination" | sha256sum --check --status || {
        echo "Pinned source hash mismatch: $destination" >&2
        exit 1
    }
}

cpython_archive="$downloads/Python-${CPYTHON_VERSION}.tar.xz"
numpy_archive="$downloads/numpy-${NUMPY_VERSION}.tar.gz"
cython_archive="$downloads/cython-${CYTHON_VERSION}.tar.gz"
fetch "$CPYTHON_URL" "$CPYTHON_SHA256" "$cpython_archive"
fetch "$NUMPY_URL" "$NUMPY_SHA256" "$numpy_archive"
fetch "$CYTHON_URL" "$CYTHON_SHA256" "$cython_archive"
"$host_python" - "$sources" "$cpython_archive" "$numpy_archive" "$cython_archive" <<'PY'
import sys, tarfile
from pathlib import Path
destination = Path(sys.argv[1]).resolve()
for name in sys.argv[2:]:
    with tarfile.open(name) as archive:
        archive.extractall(destination, filter="data")
PY
cython_source="$sources/cython-${CYTHON_VERSION}"
cython="$root/cython"
cat > "$cython" <<EOF
#!/usr/bin/env bash
exec "$host_python" "$cython_source/cython.py" "\$@"
EOF
chmod 0555 "$cython"
[[ "$($cython --version 2>&1)" == "Cython version $CYTHON_VERSION" ]]

ninja_source="$sources/ninja-${NINJA_VERSION}"
git init "$ninja_source"
git -C "$ninja_source" remote add origin https://github.com/ninja-build/ninja.git
git -C "$ninja_source" fetch --depth 1 origin "$NINJA_REVISION"
git -C "$ninja_source" checkout --detach FETCH_HEAD
[[ "$(git -C "$ninja_source" rev-parse HEAD)" == "$NINJA_REVISION" ]]
[[ "$(git -C "$ninja_source" remote get-url origin)" == "https://github.com/ninja-build/ninja.git" ]]
git -C "$ninja_source" fsck --strict
(cd "$ninja_source" && "$host_python" configure.py --bootstrap)
[[ "$($ninja_source/ninja --version)" == "$NINJA_VERSION" ]]
export PATH="$root:$ninja_source:$PATH"
export CYTHON="$cython"
[[ "$(cython --version 2>&1)" == "Cython version $CYTHON_VERSION" ]]

emsdk="$sources/emsdk"
git init "$emsdk"
git -C "$emsdk" remote add origin https://github.com/emscripten-core/emsdk.git
git -C "$emsdk" fetch --depth 1 origin "$EMSDK_REVISION"
git -C "$emsdk" checkout --detach FETCH_HEAD
[[ "$(git -C "$emsdk" rev-parse HEAD)" == "$EMSDK_REVISION" ]]
[[ "$(git -C "$emsdk" remote get-url origin)" == "https://github.com/emscripten-core/emsdk.git" ]]
git -C "$emsdk" fsck --strict
"$emsdk/emsdk" install "$EMSCRIPTEN_VERSION"
"$emsdk/emsdk" activate "$EMSCRIPTEN_VERSION"
export EMSDK_QUIET=1
# shellcheck disable=SC1091
source "$emsdk/emsdk_env.sh"
emscripten_root="$emsdk/upstream/emscripten"
binaryen_root="$emsdk/upstream"
node_path="${EMSDK_NODE:-}"
[[ -x "$node_path" && -x "$binaryen_root/bin/wasm-opt" ]] || {
    echo "Pinned emsdk Node/Binaryen installation is incomplete" >&2
    exit 1
}
em_config="$builds/cpython-emscripten-config.py"
"$host_python" - "$em_config" "$emscripten_root" "$binaryen_root" "$node_path" <<'PY'
import sys
from pathlib import Path

config_path, emscripten_root, binaryen_root, node_path = map(Path, sys.argv[1:])
config_path.write_text(
    f"LLVM_ROOT = {str(binaryen_root / 'bin')!r}\n"
    f"EMSCRIPTEN_ROOT = {str(emscripten_root)!r}\n"
    f"BINARYEN_ROOT = {str(binaryen_root)!r}\n"
    f"NODE_JS = {str(node_path)!r}\n",
    encoding="utf-8",
)
PY
export EM_CONFIG="$em_config"
emcc --version | sed -n '1p' | grep -F " $EMSCRIPTEN_VERSION " >/dev/null
[[ "$(ninja --version)" == "$NINJA_VERSION" ]]

cpython="$sources/Python-${CPYTHON_VERSION}"
printf '\n# Infernux Web is single-threaded.\nac_cv_func_pthread_kill=no\n' \
    >> "$cpython/Tools/wasm/config.site-wasm32-emscripten"
(cd "$cpython" && "$host_python" Tools/wasm/wasm_build.py emscripten-browser)
cpython_build="$cpython/builddir/emscripten-browser"
[[ -f "$cpython_build/libpython3.13.a" && -d "$cpython_build/usr/local" ]]
cpython_host="$cpython/builddir/build/python"
[[ -x "$cpython_host" ]] || { echo "Pinned CPython build interpreter is missing" >&2; exit 1; }
[[ "$("$cpython_host" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')" == "$CPYTHON_VERSION" ]] || {
    echo "Pinned CPython build interpreter has the wrong version" >&2
    exit 1
}
target_sysconfig_dir="$cpython_build/build/lib.emscripten-wasm32-3.13"
mapfile -t target_sysconfig_files < <(
    find "$target_sysconfig_dir" -maxdepth 1 -type f \
        -name '_sysconfigdata__emscripten_wasm32-emscripten.py' -print
)
if [[ "${#target_sysconfig_files[@]}" -ne 1 ]]; then
    echo "Expected exactly one pinned Emscripten sysconfigdata module" >&2
    exit 1
fi
target_sysconfig="${target_sysconfig_files[0]}"
target_sysconfig_name="$(basename "$target_sysconfig" .py)"
cross_python="$root/cross-python"
cat > "$cross_python" <<EOF
#!/usr/bin/env bash
set -euo pipefail
unset PYTHONHOME PYTHONPATH
export _PYTHON_PROJECT_BASE='$cpython_build'
export _PYTHON_HOST_PLATFORM='emscripten-wasm32'
export _PYTHON_SYSCONFIGDATA_NAME='$target_sysconfig_name'
export _PYTHON_SYSCONFIGDATA_PATH='$target_sysconfig_dir'
exec '$cpython_host' "\$@"
EOF
chmod 0555 "$cross_python"

numpy="$sources/numpy-${NUMPY_VERSION}"
meson="$numpy/vendored-meson/meson/meson.py"
meson_python_info="$numpy/vendored-meson/meson/mesonbuild/scripts/python_info.py"
cross_python_info="$builds/cross-python-info.json"
"$cross_python" "$meson_python_info" > "$cross_python_info"
"$host_python" - "$cross_python_info" "$cpython/Include" "$cpython_build" <<'PY'
import json
import sys
from pathlib import Path

document = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
variables = document.get("variables", {})
expected = {
    "version": "3.13",
    "platform": "emscripten-wasm32",
    "suffix": ".cpython-313-wasm32-emscripten.so",
    "link_libpython": False,
}
for key, value in expected.items():
    if document.get(key) != value:
        raise SystemExit(f"cross Python probe mismatch for {key}: {document.get(key)!r}")
variable_expected = {
    "py_version": "3.13.15",
    "SOABI": "cpython-313-wasm32-emscripten",
    "EXT_SUFFIX": ".cpython-313-wasm32-emscripten.so",
    "MULTIARCH": "wasm32-emscripten",
    "SIZEOF_VOID_P": 4,
}
for key, value in variable_expected.items():
    if variables.get(key) != value:
        raise SystemExit(f"target sysconfig mismatch for {key}: {variables.get(key)!r}")
paths = document.get("paths", {})
if Path(paths.get("include", "")).resolve() != Path(sys.argv[2]).resolve():
    raise SystemExit("cross Python probe did not select the pinned CPython headers")
if Path(paths.get("platinclude", "")).resolve() != Path(sys.argv[3]).resolve():
    raise SystemExit("cross Python probe did not select the pinned target pyconfig.h")
PY
"$host_python" - "$builds/cross-python-provenance.json" \
    "$cpython_host" "$target_sysconfig" "$cross_python" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

output = Path(sys.argv[1])
records = {}
for label, value in zip(("host_interpreter", "target_sysconfig", "wrapper"), sys.argv[2:]):
    path = Path(value).resolve()
    records[label] = {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
    }
output.write_text(
    json.dumps({"schema": "infernux.numpy_cross_python.v1", "files": records}, sort_keys=True, indent=2) + "\n",
    encoding="utf-8",
)
PY

cross="$builds/numpy-emscripten-static.cross"
cat > "$cross" <<EOF
[binaries]
c = ['$host_python', '$compiler', '--driver', '$emsdk/upstream/emscripten/emcc', '--archiver', '$emsdk/upstream/emscripten/emar', '--record-dir', '$records', '--']
cpp = ['$host_python', '$compiler', '--driver', '$emsdk/upstream/emscripten/em++', '--archiver', '$emsdk/upstream/emscripten/emar', '--record-dir', '$records', '--']
cython = '$cython'
python = '$cross_python'
exe_wrapper = '$node_path'
pkgconfig = 'pkg-config'

[properties]
needs_exe_wrapper = true
skip_sanity_check = true
longdouble_format = 'IEEE_QUAD_LE'

[host_machine]
system = 'emscripten'
cpu_family = 'wasm32'
cpu = 'wasm'
endian = 'little'
EOF

numpy_build="$builds/numpy"
"$host_python" "$meson" setup "$numpy_build" "$numpy" \
    --cross-file "$cross" --buildtype release \
    -Dblas=none -Dlapack=none -Dallow-noblas=true \
    -Ddisable-threading=true -Ddisable-optimization=true
"$host_python" "$meson" compile -C "$numpy_build" -j 2
DESTDIR="$install_root" "$host_python" "$meson" install -C "$numpy_build" \
    --tags runtime,python-runtime
"$host_python" "$packager" \
    --install-root "$install_root" --record-dir "$records" \
    --numpy-build-root "$numpy_build" --cpython-build-root "$cpython_build" \
    --output-root "$runtime_root" \
    --archiver "$emsdk/upstream/emscripten/emar"
"$host_python" "$native_payload" \
    --verify-python-package-payload "$runtime_root/payload" \
    --runtime-manifest "$runtime_root/runtime-manifest.json" --package numpy

"$host_python" - "$runtime_root/payload/numpy_static_link.json" "$runtime_root/numpy-link.rsp" <<'PY'
import json, sys
from pathlib import Path
manifest, output = map(Path, sys.argv[1:])
document = json.loads(manifest.read_text(encoding="utf-8"))
root = manifest.parent
output.write_text("\n".join(str(root / item) for item in document["archives"]) + "\n", encoding="utf-8")
PY

probe="$runtime_root/numpy-node-probe.js"
em++ "$probe_source" "$runtime_root/payload/numpy_builtin_registry.c" \
    -I "$cpython/Include" -I "$cpython_build" \
    "$cpython_build/libpython3.13.a" \
    "$cpython_build/Modules/expat/libexpat.a" \
    "$cpython_build/Modules/_decimal/libmpdec/libmpdec.a" \
    "$cpython_build/Modules/_hacl/libHacl_Hash_SHA2.a" \
    -Wl,--start-group @"$runtime_root/numpy-link.rsp" -Wl,--end-group \
    -sUSE_ZLIB=1 -sUSE_BZIP2=1 -sUSE_SQLITE3=1 -sFORCE_FILESYSTEM=1 \
    -sALLOW_MEMORY_GROWTH=1 -sENVIRONMENT=node -sEXIT_RUNTIME=1 \
    --preload-file "$cpython_build/usr/local@/usr/local" \
    --preload-file "$runtime_root/payload/site-packages@/usr/local/lib/python3.13/site-packages" \
    -o "$probe"
(cd "$runtime_root" && "$node_path" "$(basename "$probe")") | tee "$runtime_root/numpy-node-probe.log"
grep -Fx "INFERNUX_WEB_NUMPY_NODE_READY version=2.2.5 abi=cp313 ndarray=ok ufunc=ok matmul=ok loader=builtin" \
    "$runtime_root/numpy-node-probe.log"
if find "$runtime_root/payload" -type f \( -name '*.so' -o -name '*.wasm' \) | grep -q .; then
    echo "Dynamic modules are forbidden in the NumPy payload" >&2
    exit 1
fi
echo "NumPy static-built-in runtime ready: $runtime_root"
