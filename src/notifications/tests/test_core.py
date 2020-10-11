from notifications.core import (
    get_obj_from_channel_name,
    convert_obj_to_channel_name,
)
import pytest


@pytest.mark.django_db
def test_convert_obj_to_channel_name(wydawnictwo_zwarte):
    assert convert_obj_to_channel_name(wydawnictwo_zwarte).startswith(
        "bpp.wydawnictwo_zwarte-"
    )


@pytest.mark.django_db
def test_get_obj_from_channel_name(wydawnictwo_zwarte):
    pk = wydawnictwo_zwarte.pk
    rec = get_obj_from_channel_name(f"bpp.wydawnictwo_zwarte-{pk}")
    assert rec == wydawnictwo_zwarte
