import random

import pytest

from bpp.tests import normalize_html

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from django.conf import settings
from model_bakery import baker

from bpp.models import Autor_Jednostka, Uczelnia
from bpp.models.autor import Autor
from bpp.views.browse import JednostkiView
from fixtures import JEDNOSTKA_PODRZEDNA, JEDNOSTKA_UCZELNI


def test_browse_jednostka_link_osadzania(jednostka, client):
    """Strona jednostki zawiera drobny link do dokumentacji widgetu osadzania
    (z prefillem slugu jednostki)."""
    res = client.get(reverse("bpp:browse_jednostka", args=(jednostka.slug,)))
    content = res.rendered_content

    assert "Osadź publikacje tej jednostki" in content
    assert "widget-publikacji" in content
    assert f"jednostka={jednostka.slug}" in content


@pytest.mark.django_db
def test_jednostka_nie_wyswietlaj_autorow_gdy_wielu(client, jednostka):
    for _n in range(settings.MAX_NO_AUTHORS_ON_BROWSE_JEDNOSTKA_PAGE + 1):
        jednostka.dodaj_autora(baker.make(Autor))

    res = client.get(reverse("bpp:browse_jednostka", args=(jednostka.slug,)))
    assert "... napisane przez" not in res.rendered_content


def test_browse_jednostka_nadrzedna(jednostka, jednostka_podrzedna, client):
    url = reverse("bpp:browse_jednostka", args=(jednostka.slug,))
    page = client.get(url)
    assert "Jednostki podrzędne" in normalize_html(page.rendered_content)

    url = reverse("bpp:browse_jednostka", args=(jednostka_podrzedna.slug,))
    page = client.get(url)
    assert "Wchodzi w skład" in normalize_html(page.rendered_content)


@pytest.mark.django_db
def test_browse_jednostka_paginate_by(uczelnia: Uczelnia):
    j = JednostkiView()
    assert j.get_paginate_by(None) == uczelnia.ilosc_jednostek_na_strone

    ile = random.randint(10, 10000)
    uczelnia.ilosc_jednostek_na_strone = ile
    uczelnia.save()
    assert j.get_paginate_by(None) == ile


def test_browse_jednostka_sortowanie(jednostka, jednostka_podrzedna, uczelnia, client):
    jednostka.nazwa = "Z jednostka"
    jednostka.save()

    jednostka_podrzedna.nazwa = "A jednostka"
    jednostka_podrzedna.save()

    uczelnia.sortuj_jednostki_alfabetycznie = True
    uczelnia.save()

    url = reverse("bpp:browse_jednostki")
    page = client.get(url)
    idx1 = page.rendered_content.find("A jednostka")
    idx2 = page.rendered_content.find("Z jednostka")

    assert idx1 < idx2

    uczelnia.sortuj_jednostki_alfabetycznie = False
    uczelnia.save()
    page = client.get(url)

    idx1 = page.rendered_content.find("A jednostka")
    idx2 = page.rendered_content.find("Z jednostka")
    assert idx1 > idx2


def test_browse_jednostka_nadrzedna_tekst(jednostka_podrzedna, jednostka, client):
    url = reverse("bpp:browse_jednostka", args=(jednostka.slug,))
    res = client.get(url)
    assert "Jednostki podrzędne:" in normalize_html(res.rendered_content)

    url = reverse("bpp:browse_jednostka", args=(jednostka_podrzedna.slug,))
    res = client.get(url)
    assert "Jednostki podrzędne:" not in normalize_html(res.rendered_content)


def test_browse_pokazuj_tylko_jednostki_nadrzedne_nie(
    jednostka_podrzedna, jednostka, client, uczelnia
):
    url = reverse("bpp:browse_jednostki")
    res = client.get(url)
    assert JEDNOSTKA_UCZELNI in normalize_html(res.rendered_content)
    assert JEDNOSTKA_PODRZEDNA in normalize_html(res.rendered_content)


def test_browse_pokazuj_tylko_jednostki_nadrzedne_tak(uczelnia, client, db):
    # Faza B (#438): po retargecie fixture ``jednostka`` wisi pod ukrytym
    # węzłem-lustrem (nie jest top-level). Filtr „tylko nadrzędne" = ``parent
    # IS NULL``, więc budujemy jawnie widoczną jednostkę top-level + dziecko.
    from bpp.tests.util import any_jednostka

    top = any_jednostka(nazwa="Jednostka Nadrzędna T", wydzial=None, uczelnia=uczelnia)
    any_jednostka(nazwa="Jednostka Podrzędna T", uczelnia=uczelnia, parent=top)

    uczelnia.pokazuj_tylko_jednostki_nadrzedne = True
    uczelnia.save()

    url = reverse("bpp:browse_jednostki")
    res = client.get(url)
    content = normalize_html(res.rendered_content)
    assert "Jednostka Nadrzędna T" in content
    assert "Jednostka Podrzędna T" not in content


@pytest.mark.parametrize("arg_res", [True, False])
def test_jednostka_pokazuj_opis(jednostka, client, arg_res):
    TESTSTR = "opis=foobar"
    jednostka.pokazuj_opis = arg_res
    jednostka.opis = TESTSTR
    jednostka.save()

    url = reverse("bpp:browse_jednostka", args=(jednostka.slug,))
    res = client.get(url)
    result = TESTSTR in normalize_html(res.rendered_content)
    assert result is arg_res


def test_browse_jednostka_styl_wydzialu_uklad_dawnego_wydzial_html(uczelnia, client):
    """Faza B (#438): strona w stylu wydziału (rodzaj z flagą
    ``pokazuj_strukture_podjednostek``) odtwarza układ dawnego wydzial.html:
    panel ``modern-header`` z nazwą i statami W ŚRODKU panelu, pod panelem
    wyśrodkowany przycisk „Pokaż wszystkie publikacje", dalej sekcje
    strukturalne. Węzeł-korzeń wysyła krótki POST ``wydzial=pk`` (jak dawny
    wydzial.html) zamiast listy wszystkich potomków. Karty hierarchii
    „Wchodzi w skład" / „Jednostki podrzędne" pozostają ukryte — strukturę
    pokazują sekcje. Na zwykłej jednostce bez zmian (patrz
    ``test_browse_jednostka_nadrzedna``)."""
    from bpp.models import RodzajJednostki
    from bpp.tests.util import any_jednostka

    rodzaj_wydzial = RodzajJednostki.objects.get(nazwa="Wydział")

    # Wydział jako korzeń drzewa, z dwiema podjednostkami (>1, żeby
    # JednostkaView nie przeskoczył redirectem na jedyną podjednostkę).
    wydzial = any_jednostka(
        nazwa="Wydział Testowy WZ",
        uczelnia=uczelnia,
        wydzial=None,
        parent=None,
        rodzaj=rodzaj_wydzial,
    )
    dziecko = any_jednostka(
        nazwa="Katedra Pierwsza WZ",
        uczelnia=uczelnia,
        wydzial=None,
        parent=wydzial,
        aktualna=True,
        widoczna=True,
    )
    any_jednostka(
        nazwa="Katedra Druga WZ",
        uczelnia=uczelnia,
        wydzial=None,
        parent=wydzial,
        aktualna=True,
        widoczna=True,
    )

    url = reverse("bpp:browse_jednostka", args=(wydzial.slug,))
    content = normalize_html(client.get(url).rendered_content)

    # Karty hierarchii nadal ukryte:
    assert "Wchodzi w skład" not in content
    assert "Jednostki podrzędne" not in content

    # Panel nagłówka jak w dawnym wydzial.html, staty w środku panelu,
    # przycisk dopiero pod panelem:
    idx_header = content.find("modern-header")
    idx_stats = content.find("wydzial-stats")
    idx_przycisk = content.find("Pokaż wszystkie publikacje")
    assert idx_header != -1
    assert idx_stats != -1
    assert idx_przycisk != -1
    assert idx_header < idx_stats < idx_przycisk

    # Korzeń drzewa: krótki POST ``wydzial=pk`` jak w dawnym wydzial.html,
    # bez wyliczania wszystkich potomków (mega-długi formularz multiseeka):
    assert f'name="wydzial" value="{wydzial.pk}"' in content
    assert 'name="jednostka"' not in content

    # ...a sekcja strukturalna dalej renderuje podjednostki:
    assert dziecko.nazwa in content


def test_browse_jednostka_styl_wydzialu_nie_korzen_fallback_jednostki(
    uczelnia, client
):
    """Węzeł w stylu wydziału położony GŁĘBIEJ w drzewie (ma rodzica) nie
    może użyć POST ``wydzial=pk`` — ``WydzialQueryObject.value_from_web``
    rozwiązuje wyłącznie korzenie (``parent IS NULL``), a denorm
    ``jednostka.wydzial`` wskazuje korzeń całego drzewa, nie ten węzeł.
    Przycisk wysyła wtedy jawną listę: jednostkę + wszystkich potomków."""
    from bpp.models import RodzajJednostki
    from bpp.tests.util import any_jednostka

    rodzaj_wydzial = RodzajJednostki.objects.get(nazwa="Wydział")

    nadrzedna = any_jednostka(
        nazwa="Jednostka nadrzędna NK", uczelnia=uczelnia, wydzial=None, parent=None
    )
    wydzial = any_jednostka(
        nazwa="Wydział Zagnieżdżony NK",
        uczelnia=uczelnia,
        wydzial=None,
        parent=nadrzedna,
        rodzaj=rodzaj_wydzial,
    )
    dziecko = any_jednostka(
        nazwa="Katedra Zagnieżdżona Pierwsza NK",
        uczelnia=uczelnia,
        wydzial=None,
        parent=wydzial,
        aktualna=True,
        widoczna=True,
    )
    dziecko2 = any_jednostka(
        nazwa="Katedra Zagnieżdżona Druga NK",
        uczelnia=uczelnia,
        wydzial=None,
        parent=wydzial,
        aktualna=True,
        widoczna=True,
    )

    url = reverse("bpp:browse_jednostka", args=(wydzial.slug,))
    content = normalize_html(client.get(url).rendered_content)

    assert "Wchodzi w skład" not in content
    assert 'name="wydzial"' not in content
    for pk in (wydzial.pk, dziecko.pk, dziecko2.pk):
        assert f'name="jednostka" value="{pk}"' in content


def test_browse_jednostka_zwykla_ma_przycisk_pokaz_wszystkie(jednostka, client):
    """Na zwykłej jednostce (rodzaj bez ``pokazuj_strukture_podjednostek``)
    przycisk „Pokaż wszystkie publikacje" jest widoczny."""
    url = reverse("bpp:browse_jednostka", args=(jednostka.slug,))
    content = normalize_html(client.get(url).rendered_content)
    assert "Pokaż wszystkie publikacje" in content


def test_jednostka_aktualni_pracownicy(
    jednostka, autor_jan_nowak, autor_jan_kowalski, wydawnictwo_ciagle, client
):
    # Kowalski to obecny pracownik
    Autor_Jednostka.objects.create(
        autor=autor_jan_kowalski, jednostka=jednostka, podstawowe_miejsce_pracy=True
    )

    # Nowak to osoba ktora wczesniej miala publikacje
    wydawnictwo_ciagle.dodaj_autora(autor=autor_jan_nowak, jednostka=jednostka)
    Autor_Jednostka.objects.filter(autor=autor_jan_nowak).delete()

    url = reverse("bpp:browse_jednostka", args=(jednostka.slug,))
    res = client.get(url)
    html = normalize_html(res.rendered_content)
    assert "Obecni pracownicy" in html
    assert "Byli pracownicy" in html
