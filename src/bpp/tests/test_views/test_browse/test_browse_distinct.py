"""Brak zbędnego ``DISTINCT`` w publicznych widokach przeglądania.

``SELECT DISTINCT`` na ``bpp_rekord_mat`` porównuje 49 kolumn (w tym
``search_index`` typu tsvector i duże ``opis_bibliograficzny_cache``), a na
``bpp_autor`` — 29. Kosztuje to sort/hash całej tabeli: ``COUNT`` nie może
pójść index-only scanem, a ``recently_updated`` materializuje całość zanim
zadziała ``LIMIT 12``.

Deduplikacja jest potrzebna WYŁĄCZNIE tam, gdzie filtr dokłada JOIN po
relacji wielowartościowej. W ``scope_rekord_do_uczelni`` taki JOIN pojawia
się tylko w trybie multi-host — i helper sam dokłada tam ``.distinct()``.
Widoki nie mają go dokładać bezwarunkowo.

Testy dzielą się na dwie grupy:

* **siatka bezpieczeństwa** — wyniki nie zawierają duplikatów przy danych,
  które by je wywołały, gdyby gdzieś siedział mnożący JOIN. Te testy mają
  przechodzić PRZED i PO zmianie.
* **kształt SQL** — ``queryset.query.distinct`` jest ``False``. Sprawdzamy
  flagę zapytania, nie tekst SQL-a: ``ZrodlaView`` ma legalny ``DISTINCT``
  w podzapytaniu ``pk__in=...values_list(...).distinct()``, więc szukanie
  napisu „DISTINCT" dawałoby fałszywy alarm.
"""

import pytest
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor_Jednostka, Jednostka
from bpp.views.browse import AutorzyView, JednostkiView, ZrodlaView


def _pks(iterable):
    return [obj.pk for obj in iterable]


def _bez_duplikatow(iterable):
    pks = _pks(iterable)
    return len(pks) == len(set(pks))


def _queryset_widoku(klasa, uczelnia):
    """Zbuduj queryset widoku-Browsera poza cyklem żądania.

    ``RequestFactory`` ustawia ``SERVER_NAME=testserver``, czyli dokładnie
    domenę ``Site`` z fikstury ``uczelnia`` — ``get_for_request`` odnajdzie
    więc uczelnię tak samo jak w realnym żądaniu.
    """
    view = klasa()
    view.request = RequestFactory().get("/")
    view.kwargs = {}
    view.object_list = None
    return view.get_queryset()


# ---------------------------------------------------------------------------
# Strona główna (get_uczelnia_context_data)
# ---------------------------------------------------------------------------


@pytest.fixture
def rekord_z_autorem_w_dwoch_jednostkach(
    uczelnia,
    jednostka,
    druga_jednostka,
    autor_jan_nowak,
    typy_odpowiedzialnosci,
    charaktery_formalne,
    jezyki,
    denorms,
):
    """Jeden rekord z DWOMA wierszami autorstwa — kandydat na duplikat.

    Autor jest wpisany na publikację dwa razy, raz z każdej jednostki. Każdy
    filtr idący JOIN-em przez ``autorzy`` zwróciłby ten rekord dwukrotnie.
    """
    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor
    from bpp.models.cache import Rekord

    wc = baker.make(Wydawnictwo_Ciagle)
    for kolejnosc, jedn in enumerate((jednostka, druga_jednostka)):
        baker.make(
            Wydawnictwo_Ciagle_Autor,
            rekord=wc,
            autor=autor_jan_nowak,
            jednostka=jedn,
            kolejnosc=kolejnosc,
        )

    Autor_Jednostka.objects.get_or_create(autor=autor_jan_nowak, jednostka=jednostka)
    Autor_Jednostka.objects.get_or_create(
        autor=autor_jan_nowak, jednostka=druga_jednostka
    )

    denorms.rebuildall()
    return Rekord.objects.get_for_model(wc)


@pytest.mark.django_db
def test_strona_glowna_bez_duplikatow(uczelnia, rekord_z_autorem_w_dwoch_jednostkach):
    """Siatka bezpieczeństwa: licznik i lista liczą rekord RAZ."""
    from bpp.views.browse import get_uczelnia_context_data

    get_uczelnia_context_data.invalidate()
    ctx = get_uczelnia_context_data(uczelnia)

    assert ctx["total_rekord_count"] == 1
    assert _pks(ctx["recently_updated"]) == [rekord_z_autorem_w_dwoch_jednostkach.pk]


@pytest.mark.django_db
def test_strona_glowna_bez_distinct_w_sql(
    uczelnia, client, rekord_z_autorem_w_dwoch_jednostkach
):
    """Single-host: żadne zapytanie do ``bpp_rekord_mat`` nie ma DISTINCT."""
    from cacheops import invalidate_all

    invalidate_all()

    with CaptureQueriesContext(connection) as ctx:
        res = client.get(reverse("bpp:browse_uczelnia", args=(uczelnia.slug,)))

    assert res.status_code == 200

    zapytania_mat = [
        q["sql"] for q in ctx.captured_queries if "bpp_rekord_mat" in q["sql"]
    ]
    assert zapytania_mat, "strona główna nie odpytała tabeli zmaterializowanej"
    assert not [sql for sql in zapytania_mat if "DISTINCT" in sql.upper()]


@pytest.mark.django_db
def test_scope_rekord_doklada_distinct_tylko_gdy_joinuje(uczelnia):
    """Kontrakt helpera: DISTINCT idzie w parze z JOIN-em, nie osobno."""
    from bpp.models.cache import Rekord
    from bpp.util.uczelnia_scope import scope_rekord_do_uczelni

    # single-host → no-op, bez JOIN-a i bez DISTINCT
    assert not scope_rekord_do_uczelni(Rekord.objects.all(), uczelnia).query.distinct

    # multi-host → JOIN po M2M ``autorzy`` + DISTINCT (helper dokłada sam)
    baker.make("bpp.Uczelnia", nazwa="Druga uczelnia", skrot="DU")
    assert scope_rekord_do_uczelni(Rekord.objects.all(), uczelnia).query.distinct


# ---------------------------------------------------------------------------
# AutorzyView
# ---------------------------------------------------------------------------


@pytest.fixture
def autor_z_wieloma_powiazaniami(
    uczelnia,
    jednostka,
    druga_jednostka,
    autor_jan_nowak,
    typy_odpowiedzialnosci,
    charaktery_formalne,
    jezyki,
    denorms,
):
    """Autor w dwóch jednostkach i z dwiema publikacjami.

    Gdyby filtry ``AutorzyView`` szły JOIN-em po ``autor_jednostka`` albo po
    zmaterializowanej ``bpp_autorzy_mat``, autor pojawiłby się na liście
    cztery razy.
    """
    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor

    Autor_Jednostka.objects.get_or_create(autor=autor_jan_nowak, jednostka=jednostka)
    Autor_Jednostka.objects.get_or_create(
        autor=autor_jan_nowak, jednostka=druga_jednostka
    )

    for _ in range(2):
        wc = baker.make(Wydawnictwo_Ciagle)
        baker.make(
            Wydawnictwo_Ciagle_Autor,
            rekord=wc,
            autor=autor_jan_nowak,
            jednostka=jednostka,
        )

    # Oba filtry uczelniane muszą być AKTYWNE, żeby test dotykał ścieżki
    # z Exists()/OuterRef, a nie ją omijał.
    uczelnia.pokazuj_autorow_obcych_w_przegladaniu_danych = False
    uczelnia.pokazuj_autorow_bez_prac_w_przegladaniu_danych = False
    uczelnia.save()

    denorms.rebuildall()
    return autor_jan_nowak


@pytest.mark.django_db
def test_autorzy_view_bez_duplikatow(client, uczelnia, autor_z_wieloma_powiazaniami):
    res = client.get(reverse("bpp:browse_autorzy"))

    assert res.status_code == 200
    lista = list(res.context["object_list"])
    assert _bez_duplikatow(lista)
    assert _pks(lista).count(autor_z_wieloma_powiazaniami.pk) == 1
    assert res.context["paginator"].count == 1


@pytest.mark.django_db
def test_autorzy_view_bez_duplikatow_przy_literce_i_szukaniu(
    client, uczelnia, autor_z_wieloma_powiazaniami
):
    """Obie dodatkowe ścieżki filtrowania (literka, fulltext) też nie mnożą."""
    res = client.get(reverse("bpp:browse_autorzy_literka", args=("N",)))
    assert res.status_code == 200
    assert _bez_duplikatow(res.context["object_list"])
    assert res.context["paginator"].count == 1

    res = client.get(reverse("bpp:browse_autorzy"), data={"search": "Nowak"})
    assert res.status_code == 200
    assert _bez_duplikatow(res.context["object_list"])
    assert res.context["paginator"].count == 1


@pytest.mark.django_db
def test_autorzy_view_queryset_bez_distinct(uczelnia, autor_z_wieloma_powiazaniami):
    assert not _queryset_widoku(AutorzyView, uczelnia).query.distinct


# ---------------------------------------------------------------------------
# ZrodlaView
# ---------------------------------------------------------------------------


@pytest.fixture
def zrodlo_z_wieloma_pracami(uczelnia, zrodlo, charaktery_formalne, jezyki):
    """Źródło z trzema publikacjami — kandydat na potrójny duplikat."""
    from bpp.models import Wydawnictwo_Ciagle

    for _ in range(3):
        baker.make(Wydawnictwo_Ciagle, zrodlo=zrodlo)

    # Domyślne False, ale ustawiamy jawnie: filtr ``pk__in=`` ma być aktywny.
    uczelnia.pokazuj_zrodla_bez_prac_w_przegladaniu_danych = False
    uczelnia.save()
    return zrodlo


@pytest.mark.django_db
def test_zrodla_view_bez_duplikatow(client, uczelnia, zrodlo_z_wieloma_pracami):
    res = client.get(reverse("bpp:browse_zrodla"))

    assert res.status_code == 200
    lista = list(res.context["object_list"])
    assert _bez_duplikatow(lista)
    assert _pks(lista).count(zrodlo_z_wieloma_pracami.pk) == 1


@pytest.mark.django_db
def test_zrodla_view_bez_duplikatow_przy_literce(
    client, uczelnia, zrodlo_z_wieloma_pracami
):
    res = client.get(reverse("bpp:browse_zrodla_literka", args=("T",)))

    assert res.status_code == 200
    assert _bez_duplikatow(res.context["object_list"])
    assert res.context["paginator"].count == 1


@pytest.mark.django_db
def test_zrodla_view_queryset_bez_distinct(uczelnia, zrodlo_z_wieloma_pracami):
    """Zapytanie główne bez DISTINCT — mimo DISTINCT w podzapytaniu ``pk__in``."""
    qs = _queryset_widoku(ZrodlaView, uczelnia)

    assert not qs.query.distinct
    # Premisa testu: podzapytanie faktycznie zawiera DISTINCT, więc test na
    # sam napis „DISTINCT" byłby bezużyteczny.
    assert "DISTINCT" in str(qs.query).upper()


# ---------------------------------------------------------------------------
# JednostkiView
# ---------------------------------------------------------------------------


@pytest.fixture
def jednostki_z_podjednostkami(uczelnia, jednostka, druga_jednostka):
    """Jednostki z dziećmi w drzewie MPTT i z autorami.

    Relacje ``children`` / ``autor_jednostka`` są wielowartościowe — gdyby
    filtr widoku po nich joinował, rodzic pojawiłby się wielokrotnie.
    """
    for i in range(2):
        Jednostka.objects.create(
            nazwa=f"Podjednostka {i}",
            skrot=f"PJ{i}",
            parent=jednostka,
            uczelnia=uczelnia,
        )
    return jednostka


@pytest.mark.django_db
def test_jednostki_view_bez_duplikatow(client, uczelnia, jednostki_z_podjednostkami):
    res = client.get(reverse("bpp:browse_jednostki"))

    assert res.status_code == 200
    lista = list(res.context["object_list"])
    assert _bez_duplikatow(lista)
    assert _pks(lista).count(jednostki_z_podjednostkami.pk) == 1


@pytest.mark.django_db
def test_jednostki_view_bez_duplikatow_tylko_nadrzedne(
    client, uczelnia, jednostki_z_podjednostkami
):
    """Ścieżka ``pokazuj_tylko_jednostki_nadrzedne`` również nie mnoży."""
    uczelnia.pokazuj_tylko_jednostki_nadrzedne = True
    uczelnia.save()

    res = client.get(reverse("bpp:browse_jednostki"))

    assert res.status_code == 200
    assert _bez_duplikatow(res.context["object_list"])


@pytest.mark.django_db
def test_jednostki_view_queryset_bez_distinct(uczelnia, jednostki_z_podjednostkami):
    assert not _queryset_widoku(JednostkiView, uczelnia).query.distinct


# ---------------------------------------------------------------------------
# Multi-host: deduplikacja MUSI zostać
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_multihost_strona_glowna_nadal_deduplikuje(
    uczelnia1,
    uczelnia2,
    jednostka_uczelnia1,
    autor_uczelnia1,
    typy_odpowiedzialnosci,
    charaktery_formalne,
    jezyki,
    denorms,
):
    """Multi-host: JOIN po ``autorzy`` istnieje, więc DISTINCT musi działać.

    Autor jest wpisany na publikację dwa razy (dwie jednostki tej samej
    uczelni) — bez deduplikacji licznik pokazałby 2 zamiast 1.
    """
    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor
    from bpp.views.browse import get_uczelnia_context_data

    druga = Jednostka.objects.create(
        nazwa="Druga jednostka uczelni 1",
        skrot="DJU1",
        uczelnia=uczelnia1,
    )

    wc = baker.make(Wydawnictwo_Ciagle)
    for kolejnosc, jedn in enumerate((jednostka_uczelnia1, druga)):
        baker.make(
            Wydawnictwo_Ciagle_Autor,
            rekord=wc,
            autor=autor_uczelnia1,
            jednostka=jedn,
            kolejnosc=kolejnosc,
        )

    denorms.rebuildall()

    get_uczelnia_context_data.invalidate()
    ctx = get_uczelnia_context_data(uczelnia1)

    assert ctx["total_rekord_count"] == 1
    assert _bez_duplikatow(ctx["recently_updated"])
    assert len(list(ctx["recently_updated"])) == 1


@pytest.mark.django_db
def test_multihost_streszczenia_nadal_deduplikuja(
    uczelnia1,
    uczelnia2,
    jednostka_uczelnia1,
    autor_uczelnia1,
    typy_odpowiedzialnosci,
    charaktery_formalne,
    jezyki,
    denorms,
):
    """``recent_abstracts`` joinuje przez ``rekord__autorzy_set`` (multi-host)."""
    from bpp.models import (
        Wydawnictwo_Ciagle,
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Ciagle_Streszczenie,
    )
    from bpp.views.browse import get_uczelnia_context_data

    druga = Jednostka.objects.create(
        nazwa="Druga jednostka uczelni 1",
        skrot="DJU1",
        uczelnia=uczelnia1,
    )

    wc = baker.make(Wydawnictwo_Ciagle)
    for kolejnosc, jedn in enumerate((jednostka_uczelnia1, druga)):
        baker.make(
            Wydawnictwo_Ciagle_Autor,
            rekord=wc,
            autor=autor_uczelnia1,
            jednostka=jedn,
            kolejnosc=kolejnosc,
        )
    streszczenie = baker.make(
        Wydawnictwo_Ciagle_Streszczenie,
        rekord=wc,
        streszczenie="Treść streszczenia.",
    )

    denorms.rebuildall()

    get_uczelnia_context_data.invalidate()
    ctx = get_uczelnia_context_data(uczelnia1)

    lista = list(ctx["recent_abstracts"])
    assert _pks(lista) == [streszczenie.pk]
