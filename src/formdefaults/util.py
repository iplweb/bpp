def full_name(o):
    module = o.__class__.__module__
    if module is None or module == str.__class__.__module__:
        return o.__class__.__name__
    return module + "." + o.__class__.__name__


def get_python_class_by_name(full_name):
    import importlib

    s_module = full_name[: full_name.rfind(".")]
    s_klass = full_name[full_name.rfind(".") + 1 :]

    py_module = importlib.import_module(s_module)
    py_klass = getattr(py_module, s_klass)

    return py_klass
