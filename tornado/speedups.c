#define PY_SSIZE_T_CLEAN
#include <Python.h>

static PyObject* websocket_mask(PyObject* self, PyObject* args) {
    const char* mask;
    Py_ssize_t mask_len;
    const char* data;
    Py_ssize_t data_len;
    Py_ssize_t i;
    PyObject* result;
    char* buf;

    if (!PyArg_ParseTuple(args, "s#s#", &mask, &mask_len, &data, &data_len)) {
        return NULL;
    }

    result = PyBytes_FromStringAndSize(NULL, data_len);
    if (!result) {
        return NULL;
    }
    buf = PyBytes_AsString(result);
    for (i = 0; i < data_len; i++) {
        buf[i] = data[i] ^ mask[i % 4];
    }

    return result;
}

static PyObject* utf8(PyObject* self, PyObject* args) {
    PyObject* value;

    if (!PyArg_ParseTuple(args, "O", &value)) {
        return NULL;
    }

    if (PyBytes_Check(value) || value == Py_None) {
        Py_INCREF(value);
        return value;
    }

    if (!PyUnicode_Check(value)) {
        PyErr_Format(PyExc_TypeError,
            "Expected bytes, unicode, or None; got %r", PyObject_Type(value));
        return NULL;
    }

    return PyUnicode_AsUTF8String(value);
}

static PyMethodDef methods[] = {
    {"websocket_mask",  websocket_mask, METH_VARARGS, ""},
    {"utf8",  utf8, METH_VARARGS, ""},
    {NULL, NULL, 0, NULL}
};

#if PY_MAJOR_VERSION >= 3
static struct PyModuleDef speedupsmodule = {
   PyModuleDef_HEAD_INIT,
   "speedups",
   NULL,
   -1,
   methods
};

PyMODINIT_FUNC
PyInit_speedups() {
    return PyModule_Create(&speedupsmodule);
}
#else  // Python 2.x
PyMODINIT_FUNC
initspeedups() {
    Py_InitModule("tornado.speedups", methods);
}
#endif
