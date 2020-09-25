from formdefaults.models import FormRepresentationManager
from formdefaults.util import full_name


def test_full_name():
    assert (
        full_name(FormRepresentationManager())
        == "formdefaults.models.FormRepresentationManager"
    )
