#ifndef Py_INTERNAL_INTERPOLATION_H
#define Py_INTERNAL_INTERPOLATION_H

#ifdef __cplusplus
extern "C" {
#endif

#ifndef Py_BUILD_CORE
#  error "this header requires Py_BUILD_CORE define"
#endif

extern PyTypeObject _PyInterpolation_Type;

/* Conversion codes encoded in BUILD_INTERPOLATION's oparg. */
#define _Py_TSTRING_CONVERSION_NONE   0
#define _Py_TSTRING_CONVERSION_STR    1
#define _Py_TSTRING_CONVERSION_REPR   2
#define _Py_TSTRING_CONVERSION_ASCII  3
#define _Py_TSTRING_CONVERSION_PRETTY 4

#define _PyInterpolation_CheckExact(op) Py_IS_TYPE((op), &_PyInterpolation_Type)

PyAPI_FUNC(PyObject *) _PyInterpolation_Build(PyObject *value, PyObject *str,
                                              int conversion, PyObject *format_spec);

extern PyStatus _PyInterpolation_InitTypes(PyInterpreterState *interp);
extern PyObject *_PyInterpolation_GetValueRef(PyObject *interpolation);

#ifdef __cplusplus
}
#endif

#endif
