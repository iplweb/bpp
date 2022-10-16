class CodeAccessNotAllowed(Exception):
    """This exception occurs when a code tries to import a module from a
    path that is not explictly allowed.

    The way it works:
    * you should put ``DYNAMIC_COLUMNS_ALLOWED_IMPORT_PATHS`` setting in your settings.py,
      it should be a list of admin modules, that are allowed to be imported from module names
      stored inside database
    * if database wants to import a module that is not in this path, like instead importing
      ``yourapp.admin.SomeClass`` it wants to import ``malicious_module.code``, this exception
      will be raised.
    """
