"""
Template and channel name derivation from LiveOperation subclasses.

class_to_snake uses the inflection-style two-pass regex:
  pass 1: ([A-Z]+)([A-Z][a-z]) → insert _ before final cap of acronym
  pass 2: ([a-z\\d])([A-Z])    → insert _ between lower/digit and upper
  then .lower()

Examples: ImportPunktacji→import_punktacji, ImportPBN2→import_pbn2,
          ABCTest→abc_test, DemoOp→demo_op.
"""
from __future__ import annotations

import re
from typing import Any


def class_to_snake(name: str) -> str:
    """Convert CamelCase class name to snake_case, handling acronyms/digits."""
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    name = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", name)
    return name.lower()


def _class_name(model_cls: Any) -> str:
    # vars() bypasses the type.__name__ C-level descriptor, returning any
    # explicit __name__ override set in the class body or for test fakes.
    return vars(model_cls).get("__name__") or model_cls.__name__


def host_template_name(model_cls: Any) -> str:
    """
    Return the host page template name for *model_cls*.

    Override: set ``host_template_name = "..."`` as a class attribute (str).
    Auto: ``<app_label>/<class_to_snake(ClassName)>.html``
    """
    attr = getattr(model_cls, "host_template_name", None)
    if isinstance(attr, str):
        return attr
    app_label = model_cls._meta.app_label
    snake = class_to_snake(_class_name(model_cls))
    return f"{app_label}/{snake}.html"


def result_template_name(model_cls: Any) -> str:
    """
    Return the result fragment template name for *model_cls*.

    Override: set ``result_template_name = "..."`` as a class attribute (str).
    Auto: ``<app_label>/<class_to_snake(ClassName)>_result.html``
    """
    attr = getattr(model_cls, "result_template_name", None)
    if isinstance(attr, str):
        return attr
    app_label = model_cls._meta.app_label
    snake = class_to_snake(_class_name(model_cls))
    return f"{app_label}/{snake}_result.html"


def channel_name(op: Any) -> str:
    """Return the Channels group name for *op*: ``liveop.<pk>``."""
    return f"liveop.{op.pk}"
