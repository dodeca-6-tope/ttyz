/*
 * module.c — C extension entry point for ttyz.ext.
 *
 * Unity build: includes every implementation file into a single TU so
 * all `static` helpers can inline across "file" boundaries.  The
 * include order encodes the dependency DAG.
 */

/* Headers: primitives → utilities → codecs. */
#include "core.h"     /* Color, Style, Cell, CellExtra types */
#include "outbuf.h"   /* growable byte buffer */
#include "ansi.h"     /* UTF-8, wcwidth, ANSI scanning */
#include "sgr.h"      /* SGR encode/decode (uses outbuf + ansi) */

/* Implementation: buffer → cells → text → render. */
#include "buffer.c"   /* Buffer type: cells ↔ ANSI */
#include "cells.c"    /* ANSI string → cells primitives */
#include "text.c"     /* line-level transforms (truncate/wrap) */
#include "render.c"   /* node-tree measure + render */

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

    PyObject *m = PyModule_Create(&module_def);
    if (!m) return NULL;

    Py_INCREF(&BufferType);
    if (PyModule_AddObject(m, "Buffer", (PyObject *)&BufferType) < 0) {
        Py_DECREF(&BufferType);
        Py_DECREF(m);
        return NULL;
    }

    return m;
}
