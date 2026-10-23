/* C support for the PEP 813 pretty-print protocol. */

#ifndef Py_BUILD_CORE_BUILTIN
#  define Py_BUILD_CORE_MODULE 1
#endif
#include "Python.h"

typedef struct {
    PyObject_HEAD
    PyObject *hints;
    PyObject *name;
    PyObject *open;
    PyObject *close;
    PyObject *sep;
    PyObject *empty;
    PyObject *single_close;
    PyObject *recursion;
    PyObject *sortable;
    PyObject *hug;
} LayoutObject;

typedef struct {
    PyObject_HEAD
    PyObject *value;
} BreakableObject;

typedef struct {
    PyObject *layout_type;
    PyObject *leaf_marker_type;
    PyObject *breakable_string_type;
    PyObject *breakable_bytes_type;
    PyObject *formattable_number_type;
    PyObject *values;
    PyObject *kwargs;
    PyObject *items;
    PyObject *delegate;
    PyObject *namespace_type;
} pprint_state;

#define LayoutObject_CAST(op) ((LayoutObject *)(op))
#define BreakableObject_CAST(op) ((BreakableObject *)(op))

static int
layout_traverse(PyObject *op, visitproc visit, void *arg)
{
    LayoutObject *self = LayoutObject_CAST(op);
    Py_VISIT(self->hints);
    Py_VISIT(self->name);
    Py_VISIT(self->open);
    Py_VISIT(self->close);
    Py_VISIT(self->sep);
    Py_VISIT(self->empty);
    Py_VISIT(self->single_close);
    Py_VISIT(self->recursion);
    Py_VISIT(self->sortable);
    Py_VISIT(self->hug);
    return 0;
}

static int
layout_clear(PyObject *op)
{
    LayoutObject *self = LayoutObject_CAST(op);
    Py_CLEAR(self->hints);
    Py_CLEAR(self->name);
    Py_CLEAR(self->open);
    Py_CLEAR(self->close);
    Py_CLEAR(self->sep);
    Py_CLEAR(self->empty);
    Py_CLEAR(self->single_close);
    Py_CLEAR(self->recursion);
    Py_CLEAR(self->sortable);
    Py_CLEAR(self->hug);
    return 0;
}

static void
layout_dealloc(PyObject *op)
{
    PyTypeObject *type = Py_TYPE(op);
    PyObject_GC_UnTrack(op);
    (void)layout_clear(op);
    type->tp_free(op);
    Py_DECREF(type);
}

static int
layout_init(PyObject *op, PyObject *args, PyObject *kwargs)
{
    LayoutObject *self = LayoutObject_CAST(op);
    static char *kwlist[] = {
        "hints", "name", "open", "close", "sep", "empty",
        "single_close", "recursion", "sortable", "hug", NULL
    };
    PyObject *hints = NULL, *name = Py_None, *open = Py_None;
    PyObject *close = Py_None, *sep = NULL, *empty = Py_None;
    PyObject *single_close = Py_None, *recursion = NULL;
    PyObject *sortable = Py_False, *hug = Py_False;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|$OOOOOOOOOO:Layout",
                                     kwlist, &hints, &name, &open, &close,
                                     &sep, &empty, &single_close, &recursion,
                                     &sortable, &hug)) {
        return -1;
    }
    if (hints == NULL) {
        PyObject *dict = PyDict_New();
        if (dict == NULL) {
            return -1;
        }
        hints = PyDictProxy_New(dict);
        Py_DECREF(dict);
        if (hints == NULL) {
            return -1;
        }
    }
    else {
        Py_INCREF(hints);
    }
    if (sep == NULL) {
        sep = PyUnicode_FromString(",");
        if (sep == NULL) {
            Py_DECREF(hints);
            return -1;
        }
    }
    else {
        Py_INCREF(sep);
    }
    if (recursion == NULL) {
        recursion = PyUnicode_FromString("...");
        if (recursion == NULL) {
            Py_DECREF(hints);
            Py_DECREF(sep);
            return -1;
        }
    }
    else {
        Py_INCREF(recursion);
    }

    PyObject *values[] = {hints, name, open, close, sep, empty,
                          single_close, recursion, sortable, hug};
    PyObject **fields[] = {&self->hints, &self->name, &self->open,
                           &self->close, &self->sep, &self->empty,
                           &self->single_close, &self->recursion,
                           &self->sortable, &self->hug};
    for (size_t i = 0; i < Py_ARRAY_LENGTH(values); i++) {
        Py_INCREF(values[i]);
        Py_XSETREF(*fields[i], values[i]);
    }
    Py_DECREF(hints);
    Py_DECREF(sep);
    Py_DECREF(recursion);
    return 0;
}

static PyObject *
layout_get_hints(PyObject *op, void *closure)
{
    return Py_NewRef(LayoutObject_CAST(op)->hints);
}

#define LAYOUT_GETTER(name) \
static PyObject *layout_get_##name(PyObject *op, void *closure) \
{ return Py_NewRef(LayoutObject_CAST(op)->name); }
LAYOUT_GETTER(name)
LAYOUT_GETTER(open)
LAYOUT_GETTER(close)
LAYOUT_GETTER(sep)
LAYOUT_GETTER(empty)
LAYOUT_GETTER(single_close)
LAYOUT_GETTER(recursion)
LAYOUT_GETTER(sortable)
LAYOUT_GETTER(hug)

static PyGetSetDef layout_getset[] = {
    {"hints", layout_get_hints, NULL, NULL, NULL},
    {"name", layout_get_name, NULL, NULL, NULL},
    {"open", layout_get_open, NULL, NULL, NULL},
    {"close", layout_get_close, NULL, NULL, NULL},
    {"sep", layout_get_sep, NULL, NULL, NULL},
    {"empty", layout_get_empty, NULL, NULL, NULL},
    {"single_close", layout_get_single_close, NULL, NULL, NULL},
    {"recursion", layout_get_recursion, NULL, NULL, NULL},
    {"sortable", layout_get_sortable, NULL, NULL, NULL},
    {"hug", layout_get_hug, NULL, NULL, NULL},
    {NULL}
};

static PyObject *
layout_repr(PyObject *op)
{
    LayoutObject *self = LayoutObject_CAST(op);
    PyObject *parts = PyList_New(0);
    if (parts == NULL) {
        return NULL;
    }
    static const char *names[] = {
        "hints", "name", "open", "close", "sep", "empty",
        "single_close", "recursion", "sortable", "hug"
    };
    PyObject **values[] = {
        &self->hints, &self->name, &self->open, &self->close, &self->sep,
        &self->empty, &self->single_close, &self->recursion,
        &self->sortable, &self->hug
    };
    for (size_t i = 0; i < Py_ARRAY_LENGTH(names); i++) {
        PyObject *part = PyUnicode_FromFormat("%s=%R", names[i], *values[i]);
        if (part == NULL || PyList_Append(parts, part) < 0) {
            Py_XDECREF(part);
            Py_DECREF(parts);
            return NULL;
        }
        Py_DECREF(part);
    }
    PyObject *sep = PyUnicode_FromString(", ");
    PyObject *body = sep == NULL ? NULL : PyUnicode_Join(sep, parts);
    Py_XDECREF(sep);
    Py_DECREF(parts);
    if (body == NULL) {
        return NULL;
    }
    PyObject *qualname = PyObject_GetAttrString((PyObject *)Py_TYPE(op),
                                                "__qualname__");
    PyObject *result = qualname == NULL ? NULL :
        PyUnicode_FromFormat("%U(%U)", qualname, body);
    Py_XDECREF(qualname);
    Py_DECREF(body);
    return result;
}

static PyObject *
layout_richcompare(PyObject *left, PyObject *right, int op)
{
    if (Py_TYPE(left) != Py_TYPE(right) ||
        (op != Py_EQ && op != Py_NE)) {
        Py_RETURN_NOTIMPLEMENTED;
    }
    LayoutObject *a = LayoutObject_CAST(left);
    LayoutObject *b = LayoutObject_CAST(right);
    PyObject **av[] = {&a->hints,&a->name,&a->open,&a->close,&a->sep,&a->empty,
                       &a->single_close,&a->recursion,&a->sortable,&a->hug};
    PyObject **bv[] = {&b->hints,&b->name,&b->open,&b->close,&b->sep,&b->empty,
                       &b->single_close,&b->recursion,&b->sortable,&b->hug};
    int equal = 1;
    for (size_t i = 0; i < Py_ARRAY_LENGTH(av); i++) {
        int same = PyObject_RichCompareBool(*av[i], *bv[i], Py_EQ);
        if (same < 0) {
            return NULL;
        }
        if (!same) {
            equal = 0;
            break;
        }
    }
    return PyBool_FromLong(op == Py_EQ ? equal : !equal);
}

static Py_hash_t
layout_hash(PyObject *op)
{
    LayoutObject *self = LayoutObject_CAST(op);
    PyObject *tuple = PyTuple_Pack(10, self->hints, self->name, self->open,
        self->close, self->sep, self->empty, self->single_close,
        self->recursion, self->sortable, self->hug);
    if (tuple == NULL) {
        return -1;
    }
    Py_hash_t result = PyObject_Hash(tuple);
    Py_DECREF(tuple);
    return result;
}

static PyType_Slot layout_slots[] = {
    {Py_tp_dealloc, layout_dealloc},
    {Py_tp_traverse, layout_traverse},
    {Py_tp_clear, layout_clear},
    {Py_tp_init, layout_init},
    {Py_tp_new, PyType_GenericNew},
    {Py_tp_getset, layout_getset},
    {Py_tp_repr, layout_repr},
    {Py_tp_richcompare, layout_richcompare},
    {Py_tp_hash, layout_hash},
    {0, NULL}
};

static PyType_Spec layout_spec = {
    .name = "_pprint.Layout",
    .basicsize = sizeof(LayoutObject),
    .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC | Py_TPFLAGS_BASETYPE,
    .slots = layout_slots,
};

static int
breakable_traverse(PyObject *op, visitproc visit, void *arg)
{
    Py_VISIT(BreakableObject_CAST(op)->value);
    return 0;
}

static int
breakable_clear(PyObject *op)
{
    Py_CLEAR(BreakableObject_CAST(op)->value);
    return 0;
}

static void
breakable_dealloc(PyObject *op)
{
    PyTypeObject *type = Py_TYPE(op);
    PyObject_GC_UnTrack(op);
    (void)breakable_clear(op);
    type->tp_free(op);
    Py_DECREF(type);
}

static int
breakable_init(PyObject *op, PyObject *args, PyObject *kwargs)
{
    static char *kwlist[] = {"value", NULL};
    PyObject *value;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O:Breakable", kwlist,
                                     &value)) {
        return -1;
    }
    Py_INCREF(value);
    Py_XSETREF(BreakableObject_CAST(op)->value, value);
    return 0;
}

static PyObject *
breakable_get_value(PyObject *op, void *closure)
{
    return Py_NewRef(BreakableObject_CAST(op)->value);
}

static PyGetSetDef breakable_getset[] = {
    {"value", breakable_get_value, NULL, NULL, NULL},
    {NULL}
};

static PyObject *
leaf_marker_repr(PyObject *op)
{
    PyObject *value = PyObject_GetAttrString(op, "value");
    if (value == NULL) {
        return NULL;
    }
    PyObject *qualname = PyObject_GetAttrString((PyObject *)Py_TYPE(op),
                                                "__qualname__");
    if (qualname == NULL) {
        Py_DECREF(value);
        return NULL;
    }
    PyObject *result = PyUnicode_FromFormat("%U(%R)", qualname, value);
    Py_DECREF(qualname);
    Py_DECREF(value);
    return result;
}

static PyType_Slot leaf_marker_slots[] = {
    {Py_tp_repr, leaf_marker_repr},
    {Py_tp_new, PyType_GenericNew},
    {0, NULL}
};

static PyType_Spec leaf_marker_spec = {
    .name = "_pprint._LeafMarker",
    .basicsize = sizeof(PyObject),
    .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .slots = leaf_marker_slots,
};

static PyObject *
breakable_richcompare(PyObject *left, PyObject *right, int op)
{
    if (Py_TYPE(left) != Py_TYPE(right) ||
        (op != Py_EQ && op != Py_NE)) {
        Py_RETURN_NOTIMPLEMENTED;
    }
    int equal = PyObject_RichCompareBool(BreakableObject_CAST(left)->value,
                                         BreakableObject_CAST(right)->value,
                                         Py_EQ);
    if (equal < 0) {
        return NULL;
    }
    return PyBool_FromLong(op == Py_EQ ? equal : !equal);
}

static Py_hash_t
breakable_hash(PyObject *op)
{
    PyObject *tuple = PyTuple_Pack(1, BreakableObject_CAST(op)->value);
    if (tuple == NULL) {
        return -1;
    }
    Py_hash_t result = PyObject_Hash(tuple);
    Py_DECREF(tuple);
    return result;
}

static PyType_Slot breakable_slots[] = {
    {Py_tp_dealloc, breakable_dealloc},
    {Py_tp_traverse, breakable_traverse},
    {Py_tp_clear, breakable_clear},
    {Py_tp_init, breakable_init},
    {Py_tp_new, PyType_GenericNew},
    {Py_tp_getset, breakable_getset},
    {Py_tp_richcompare, breakable_richcompare},
    {Py_tp_hash, breakable_hash},
    {0, NULL}
};

static PyType_Spec breakable_string_spec = {
    .name = "_pprint.BreakableString",
    .basicsize = sizeof(BreakableObject),
    .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC | Py_TPFLAGS_BASETYPE,
    .slots = breakable_slots,
};

static PyType_Spec breakable_bytes_spec = {
    .name = "_pprint.BreakableBytes",
    .basicsize = sizeof(BreakableObject),
    .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC | Py_TPFLAGS_BASETYPE,
    .slots = breakable_slots,
};

static PyType_Spec formattable_number_spec = {
    .name = "_pprint.FormattableNumber",
    .basicsize = sizeof(BreakableObject),
    .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC | Py_TPFLAGS_BASETYPE,
    .slots = breakable_slots,
};

static int
pprint_traverse(PyObject *module, visitproc visit, void *arg)
{
    pprint_state *state = PyModule_GetState(module);
    Py_VISIT(state->layout_type);
    Py_VISIT(state->leaf_marker_type);
    Py_VISIT(state->breakable_string_type);
    Py_VISIT(state->breakable_bytes_type);
    Py_VISIT(state->formattable_number_type);
    Py_VISIT(state->values);
    Py_VISIT(state->kwargs);
    Py_VISIT(state->items);
    Py_VISIT(state->delegate);
    Py_VISIT(state->namespace_type);
    return 0;
}

static int
pprint_clear(PyObject *module)
{
    pprint_state *state = PyModule_GetState(module);
    Py_CLEAR(state->layout_type);
    Py_CLEAR(state->leaf_marker_type);
    Py_CLEAR(state->breakable_string_type);
    Py_CLEAR(state->breakable_bytes_type);
    Py_CLEAR(state->formattable_number_type);
    Py_CLEAR(state->values);
    Py_CLEAR(state->kwargs);
    Py_CLEAR(state->items);
    Py_CLEAR(state->delegate);
    Py_CLEAR(state->namespace_type);
    return 0;
}

static PyObject *
type_name(PyObject *obj)
{
    return PyObject_GetAttrString((PyObject *)Py_TYPE(obj), "__name__");
}

static int
dict_set_string(PyObject *dict, const char *key, const char *value)
{
    if (value == NULL) {
        return 0;
    }
    PyObject *obj = PyUnicode_FromString(value);
    if (obj == NULL) {
        return -1;
    }
    int result = PyDict_SetItemString(dict, key, obj);
    Py_DECREF(obj);
    return result;
}

static int
dict_set_obj(PyObject *dict, const char *key, PyObject *value)
{
    return value == NULL ? 0 : PyDict_SetItemString(dict, key, value);
}

static int
dict_set_true(PyObject *dict, const char *key, int value)
{
    return value ? PyDict_SetItemString(dict, key, Py_True) : 0;
}

static PyObject *
new_layout(pprint_state *state, const char *open, const char *close,
           const char *empty, const char *single_close,
           const char *sep, const char *recursion, int sortable, int hug,
           PyObject *dynamic_open, PyObject *dynamic_close,
           PyObject *dynamic_empty)
{
    PyObject *kwargs = PyDict_New();
    if (kwargs == NULL) {
        return NULL;
    }
    int ok = dict_set_string(kwargs, "open", open) == 0 &&
        dict_set_string(kwargs, "close", close) == 0 &&
        dict_set_string(kwargs, "empty", empty) == 0 &&
        dict_set_string(kwargs, "single_close", single_close) == 0 &&
        dict_set_string(kwargs, "sep", sep) == 0 &&
        dict_set_string(kwargs, "recursion", recursion) == 0 &&
        dict_set_true(kwargs, "sortable", sortable) == 0 &&
        dict_set_true(kwargs, "hug", hug) == 0 &&
        dict_set_obj(kwargs, "open", dynamic_open) == 0 &&
        dict_set_obj(kwargs, "close", dynamic_close) == 0 &&
        dict_set_obj(kwargs, "empty", dynamic_empty) == 0;
    PyObject *result = NULL;
    if (ok) {
        PyObject *args = PyTuple_New(0);
        if (args != NULL) {
            result = PyObject_Call(state->layout_type, args, kwargs);
            Py_DECREF(args);
        }
    }
    Py_DECREF(kwargs);
    return result;
}

static PyObject *
stream_new(void)
{
    return PyList_New(0);
}

static int
stream_append(PyObject *stream, PyObject *value)
{
    return PyList_Append(stream, value);
}

static int
stream_append_new(PyObject *stream, PyObject *value)
{
    if (value == NULL) {
        return -1;
    }
    int result = PyList_Append(stream, value);
    Py_DECREF(value);
    return result;
}

static int
stream_append_iter(PyObject *stream, PyObject *iterable)
{
    PyObject *it = PyObject_GetIter(iterable);
    if (it == NULL) {
        return -1;
    }
    PyObject *item;
    while ((item = PyIter_Next(it)) != NULL) {
        int result = PyList_Append(stream, item);
        Py_DECREF(item);
        if (result < 0) {
            Py_DECREF(it);
            return -1;
        }
    }
    Py_DECREF(it);
    return PyErr_Occurred() ? -1 : 0;
}

static PyObject *
stream_finish(PyObject *stream)
{
    if (stream == NULL) {
        return NULL;
    }
    PyObject *result = PyList_AsTuple(stream);
    Py_DECREF(stream);
    return result;
}

static int
stream_start(PyObject *stream, PyObject *layout)
{
    return stream_append_new(stream, layout);
}

static int
stream_add_marker(PyObject *stream, PyObject *marker)
{
    return stream_append(stream, marker);
}

static int
stream_add_pair(PyObject *stream, PyObject *name, PyObject *value)
{
    PyObject *pair = PyTuple_Pack(2, name, value);
    return stream_append_new(stream, pair);
}

static int
stream_add_named_pair(PyObject *stream, const char *name, PyObject *value)
{
    PyObject *key = PyUnicode_FromString(name);
    if (key == NULL) {
        return -1;
    }
    int result = stream_add_pair(stream, key, value);
    Py_DECREF(key);
    return result;
}

static int
stream_add_items_method(PyObject *stream, PyObject *obj)
{
    PyObject *items = PyObject_CallMethod(obj, "items", NULL);
    if (items == NULL) {
        return -1;
    }
    int result = stream_append_iter(stream, items);
    Py_DECREF(items);
    return result;
}

#define CHECK_STREAM(expr) do { if ((expr) < 0) goto error; } while (0)
#define METHOD_STATE() \
    pprint_state *state = PyModule_GetState(module); \
    if (state == NULL) return NULL

static PyObject *
list_pprint(PyObject *module, PyObject *obj)
{
    METHOD_STATE();
    PyObject *stream = stream_new();
    if (stream == NULL) return NULL;
    CHECK_STREAM(stream_start(stream, new_layout(state, "[", "]", NULL,
                                                  NULL, NULL, "[...]", 0, 0,
                                                  NULL, NULL, NULL)));
    CHECK_STREAM(stream_append_iter(stream, obj));
    return stream_finish(stream);
error:
    Py_DECREF(stream);
    return NULL;
}

static PyObject *
dict_pprint(PyObject *module, PyObject *obj)
{
    METHOD_STATE();
    PyObject *stream = stream_new();
    if (stream == NULL) return NULL;
    CHECK_STREAM(stream_start(stream, new_layout(state, "{", "}", NULL,
                                                  NULL, NULL, "{...}", 1, 0,
                                                  NULL, NULL, NULL)));
    CHECK_STREAM(stream_add_marker(stream, state->items));
    CHECK_STREAM(stream_add_items_method(stream, obj));
    return stream_finish(stream);
error:
    Py_DECREF(stream);
    return NULL;
}

static PyObject *
frozendict_pprint(PyObject *module, PyObject *obj)
{
    METHOD_STATE();
    PyObject *name = type_name(obj);
    if (name == NULL) return NULL;
    PyObject *open = PyUnicode_FromFormat("%U({", name);
    PyObject *close = PyUnicode_FromString("})");
    PyObject *empty = PyUnicode_FromFormat("%U()", name);
    Py_DECREF(name);
    if (open == NULL || close == NULL || empty == NULL) {
        Py_XDECREF(open); Py_XDECREF(close); Py_XDECREF(empty);
        return NULL;
    }
    PyObject *layout = new_layout(state, NULL, NULL, NULL, NULL, NULL, NULL,
                                  1, 0, open, close, empty);
    Py_DECREF(open); Py_DECREF(close); Py_DECREF(empty);
    PyObject *stream = stream_new();
    if (layout == NULL || stream == NULL) {
        Py_XDECREF(layout); Py_XDECREF(stream);
        return NULL;
    }
    CHECK_STREAM(stream_start(stream, layout));
    CHECK_STREAM(stream_add_marker(stream, state->items));
    CHECK_STREAM(stream_add_items_method(stream, obj));
    return stream_finish(stream);
error:
    Py_DECREF(stream);
    return NULL;
}

static PyObject *
ordered_dict_pprint(PyObject *module, PyObject *obj)
{
    METHOD_STATE();
    PyObject *name = type_name(obj);
    if (name == NULL) return NULL;
    PyObject *open = PyUnicode_FromFormat("%U([", name);
    PyObject *close = PyUnicode_FromString("])");
    PyObject *empty = PyUnicode_FromFormat("%U()", name);
    Py_DECREF(name);
    if (open == NULL || close == NULL || empty == NULL) {
        Py_XDECREF(open); Py_XDECREF(close); Py_XDECREF(empty);
        return NULL;
    }
    PyObject *layout = new_layout(state, NULL, NULL, NULL, NULL, NULL, NULL,
                                  0, 0, NULL, NULL, empty);
    Py_DECREF(open); Py_DECREF(close); Py_DECREF(empty);
    PyObject *stream = stream_new();
    if (layout == NULL || stream == NULL) {
        Py_XDECREF(layout); Py_XDECREF(stream);
        return NULL;
    }
    CHECK_STREAM(stream_start(stream, layout));
    CHECK_STREAM(stream_add_marker(stream, state->items));
    CHECK_STREAM(stream_add_items_method(stream, obj));
    return stream_finish(stream);
error:
    Py_DECREF(stream);
    return NULL;
}

static PyObject *
dict_view_pprint(PyObject *module, PyObject *obj)
{
    METHOD_STATE();
    PyObject *name = type_name(obj);
    if (name == NULL) return NULL;
    PyObject *open = PyUnicode_FromFormat("%U([", name);
    PyObject *close = PyUnicode_FromString("])");
    Py_DECREF(name);
    if (open == NULL || close == NULL) {
        Py_XDECREF(open); Py_XDECREF(close);
        return NULL;
    }
    PyObject *layout = new_layout(state, NULL, NULL, NULL, NULL, NULL, NULL,
                                  1, 0, open, close, NULL);
    Py_DECREF(open); Py_DECREF(close);
    PyObject *stream = stream_new();
    if (layout == NULL || stream == NULL) {
        Py_XDECREF(layout); Py_XDECREF(stream);
        return NULL;
    }
    CHECK_STREAM(stream_start(stream, layout));
    CHECK_STREAM(stream_append_iter(stream, obj));
    return stream_finish(stream);
error:
    Py_DECREF(stream);
    return NULL;
}

static PyObject *
tuple_pprint(PyObject *module, PyObject *obj)
{
    METHOD_STATE();
    PyObject *stream = stream_new();
    if (stream == NULL) return NULL;
    CHECK_STREAM(stream_start(stream, new_layout(state, "(", ")", NULL,
                                                  ",)", NULL, "(...)", 0, 0,
                                                  NULL, NULL, NULL)));
    CHECK_STREAM(stream_append_iter(stream, obj));
    return stream_finish(stream);
error:
    Py_DECREF(stream);
    return NULL;
}

static PyObject *
set_pprint(PyObject *module, PyObject *obj)
{
    METHOD_STATE();
    PyObject *layout;
    if (Py_TYPE(obj) == &PySet_Type) {
        layout = new_layout(state, "{", "}", "set()", NULL, NULL, NULL, 1, 0,
                            NULL, NULL, NULL);
    }
    else {
        PyObject *name = type_name(obj);
        if (name == NULL) return NULL;
        PyObject *open = PyUnicode_FromFormat("%U({", name);
        PyObject *close = PyUnicode_FromString("})");
        PyObject *empty = PyUnicode_FromFormat("%U()", name);
        Py_DECREF(name);
        if (open == NULL || close == NULL || empty == NULL) {
            Py_XDECREF(open); Py_XDECREF(close); Py_XDECREF(empty);
            return NULL;
        }
        layout = new_layout(state, NULL, NULL, NULL, NULL, NULL, NULL, 1, 0,
                            open, close, empty);
        Py_DECREF(open); Py_DECREF(close); Py_DECREF(empty);
    }
    PyObject *stream = stream_new();
    if (layout == NULL || stream == NULL) {
        Py_XDECREF(layout); Py_XDECREF(stream);
        return NULL;
    }
    CHECK_STREAM(stream_start(stream, layout));
    CHECK_STREAM(stream_append_iter(stream, obj));
    return stream_finish(stream);
error:
    Py_DECREF(stream);
    return NULL;
}

static PyObject *
frozen_set_pprint(PyObject *module, PyObject *obj)
{
    METHOD_STATE();
    PyObject *name = type_name(obj);
    if (name == NULL) return NULL;
    PyObject *open = PyUnicode_FromFormat("%U({", name);
    PyObject *close = PyUnicode_FromString("})");
    PyObject *empty = PyUnicode_FromFormat("%U()", name);
    Py_DECREF(name);
    if (open == NULL || close == NULL || empty == NULL) {
        Py_XDECREF(open); Py_XDECREF(close); Py_XDECREF(empty);
        return NULL;
    }
    PyObject *layout = new_layout(state, NULL, NULL, NULL, NULL, NULL, NULL,
                                  1, 0, open, close, empty);
    Py_DECREF(open); Py_DECREF(close); Py_DECREF(empty);
    PyObject *stream = stream_new();
    if (layout == NULL || stream == NULL) {
        Py_XDECREF(layout); Py_XDECREF(stream);
        return NULL;
    }
    CHECK_STREAM(stream_start(stream, layout));
    CHECK_STREAM(stream_append_iter(stream, obj));
    return stream_finish(stream);
error:
    Py_DECREF(stream);
    return NULL;
}

static PyObject *
delegated_pprint(PyObject *module, PyObject *obj, PyObject *wrapper_type)
{
    pprint_state *state = PyModule_GetState(module);
    if (state == NULL) return NULL;
    PyObject *stream = PyTuple_New(2);
    if (stream == NULL) return NULL;
    PyObject *wrapped = PyObject_CallOneArg(wrapper_type, obj);
    if (wrapped == NULL) {
        Py_DECREF(stream);
        return NULL;
    }
    PyTuple_SET_ITEM(stream, 0, Py_NewRef(state->delegate));
    PyTuple_SET_ITEM(stream, 1, wrapped);
    return stream;
}

static PyObject *
str_pprint(PyObject *module, PyObject *obj)
{
    METHOD_STATE();
    return delegated_pprint(module, obj, state->breakable_string_type);
}

static PyObject *
bytes_pprint(PyObject *module, PyObject *obj)
{
    METHOD_STATE();
    return delegated_pprint(module, obj, state->breakable_bytes_type);
}

static PyObject *
number_pprint(PyObject *module, PyObject *obj)
{
    METHOD_STATE();
    PyObject *stream = PyTuple_New(2);
    if (stream == NULL) return NULL;
    PyObject *wrapped = PyObject_CallOneArg(state->formattable_number_type, obj);
    if (wrapped == NULL) {
        Py_DECREF(stream);
        return NULL;
    }
    PyTuple_SET_ITEM(stream, 0, Py_NewRef(state->delegate));
    PyTuple_SET_ITEM(stream, 1, wrapped);
    return stream;
}

static PyObject *
int_pprint(PyObject *module, PyObject *obj)
{
    return number_pprint(module, obj);
}

static PyObject *
float_pprint(PyObject *module, PyObject *obj)
{
    return number_pprint(module, obj);
}

static PyObject *
bytearray_pprint(PyObject *module, PyObject *obj)
{
    METHOD_STATE();
    PyObject *value = PyObject_CallOneArg((PyObject *)&PyBytes_Type, obj);
    if (value == NULL) return NULL;
    PyObject *stream = stream_new();
    if (stream == NULL) { Py_DECREF(value); return NULL; }
    PyObject *layout = new_layout(state, "bytearray(", ")", NULL,
                                  NULL, "", NULL, 0, 0, NULL, NULL, NULL);
    if (layout == NULL) {
        Py_DECREF(value);
        Py_DECREF(stream);
        return NULL;
    }
    if (stream_start(stream, layout) < 0) {
        Py_DECREF(value);
        Py_DECREF(stream);
        return NULL;
    }
    if (stream_append_new(stream, value) < 0) {
        Py_DECREF(stream);
        return NULL;
    }
    return stream_finish(stream);
}

static PyObject *
mappingproxy_pprint(PyObject *module, PyObject *obj)
{
    METHOD_STATE();
    PyObject *value = PyObject_CallOneArg((PyObject *)&PyDict_Type, obj);
    if (value == NULL) return NULL;
    PyObject *stream = stream_new();
    if (stream == NULL) { Py_DECREF(value); return NULL; }
    PyObject *layout = new_layout(state, "mappingproxy(", ")", NULL,
                                  NULL, NULL, NULL, 0, 1, NULL, NULL, NULL);
    if (layout == NULL) {
        Py_DECREF(value);
        Py_DECREF(stream);
        return NULL;
    }
    if (stream_start(stream, layout) < 0) {
        Py_DECREF(value);
        Py_DECREF(stream);
        return NULL;
    }
    if (stream_append_new(stream, value) < 0) {
        Py_DECREF(stream);
        return NULL;
    }
    return stream_finish(stream);
}

static PyObject *
namespace_pprint(PyObject *module, PyObject *obj)
{
    METHOD_STATE();
    PyObject *name = Py_TYPE(obj) == (PyTypeObject *)state->namespace_type ?
        PyUnicode_FromString("namespace") : type_name(obj);
    if (name == NULL) return NULL;
    PyObject *open = PyUnicode_FromFormat("%U(", name);
    Py_DECREF(name);
    if (open == NULL) return NULL;
    PyObject *close = PyUnicode_FromString(")");
    if (close == NULL) { Py_DECREF(open); return NULL; }
    PyObject *layout = new_layout(state, NULL, NULL, NULL, NULL, NULL, NULL, 0, 0,
                                  open, close, NULL);
    Py_DECREF(open); Py_DECREF(close);
    PyObject *stream = stream_new();
    if (layout == NULL || stream == NULL) {
        Py_XDECREF(layout); Py_XDECREF(stream);
        return NULL;
    }
    PyObject *dict = PyObject_GetAttrString(obj, "__dict__");
    PyObject *items = NULL;
    if (dict == NULL) goto error;
    items = PyObject_CallMethod(dict, "items", NULL);
    Py_DECREF(dict);
    if (items == NULL) goto error;
    PyObject *layout_to_add = layout;
    layout = NULL;
    CHECK_STREAM(stream_start(stream, layout_to_add));
    CHECK_STREAM(stream_add_marker(stream, state->kwargs));
    CHECK_STREAM(stream_append_iter(stream, items));
    Py_DECREF(items);
    return stream_finish(stream);
error:
    Py_XDECREF(layout);
    Py_XDECREF(items);
    Py_DECREF(stream);
    return NULL;
}

static PyObject *
defaultdict_pprint(PyObject *module, PyObject *obj)
{
    METHOD_STATE();
    PyObject *name = type_name(obj);
    if (name == NULL) return NULL;
    PyObject *open = PyUnicode_FromFormat("%U(", name);
    Py_DECREF(name);
    if (open == NULL) return NULL;
    PyObject *close = PyUnicode_FromString(")");
    if (close == NULL) { Py_DECREF(open); return NULL; }
    PyObject *layout = new_layout(state, NULL, NULL, NULL, NULL, NULL, NULL, 0, 1,
                                  open, close, NULL);
    Py_DECREF(open); Py_DECREF(close);
    PyObject *factory = PyObject_GetAttrString(obj, "default_factory");
    PyObject *dict = PyObject_CallOneArg((PyObject *)&PyDict_Type, obj);
    PyObject *stream = stream_new();
    if (layout == NULL || factory == NULL || dict == NULL || stream == NULL) {
        Py_XDECREF(layout); Py_XDECREF(factory); Py_XDECREF(dict);
        Py_XDECREF(stream);
        return NULL;
    }
    CHECK_STREAM(stream_start(stream, layout));
    int result = stream_append_new(stream, factory);
    factory = NULL;
    CHECK_STREAM(result);
    result = stream_append_new(stream, dict);
    dict = NULL;
    CHECK_STREAM(result);
    return stream_finish(stream);
error:
    Py_XDECREF(factory);
    Py_XDECREF(dict);
    Py_DECREF(stream);
    return NULL;
}

static PyObject *
deque_pprint(PyObject *module, PyObject *obj)
{
    METHOD_STATE();
    PyObject *maxlen = PyObject_GetAttrString(obj, "maxlen");
    if (maxlen == NULL) {
        return NULL;
    }
    PyObject *layout = new_layout(state, NULL, NULL, NULL, NULL, NULL,
                                  "[...]", 0, 1, NULL, NULL, NULL);
    PyObject *stream = stream_new();
    if (layout == NULL || stream == NULL) {
        Py_XDECREF(layout);
        Py_XDECREF(stream);
        Py_DECREF(maxlen);
        return NULL;
    }
    CHECK_STREAM(stream_start(stream, layout));
    PyObject *values = PySequence_List(obj);
    if (values == NULL) goto error;
    CHECK_STREAM(stream_append_new(stream, values));
    if (maxlen != Py_None) {
        PyObject *key = PyUnicode_FromString("maxlen");
        if (key == NULL) goto error;
        if (stream_add_marker(stream, state->kwargs) < 0) {
            Py_DECREF(key);
            goto error;
        }
        int result = stream_add_pair(stream, key, maxlen);
        Py_DECREF(key);
        if (result < 0) goto error;
    }
    Py_DECREF(maxlen);
    return stream_finish(stream);
error:
    Py_DECREF(maxlen);
    Py_DECREF(stream);
    return NULL;
}

static PyObject *
template_pprint(PyObject *module, PyObject *obj)
{
    METHOD_STATE();
    PyObject *name = type_name(obj);
    if (name == NULL) return NULL;
    PyObject *open = PyUnicode_FromFormat("%U(", name);
    Py_DECREF(name);
    if (open == NULL) return NULL;
    PyObject *close = PyUnicode_FromString(")");
    if (close == NULL) { Py_DECREF(open); return NULL; }
    PyObject *layout = new_layout(state, NULL, NULL, NULL, NULL, NULL, NULL, 0, 0,
                                  open, close, NULL);
    Py_DECREF(open); Py_DECREF(close);
    PyObject *strings = PyObject_GetAttrString(obj, "strings");
    PyObject *interpolations = PyObject_GetAttrString(obj, "interpolations");
    PyObject *stream = stream_new();
    if (layout == NULL || strings == NULL || interpolations == NULL || stream == NULL) {
        Py_XDECREF(layout); Py_XDECREF(strings); Py_XDECREF(interpolations);
        Py_XDECREF(stream);
        return NULL;
    }
    CHECK_STREAM(stream_start(stream, layout));
    CHECK_STREAM(stream_add_marker(stream, state->kwargs));
    CHECK_STREAM(stream_add_named_pair(stream, "strings", strings));
    CHECK_STREAM(stream_add_named_pair(stream, "interpolations", interpolations));
    Py_DECREF(strings); Py_DECREF(interpolations);
    return stream_finish(stream);
error:
    Py_XDECREF(strings);
    Py_XDECREF(interpolations);
    Py_DECREF(stream);
    return NULL;
}

static PyObject *
interpolation_pprint(PyObject *module, PyObject *obj)
{
    METHOD_STATE();
    PyObject *name = type_name(obj);
    if (name == NULL) return NULL;
    PyObject *open = PyUnicode_FromFormat("%U(", name);
    Py_DECREF(name);
    if (open == NULL) return NULL;
    PyObject *close = PyUnicode_FromString(")");
    if (close == NULL) { Py_DECREF(open); return NULL; }
    PyObject *layout = new_layout(state, NULL, NULL, NULL, NULL, NULL, NULL, 0, 0,
                                  open, close, NULL);
    Py_DECREF(open); Py_DECREF(close);
    PyObject *stream = stream_new();
    if (layout == NULL || stream == NULL) {
        Py_XDECREF(layout); Py_XDECREF(stream);
        return NULL;
    }
    const char *attrs[] = {"value", "expression", "conversion", "format_spec"};
    CHECK_STREAM(stream_start(stream, layout));
    for (size_t i = 0; i < Py_ARRAY_LENGTH(attrs); i++) {
        PyObject *value = PyObject_GetAttrString(obj, attrs[i]);
        if (value == NULL) goto error;
        int result = stream_append(stream, value);
        Py_DECREF(value);
        if (result < 0) {
            goto error;
        }
    }
    PyObject *printer = PyObject_GetAttrString(obj, "printer");
    if (printer == NULL) goto error;
    if (printer != Py_None) {
        if (stream_add_marker(stream, state->kwargs) < 0) {
            Py_DECREF(printer);
            goto error;
        }
        if (stream_add_named_pair(stream, "printer", printer) < 0) {
            Py_DECREF(printer);
            goto error;
        }
    }
    Py_DECREF(printer);
    return stream_finish(stream);
error:
    Py_DECREF(stream);
    return NULL;
}

static PyMethodDef pprint_methods[] = {
    {"_list_pprint", list_pprint, METH_O, NULL},
    {"_dict_pprint", dict_pprint, METH_O, NULL},
    {"_frozendict_pprint", frozendict_pprint, METH_O, NULL},
    {"_ordered_dict_pprint", ordered_dict_pprint, METH_O, NULL},
    {"_dict_view_pprint", dict_view_pprint, METH_O, NULL},
    {"_tuple_pprint", tuple_pprint, METH_O, NULL},
    {"_set_pprint", set_pprint, METH_O, NULL},
    {"_frozen_set_pprint", frozen_set_pprint, METH_O, NULL},
    {"_str_pprint", str_pprint, METH_O, NULL},
    {"_bytes_pprint", bytes_pprint, METH_O, NULL},
    {"_int_pprint", int_pprint, METH_O, NULL},
    {"_float_pprint", float_pprint, METH_O, NULL},
    {"_bytearray_pprint", bytearray_pprint, METH_O, NULL},
    {"_mappingproxy_pprint", mappingproxy_pprint, METH_O, NULL},
    {"_namespace_pprint", namespace_pprint, METH_O, NULL},
    {"_defaultdict_pprint", defaultdict_pprint, METH_O, NULL},
    {"_deque_pprint", deque_pprint, METH_O, NULL},
    {"_template_pprint", template_pprint, METH_O, NULL},
    {"_interpolation_pprint", interpolation_pprint, METH_O, NULL},
    {NULL}
};

static int
add_sentinel(PyObject *module, PyObject **target, const char *name,
             const char *repr)
{
    PyObject *value = PySentinel_New(name, "pprint", repr);
    if (value == NULL) {
        return -1;
    }
    *target = value;
    if (PyModule_AddObjectRef(module, name, value) < 0) {
        Py_CLEAR(*target);
        return -1;
    }
    return 0;
}

static int
pprint_exec(PyObject *module)
{
    pprint_state *state = PyModule_GetState(module);
    state->layout_type = PyType_FromModuleAndSpec(module, &layout_spec, NULL);
    state->leaf_marker_type = PyType_FromModuleAndSpec(
        module, &leaf_marker_spec, NULL);
    PyObject *marker_bases = state->leaf_marker_type == NULL ? NULL :
        PyTuple_Pack(1, state->leaf_marker_type);
    state->breakable_string_type = PyType_FromModuleAndSpec(
        module, &breakable_string_spec, marker_bases);
    state->breakable_bytes_type = PyType_FromModuleAndSpec(
        module, &breakable_bytes_spec, marker_bases);
    state->formattable_number_type = PyType_FromModuleAndSpec(
        module, &formattable_number_spec, marker_bases);
    Py_XDECREF(marker_bases);
    if (state->layout_type == NULL || state->leaf_marker_type == NULL ||
        state->breakable_string_type == NULL ||
        state->breakable_bytes_type == NULL ||
        state->formattable_number_type == NULL) {
        return -1;
    }
    if (PyModule_AddType(module, (PyTypeObject *)state->layout_type) < 0 ||
        PyModule_AddType(module, (PyTypeObject *)state->leaf_marker_type) < 0 ||
        PyModule_AddType(module, (PyTypeObject *)state->breakable_string_type) < 0 ||
        PyModule_AddType(module, (PyTypeObject *)state->breakable_bytes_type) < 0 ||
        PyModule_AddType(module, (PyTypeObject *)state->formattable_number_type) < 0) {
        return -1;
    }
    if (add_sentinel(module, &state->values, "VALUES", "pprint.VALUES") < 0 ||
        add_sentinel(module, &state->kwargs, "KWARGS", "pprint.KWARGS") < 0 ||
        add_sentinel(module, &state->items, "ITEMS", "pprint.ITEMS") < 0 ||
        add_sentinel(module, &state->delegate, "DELEGATE", "pprint.DELEGATE") < 0) {
        return -1;
    }
    PyObject *types = PyImport_ImportModule("types");
    if (types == NULL) {
        return -1;
    }
    state->namespace_type = PyObject_GetAttrString(types, "SimpleNamespace");
    Py_DECREF(types);
    if (state->namespace_type == NULL) {
        return -1;
    }
    return 0;
}

static PyModuleDef_Slot pprint_slots[] = {
    {Py_mod_exec, pprint_exec},
    {Py_mod_multiple_interpreters, Py_MOD_PER_INTERPRETER_GIL_SUPPORTED},
    {0, NULL}
};

static struct PyModuleDef pprint_module = {
    PyModuleDef_HEAD_INIT,
    .m_name = "_pprint",
    .m_doc = "C support for the PEP 813 pretty-print protocol.",
    .m_size = sizeof(pprint_state),
    .m_methods = pprint_methods,
    .m_slots = pprint_slots,
    .m_traverse = pprint_traverse,
    .m_clear = pprint_clear,
};

PyMODINIT_FUNC
PyInit__pprint(void)
{
    return PyModuleDef_Init(&pprint_module);
}
