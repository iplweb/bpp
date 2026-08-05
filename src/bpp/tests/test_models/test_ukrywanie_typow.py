"""Testy ukrywania nieużywanych pozycji słownikowych na listach wyboru.

Freshdesk #382: pozycje słowników ``Charakter_Formalny``, ``Typ_KBN`` oraz
``Charakter_PBN`` oznaczone ``ukryty=True`` mają znikać z list wyboru przy
WPROWADZANIU danych, ale pozostawać dostępne dla istniejących rekordów.

Filtrowanie realizujemy przez ``limit_choices_to={"ukryty": False}`` na FK
formularzowych — to ogranicza wyłącznie ``ModelChoiceField`` w formularzach,
nie ruszając domyślnego managera ani istniejących rekordów.
"""

import pytest
from django.forms import modelform_factory
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from bpp.models.system import Charakter_Formalny, Charakter_PBN, Typ_KBN


def _form_field_pks(model, field_name):
    """Zwraca pk-i widoczne w ``ModelChoiceField`` formularza dla danego FK.

    Używamy realnego ``ModelForm`` (``modelform_factory``), bo to dopiero on —
    nie surowe ``field.formfield()`` — stosuje ``limit_choices_to`` przez
    ``apply_limit_choices_to_to_formfield``."""
    form_cls = modelform_factory(model, fields=[field_name])
    queryset = form_cls().fields[field_name].queryset
    return set(queryset.values_list("pk", flat=True))


@pytest.mark.django_db
def test_charakter_formalny_ukryty_znika_z_listy_wyboru():
    widoczny = baker.make(Charakter_Formalny, nazwa="Widoczny", skrot="WID")
    ukryty = baker.make(Charakter_Formalny, nazwa="Ukryty", skrot="UKR", ukryty=True)

    pks = _form_field_pks(Wydawnictwo_Ciagle, "charakter_formalny")

    assert widoczny.pk in pks
    assert ukryty.pk not in pks


@pytest.mark.django_db
def test_typ_kbn_ukryty_znika_z_listy_wyboru():
    widoczny = baker.make(Typ_KBN, nazwa="Widoczny", skrot="WID")
    ukryty = baker.make(Typ_KBN, nazwa="Ukryty", skrot="UKR", ukryty=True)

    pks = _form_field_pks(Wydawnictwo_Ciagle, "typ_kbn")

    assert widoczny.pk in pks
    assert ukryty.pk not in pks


@pytest.mark.django_db
def test_charakter_pbn_ukryty_znika_z_listy_wyboru_charakteru_formalnego():
    widoczny = baker.make(Charakter_PBN, identyfikator="A", opis="Widoczny")
    ukryty = baker.make(Charakter_PBN, identyfikator="B", opis="Ukryty", ukryty=True)

    pks = _form_field_pks(Charakter_Formalny, "charakter_pbn")

    assert widoczny.pk in pks
    assert ukryty.pk not in pks


@pytest.mark.django_db
def test_charakter_pbn_ukryty_znika_z_listy_wyboru_typu_kbn():
    widoczny = baker.make(Charakter_PBN, identyfikator="A", opis="Widoczny")
    ukryty = baker.make(Charakter_PBN, identyfikator="B", opis="Ukryty", ukryty=True)

    pks = _form_field_pks(Typ_KBN, "charakter_pbn")

    assert widoczny.pk in pks
    assert ukryty.pk not in pks


@pytest.mark.django_db
def test_domyslny_manager_nie_filtruje_ukrytych():
    """``limit_choices_to`` NIE może wpływać na domyślny manager —
    istniejące rekordy i listy w adminie muszą widzieć pozycje ukryte."""
    baker.make(Charakter_Formalny, nazwa="Ukryty", skrot="UKR", ukryty=True)
    baker.make(Typ_KBN, nazwa="Ukryty", skrot="UKR", ukryty=True)

    assert Charakter_Formalny.objects.filter(ukryty=True).count() == 1
    assert Typ_KBN.objects.filter(ukryty=True).count() == 1


@pytest.mark.django_db
def test_istniejacy_rekord_z_ukrytym_charakterem_dalej_dziala(
    wydawnictwo_ciagle,
):
    """Rekord wskazujący na ukryty już charakter/typ nadal się waliduje,
    zapisuje i wyświetla — ukrycie dotyczy tylko NOWYCH wyborów."""
    charakter = wydawnictwo_ciagle.charakter_formalny
    typ = wydawnictwo_ciagle.typ_kbn

    charakter.ukryty = True
    charakter.save()
    typ.ukryty = True
    typ.save()

    wydawnictwo_ciagle.full_clean(
        exclude=["slug", "opis_bibliograficzny_cache"], validate_unique=False
    )
    wydawnictwo_ciagle.refresh_from_db()

    assert wydawnictwo_ciagle.charakter_formalny.ukryty is True
    assert wydawnictwo_ciagle.typ_kbn.ukryty is True
    assert str(wydawnictwo_ciagle)


@pytest.mark.django_db
def test_importer_verify_form_pomija_ukryte(jezyki):
    from importer_publikacji.forms import VerifyForm

    widoczny_chf = baker.make(Charakter_Formalny, nazwa="W", skrot="WCHF")
    ukryty_chf = baker.make(Charakter_Formalny, nazwa="U", skrot="UCHF", ukryty=True)
    widoczny_typ = baker.make(Typ_KBN, nazwa="W", skrot="WTYP")
    ukryty_typ = baker.make(Typ_KBN, nazwa="U", skrot="UTYP", ukryty=True)

    form = VerifyForm()

    chf_pks = set(
        form.fields["charakter_formalny"].queryset.values_list("pk", flat=True)
    )
    typ_pks = set(form.fields["typ_kbn"].queryset.values_list("pk", flat=True))

    assert widoczny_chf.pk in chf_pks
    assert ukryty_chf.pk not in chf_pks
    assert widoczny_typ.pk in typ_pks
    assert ukryty_typ.pk not in typ_pks
