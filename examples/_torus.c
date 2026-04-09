/*
 * _torus — C-accelerated 3D torus renderer for the stress test.
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <math.h>

static const char SHADE[] = ".,-~:;=!*#$@";
static const int COLORS[] = {
    53,54,55,56,57,93,92,91,90,89,125,161,197,203,209,215,221,227,191,155,119
};
#define N_SHADE  ((int)(sizeof(SHADE) - 1))
#define N_COLORS ((int)(sizeof(COLORS) / sizeof(COLORS[0])))

static PyObject *render_torus(PyObject *self, PyObject *args) {
    double a, b;
    int width, height;
    if (!PyArg_ParseTuple(args, "ddii", &a, &b, &width, &height))
        return NULL;

    const double R1 = 1.0, R2 = 2.0, K2 = 5.0;
    double k1 = width * K2 * 0.4 / (R1 + R2);
    double cos_a = cos(a), sin_a = sin(a);
    double cos_b = cos(b), sin_b = sin(b);
    double half_w = width * 0.5, half_h = height * 0.5;

    int total = width * height;
    char *shade   = (char *)calloc(total, 1);
    int  *color   = (int *)calloc(total, sizeof(int));
    double *zbuf  = (double *)calloc(total, sizeof(double));
    if (!shade || !color || !zbuf) {
        free(shade); free(color); free(zbuf);
        return PyErr_NoMemory();
    }

    for (int ti = 0; ti < 90; ti++) {
        double theta = ti * 0.07;
        double cos_t = cos(theta), sin_t = sin(theta);
        double cx = R2 + R1 * cos_t;
        double cy = R1 * sin_t;

        for (int pi = 0; pi < 157; pi++) {
            double phi = pi * 0.04;
            double cos_p = cos(phi), sin_p = sin(phi);
            double x = cx * (cos_b * cos_p + sin_a * sin_b * sin_p) - cy * cos_a * sin_b;
            double y = cx * (sin_b * cos_p - sin_a * cos_b * sin_p) + cy * cos_a * cos_b;
            double z = K2 + cos_a * cx * sin_p + cy * sin_a;
            double ooz = 1.0 / z;
            int xp = (int)(half_w + k1 * ooz * x);
            int yp = (int)(half_h - k1 * ooz * y * 0.5);

            if (xp >= 0 && xp < width && yp >= 0 && yp < height) {
                int idx = yp * width + xp;
                if (ooz > zbuf[idx]) {
                    zbuf[idx] = ooz;
                    double lum = cos_p * cos_t * sin_b - cos_a * cos_t * sin_p
                                 - sin_a * sin_t
                                 + cos_b * (cos_a * sin_t - cos_t * sin_a * sin_p);
                    int li = (int)(lum * 8);
                    if (li < 0) li = 0;
                    if (li > N_SHADE - 1) li = N_SHADE - 1;
                    int ci = (int)((lum + 1.0) * 0.5 * (N_COLORS - 1));
                    if (ci < 0) ci = 0;
                    if (ci > N_COLORS - 1) ci = N_COLORS - 1;
                    shade[idx] = SHADE[li];
                    color[idx] = COLORS[ci];
                }
            }
        }
    }

    PyObject *result = PyList_New(height);
    if (!result) { free(shade); free(color); free(zbuf); return NULL; }

    for (int row = 0; row < height; row++) {
        /* Worst case per cell: "\033[38;5;255m.\033[0m" = ~18 bytes */
        size_t cap = (size_t)width * 20;
        char *buf = (char *)malloc(cap);
        if (!buf) {
            free(shade); free(color); free(zbuf);
            Py_DECREF(result);
            return PyErr_NoMemory();
        }
        size_t len = 0;
        int off = row * width;
        for (int col = 0; col < width; col++) {
            char ch = shade[off + col];
            if (ch == 0) {
                buf[len++] = ' ';
            } else {
                len += snprintf(buf + len, cap - len, "\033[38;5;%dm%c\033[0m",
                                color[off + col], ch);
            }
        }
        PyObject *line = PyUnicode_DecodeUTF8(buf, (Py_ssize_t)len, NULL);
        free(buf);
        if (!line) {
            free(shade); free(color); free(zbuf);
            Py_DECREF(result);
            return NULL;
        }
        PyList_SET_ITEM(result, row, line);
    }

    free(shade);
    free(color);
    free(zbuf);
    return result;
}

static PyMethodDef methods[] = {
    {"render_torus", render_torus, METH_VARARGS, "Render 3D torus to ANSI lines."},
    {NULL}
};

static struct PyModuleDef module_def = {
    PyModuleDef_HEAD_INIT,
    .m_name = "_torus",
    .m_size = -1,
    .m_methods = methods,
};

PyMODINIT_FUNC PyInit__torus(void) {
    return PyModule_Create(&module_def);
}
