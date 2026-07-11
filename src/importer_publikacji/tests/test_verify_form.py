"""Testy ``VerifyForm.charakter_formalny`` — pułapka D/H/PAT.

``VerifyForm`` filtruje ``charakter_formalny`` tylko po ``ukryty=False``
(fixtures/charakter_formalny.json: D/H/PAT mają ``ukryty=None``, czyli
falsy — więc dziś SĄ widoczne i wybieralne). Operator mógł wybrać "Patent"
dla rekordu, który i tak wyląduje jako Wydawnictwo_Ciagle/Zwarte (dispatch
w _create_publication idzie po jest_wydawnictwem_zwartym, nie po
charakter_formalny) — powstawał zmieszany, mislabelowany rekord, który
utykał w adminie (ZapobiegajNiewlasciwymCharakterom.clean_fields() blokuje
D/H/PAT, ale tylko przez full_clean(), które importer omija używając
.objects.create()). Fix: wyklucz D/H/PAT z queryseta formularza — to samo,
co robiłby model-level guard, gdyby importer go wołał.
"""

import pytest

from bpp.models import Charakter_Formalny
from importer_publikacji.forms import VerifyForm


@pytest.mark.django_db
def test_verify_form_excludes_patent_charakter(charaktery_formalne):
    form = VerifyForm()
    skroty = set(
        form.fields["charakter_formalny"].queryset.values_list("skrot", flat=True)
    )
    assert "PAT" not in skroty


@pytest.mark.django_db
def test_verify_form_excludes_doktorska_i_habilitacyjna(charaktery_formalne):
    form = VerifyForm()
    skroty = set(
        form.fields["charakter_formalny"].queryset.values_list("skrot", flat=True)
    )
    assert "D" not in skroty
    assert "H" not in skroty


@pytest.mark.django_db
def test_verify_form_still_offers_normal_charaktery(charaktery_formalne):
    """Fix nie powinien wyciąć zwykłych, poprawnych charakterów (regresja)."""
    form = VerifyForm()
    skroty = set(
        form.fields["charakter_formalny"].queryset.values_list("skrot", flat=True)
    )
    assert "AC" in skroty


@pytest.mark.django_db
def test_verify_form_invalid_with_pat_charakter(charaktery_formalne, jezyki, typy_kbn):
    """Pułapka nie jest już wybieralna nawet gdyby ktoś sfałszował POST —
    'PAT' nie ma być valid choice."""
    from bpp.models import Jezyk, Typ_KBN

    pat = Charakter_Formalny.objects.get(skrot="PAT")
    tk = Typ_KBN.objects.first()
    jez = Jezyk.objects.filter(widoczny=True).first()

    form = VerifyForm(
        data={
            "rodzaj_rekordu": "ciagle",
            "charakter_formalny": pat.pk,
            "typ_kbn": tk.pk if tk else "",
            "jezyk": jez.pk if jez else "",
            "rok": "2024",
        }
    )
    assert not form.is_valid()
    assert "charakter_formalny" in form.errors


@pytest.mark.django_db
def test_verify_form_patent_valid_without_charakter_typ_jezyk(
    charaktery_formalne, jezyki, typy_kbn
):
    """Tryb PATENT nie wymaga charakter_formalny/typ_kbn/jezyk (Patent je
    hardkoduje / nie ma typ_kbn) — formularz waliduje z samym rokiem."""
    form = VerifyForm(
        data={
            "rodzaj_rekordu": "patent",
            "rok": "2024",
            "numer_zgloszenia": "PL123456",
        }
    )
    assert form.is_valid(), form.errors


@pytest.mark.django_db
@pytest.mark.parametrize("rodzaj", ["ciagle", "zwarte"])
def test_verify_form_nonpatent_requires_charakter_typ_jezyk(
    rodzaj, charaktery_formalne, jezyki, typy_kbn
):
    """Ciągłe/zwarte nadal wymagają charakter_formalny/typ_kbn/jezyk."""
    form = VerifyForm(data={"rodzaj_rekordu": rodzaj, "rok": "2024"})
    assert not form.is_valid()
    assert "charakter_formalny" in form.errors
    assert "typ_kbn" in form.errors
    assert "jezyk" in form.errors


@pytest.mark.django_db
def test_verify_form_wdrozenie_trojstan(charaktery_formalne, jezyki, typy_kbn):
    """NullBooleanField wdrozenie: puste→None, '2'→True, '3'→False (widget
    NullBooleanSelect koduje wartości jako 'unknown'/'true'/'false')."""
    base = {"rodzaj_rekordu": "patent", "rok": "2024"}
    f_empty = VerifyForm(data={**base, "wdrozenie": "unknown"})
    assert f_empty.is_valid(), f_empty.errors
    assert f_empty.cleaned_data["wdrozenie"] is None

    f_true = VerifyForm(data={**base, "wdrozenie": "true"})
    assert f_true.is_valid(), f_true.errors
    assert f_true.cleaned_data["wdrozenie"] is True

    f_false = VerifyForm(data={**base, "wdrozenie": "false"})
    assert f_false.is_valid(), f_false.errors
    assert f_false.cleaned_data["wdrozenie"] is False
