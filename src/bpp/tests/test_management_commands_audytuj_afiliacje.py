"""#438: komenda ``audytuj_afiliacje_jednostek`` — raportuje (i opcjonalnie
naprawia) wiersze przypisań autorów z ``afiliuje=True`` wskazujące jednostki,
których rodzaj nie dopuszcza afiliacji (np. węzły-lustra „Wydział" po
konwersji ``konwertuj_wydzialy_na_jednostki``).

Symulacja „danych zastanych": wiersz tworzony jest na zwykłej jednostce (wtedy
walidacja przechodzi), a dopiero potem jednostka zmienia rodzaj na „Wydział" —
dokładnie tak, jak dzieje się to przy konwersji istniejącej bazy.
"""

from io import StringIO

import pytest
from django.core.management import call_command

from bpp.models import RodzajJednostki


def _zepsuj_afiliacje(wa, jednostka):
    """Uczyń istniejący (poprawny) wiersz „błędnym": jednostka staje się
    wydziałem, choć wiersz ma ``afiliuje=True``."""
    jednostka.rodzaj = RodzajJednostki.objects.get(nazwa="Wydział")
    jednostka.save()


@pytest.mark.django_db
def test_audyt_raportuje_bledny_wiersz(wydawnictwo_ciagle, autor_jan_nowak, jednostka):
    wa = wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka, afiliuje=True)
    _zepsuj_afiliacje(wa, jednostka)

    out = StringIO()
    call_command("audytuj_afiliacje_jednostek", stdout=out)
    output = out.getvalue()

    assert "Wydawnictwo_Ciagle_Autor" in output
    # bez --napraw wiersz zostaje nietknięty
    wa.refresh_from_db()
    assert wa.afiliuje is True


@pytest.mark.django_db
def test_audyt_z_naprawa_odznacza_afiliuje(
    wydawnictwo_ciagle, autor_jan_nowak, jednostka
):
    wa = wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka, afiliuje=True)
    _zepsuj_afiliacje(wa, jednostka)

    call_command("audytuj_afiliacje_jednostek", "--napraw")

    wa.refresh_from_db()
    assert wa.afiliuje is False


@pytest.mark.django_db
def test_audyt_czysto_gdy_brak_bledow(wydawnictwo_ciagle, autor_jan_nowak, jednostka):
    # Poprawny wiersz na zwykłej jednostce — audyt nie zgłasza problemów.
    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka, afiliuje=True)

    out = StringIO()
    call_command("audytuj_afiliacje_jednostek", stdout=out)

    assert "Brak" in out.getvalue()
