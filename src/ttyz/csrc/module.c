/*
 * module.c — C extension entry point for ttyz.ext.
 *
 * Single compilation unit: includes the split source files and
 * registers all types and functions into the Python module.
 */

#include "core.h"
#include "buffer.c"
#include "text.c"
#include "render.c"

/* ── Module definition ─────────────────────────────────────────────── */

static PyMethodDef module_methods[] = {
    {"render_to_buffer", mod_render_to_buffer, METH_VARARGS, "Render node tree directly into buffer cells."},
    {NULL}
};

static struct PyModuleDef module_def = {
    PyModuleDef_HEAD_INIT,
    .m_name    = "ttyz.ext",
    .m_doc     = "C-accelerated terminal rendering primitives.",
    .m_size    = -1,
    .m_methods = module_methods,
};

PyMODINIT_FUNC PyInit_ext(void) {
    if (PyType_Ready(&BufferType) < 0)
        return NULL;
    if (PyType_Ready(&CTextRenderType) < 0)
        return NULL;

    PyObject *m = PyModule_Create(&module_def);
    if (!m) return NULL;

    Py_INCREF(&BufferType);
    if (PyModule_AddObject(m, "Buffer", (PyObject *)&BufferType) < 0) {
        Py_DECREF(&BufferType);
        Py_DECREF(m);
        return NULL;
    }

    Py_INCREF(&CTextRenderType);
    if (PyModule_AddObject(m, "TextRender", (PyObject *)&CTextRenderType) < 0) {
        Py_DECREF(&CTextRenderType);
        Py_DECREF(m);
        return NULL;
    }

    return m;
}
