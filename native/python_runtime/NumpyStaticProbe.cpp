#include <Python.h>

#include <cstdio>

extern "C" int InfernuxRegisterNumPyBuiltins(void);

static constexpr char kNumPyProbeScript[] =
    "import importlib.machinery, sys\n"
    "import numpy as np\n"
    "assert np.__version__ == '2.2.5'\n"
    "assert sys.platform == 'emscripten'\n"
    "assert tuple(sys._emscripten_info.emscripten_version) == (4, 0, 10)\n"
    "assert np._core._multiarray_umath.__loader__ is importlib.machinery.BuiltinImporter\n"
    "a = np.arange(6, dtype=np.float64).reshape(2, 3)\n"
    "b = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])\n"
    "assert np.add(a, 1.0).tolist() == [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]\n"
    "assert (a @ b).tolist() == [[13.0, 16.0], [40.0, 52.0]]\n"
    "print('INFERNUX_WEB_NUMPY_NODE_READY version=2.2.5 abi=cp313 '"
    "      'ndarray=ok ufunc=ok matmul=ok loader=builtin')\n";

int main()
{
    if (InfernuxRegisterNumPyBuiltins() != 0) {
        std::fprintf(stderr, "INFERNUX_WEB_NUMPY_PROBE_REGISTRATION_FAILED\n");
        return 2;
    }
    Py_Initialize();
    const int result = PyRun_SimpleStringFlags(kNumPyProbeScript, nullptr);
    if (result != 0) {
        PyErr_Print();
        return 3;
    }
    if (Py_FinalizeEx() < 0)
        return 4;
    return 0;
}
