import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_match_email_false_skips_email_matching():
    baker.make("bpp.Autor", email="jan@x.pl")
    user = baker.make("bpp.BppUser", email="jan@x.pl", first_name="", last_name="")
    user.sprobuj_dopasowac_autora(match_email=False)
    user.refresh_from_db()
    assert user.autor_id is None


@pytest.mark.django_db
def test_match_names_false_skips_name_matching():
    baker.make("bpp.Autor", imiona="Jan", nazwisko="Kowalski", email="")
    user = baker.make("bpp.BppUser", first_name="Jan", last_name="Kowalski", email="")
    user.sprobuj_dopasowac_autora(match_names=False)
    user.refresh_from_db()
    assert user.autor_id is None
