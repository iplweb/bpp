import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_check_if_upload_needed_lifecycle():
    from dspace_api.models import SentToDSpace

    rec = baker.make("bpp.Wydawnictwo_Ciagle")
    uczelnia = baker.make("bpp.Uczelnia")
    data = {"dc.title": [{"value": "T"}]}

    assert SentToDSpace.objects.check_if_upload_needed(rec, uczelnia, data)

    SentToDSpace.objects.create_or_update_before_upload(rec, uczelnia, data)
    SentToDSpace.objects.mark_as_successful(
        rec, uczelnia, dspace_uuid="33333333-3333-3333-3333-333333333333"
    )

    assert not SentToDSpace.objects.check_if_upload_needed(rec, uczelnia, data)

    assert SentToDSpace.objects.check_if_upload_needed(
        rec, uczelnia, {"dc.title": [{"value": "INNE"}]}
    )


@pytest.mark.django_db
def test_per_uczelnia_isolation():
    from dspace_api.models import SentToDSpace

    rec = baker.make("bpp.Wydawnictwo_Ciagle")
    u1 = baker.make("bpp.Uczelnia")
    u2 = baker.make("bpp.Uczelnia")
    data = {"x": 1}

    SentToDSpace.objects.create_or_update_before_upload(rec, u1, data)
    SentToDSpace.objects.mark_as_successful(rec, u1, dspace_uuid=None)

    assert not SentToDSpace.objects.check_if_upload_needed(rec, u1, data)
    assert SentToDSpace.objects.check_if_upload_needed(rec, u2, data)


@pytest.mark.django_db
def test_bitstreams_zapis_i_odczyt():
    from dspace_api.models import SentToDSpace

    rec = baker.make("bpp.Wydawnictwo_Ciagle")
    uczelnia = baker.make("bpp.Uczelnia")
    data = {"dc.title": [{"value": "T"}]}

    SentToDSpace.objects.create_or_update_before_upload(rec, uczelnia, data)
    SentToDSpace.objects.mark_as_successful(
        rec, uczelnia, dspace_uuid=None, bitstreams={"5": "uuid-a", "7": "uuid-b"}
    )
    sd = SentToDSpace.objects.get_for_rec(rec, uczelnia)
    assert sd.bitstreams == {"5": "uuid-a", "7": "uuid-b"}


@pytest.mark.django_db
def test_mark_as_successful_zapisuje_handle():
    from dspace_api.models import SentToDSpace

    rec = baker.make("bpp.Wydawnictwo_Ciagle")
    uczelnia = baker.make("bpp.Uczelnia")
    data = {"dc.title": [{"value": "T"}]}

    SentToDSpace.objects.create_or_update_before_upload(rec, uczelnia, data)
    SentToDSpace.objects.mark_as_successful(
        rec, uczelnia, dspace_uuid=None, dspace_handle="11089/42"
    )
    assert SentToDSpace.objects.get_for_rec(rec, uczelnia).dspace_handle == "11089/42"


@pytest.mark.django_db
def test_check_if_upload_needed_wykrywa_zmiane_plikow():
    from dspace_api.models import SentToDSpace

    rec = baker.make("bpp.Wydawnictwo_Ciagle")
    uczelnia = baker.make("bpp.Uczelnia")
    data = {"dc.title": [{"value": "T"}]}

    SentToDSpace.objects.create_or_update_before_upload(rec, uczelnia, data)
    SentToDSpace.objects.mark_as_successful(
        rec, uczelnia, dspace_uuid=None, bitstreams={"5": "uuid-a"}
    )

    # te same metadane + ten sam zbiór plików {5} → NIE trzeba
    assert not SentToDSpace.objects.check_if_upload_needed(
        rec, uczelnia, data, bitstream_ids=[5]
    )
    # te same metadane, ale plik 5 usunięty (zbiór pusty) → TRZEBA (reconcile)
    assert SentToDSpace.objects.check_if_upload_needed(
        rec, uczelnia, data, bitstream_ids=[]
    )
    # te same metadane, dodany plik 9 → TRZEBA
    assert SentToDSpace.objects.check_if_upload_needed(
        rec, uczelnia, data, bitstream_ids=[5, 9]
    )
