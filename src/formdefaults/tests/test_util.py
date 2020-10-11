from formdefaults.models import FormRepresentationManager
from formdefaults.util import full_name, get_python_class_by_name


def test_full_name():
    assert (
        full_name(FormRepresentationManager())
        == "formdefaults.models.FormRepresentationManager"
    )


def test_get_python_class_by_name():
    fn = "formdefaults.models.FormRepresentationManager"
    assert get_python_class_by_name(fn) == FormRepresentationManager
