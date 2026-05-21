"""Testy dla ``znajdz_kandydatow_autora`` — discovery API zwracającego
listę kandydatów z rankingiem, używane przez wizard importera publikacji
gdy chce pokazać użytkownikowi kilku potencjalnych autorów do wyboru.

Filozofia: discovery (lista, z najlepszym pierwszym) jest oddzielone od
picking (wybór jednoznacznego). ``matchuj_autora`` to thin wrapper nad
tym API i wciąż zwraca pojedynczego Autora lub None.

Strategie i ich pewnosc:
- 1.00 — iexact pełne imiona + nazwisko
- 0.95 — iexact pierwsze imię + nazwisko
- 0.85 — PL↔EN (warianty v↔w + klastry + Unaccent nazwiska)

Brak strategii "tylko nazwisko bez imienia" — żeby uniknąć N Kowalskich
z różnymi imionami w wynikach.
"""

import pytest
from model_bakery import baker

from bpp.models import Autor
from import_common.core import matchuj_autora


@pytest.fixture
def kandydat_autora_cls():
    """Załadowany dataclass KandydatAutora — pojedyncze miejsce importu."""
    from import_common.core import KandydatAutora

    return KandydatAutora


@pytest.fixture
def znajdz_fn():
    """Pojedyncze miejsce importu funkcji discovery."""
    from import_common.core import znajdz_kandydatow_autora

    return znajdz_kandydatow_autora


# ---------------------------------------------------------------------------
# Strategie matchingu
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_pusta_baza_zwraca_pusta_liste(znajdz_fn):
    assert znajdz_fn("Jan", "Kowalski") == []


@pytest.mark.django_db
def test_exact_match_pewnosc_1(znajdz_fn):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    kandydaci = znajdz_fn("Jan", "Kowalski")
    assert len(kandydaci) == 1
    assert kandydaci[0].autor == autor
    assert kandydaci[0].pewnosc == 1.0
    assert kandydaci[0].powod == "iexact"


@pytest.mark.django_db
def test_pierwsze_imie_match_pewnosc_095(znajdz_fn):
    """Szukamy 'Jan', w bazie 'Jan Adam' — strategia iexact pierwsze imię."""
    autor = baker.make(Autor, imiona="Jan Adam", nazwisko="Kowalski")
    kandydaci = znajdz_fn("Jan", "Kowalski")
    assert len(kandydaci) == 1
    assert kandydaci[0].autor == autor
    assert kandydaci[0].pewnosc == 0.95
    assert kandydaci[0].powod == "iexact_pierwsze_imie"


@pytest.mark.django_db
def test_pl_en_variants_pewnosc_085(znajdz_fn):
    """Eva ↔ Ewa + Marańda ↔ Maranda przez Unaccent."""
    autor = baker.make(Autor, imiona="Ewa", nazwisko="Marańda")
    kandydaci = znajdz_fn("Eva", "Maranda")
    assert len(kandydaci) == 1
    assert kandydaci[0].autor == autor
    assert kandydaci[0].pewnosc == 0.85
    assert kandydaci[0].powod == "polish_english"


@pytest.mark.django_db
def test_inne_imie_bez_pl_en_pomijane(znajdz_fn):
    """Brak strategii 'tylko nazwisko' — Edward Maranda nie pasuje do Eva Maranda.

    Reguła użytkownika: musi się zgadzać przynajmniej imię w jakiejś formie
    (iexact, pierwsze imię iexact, albo wariant PL↔EN). 'Edward' nie ma
    wariantów wspólnych z 'Eva' → brak kandydata.
    """
    baker.make(Autor, imiona="Edward", nazwisko="Maranda")
    assert znajdz_fn("Eva", "Maranda") == []


@pytest.mark.django_db
def test_imie_z_inna_pierwsza_litera_bez_klastra_pomijane(znajdz_fn):
    """Anna ≠ Eva — różne pierwsze litery, brak klastra → pusta lista."""
    baker.make(Autor, imiona="Anna", nazwisko="Kowalska")
    assert znajdz_fn("Eva", "Kowalska") == []


# ---------------------------------------------------------------------------
# Ranking i sortowanie
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_sort_pewnosc_desc(znajdz_fn):
    """Wyższa pewność idzie pierwsza."""
    # 1.0 - exact "Jan Kowalski"
    exact = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    # 0.95 - "Jan Adam Kowalski" — szukamy "Jan"
    first_only = baker.make(Autor, imiona="Jan Adam", nazwisko="Kowalski")

    kandydaci = znajdz_fn("Jan", "Kowalski")
    assert len(kandydaci) == 2
    assert kandydaci[0].autor == exact
    assert kandydaci[1].autor == first_only
    assert kandydaci[0].pewnosc > kandydaci[1].pewnosc


@pytest.mark.django_db
def test_sort_orcid_przed_brakiem(znajdz_fn):
    """Przy równej pewności — autor z ORCID przed autorem bez."""
    bez_orcid = baker.make(Autor, imiona="Ewa", nazwisko="Marańda", orcid="")
    z_orcid = baker.make(
        Autor, imiona="Ewa", nazwisko="Maranda", orcid="0000-0001-2345-6789"
    )

    kandydaci = znajdz_fn("Eva", "Maranda")
    # Oba wpadają przez PL↔EN (pewnosc=0.85), ORCID rozstrzyga
    assert len(kandydaci) == 2
    assert kandydaci[0].autor == z_orcid
    assert kandydaci[1].autor == bez_orcid


@pytest.mark.django_db
def test_sort_liczba_publikacji_desc(znajdz_fn):
    """Przy równej pewności i braku ORCID — więcej publikacji = wyżej."""
    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor

    malo_publikacji = baker.make(Autor, imiona="Ewa", nazwisko="Marańda")
    duzo_publikacji = baker.make(Autor, imiona="Ewa", nazwisko="Maranda")

    # 1 publikacja dla mało, 3 dla dużo
    pub_a = baker.make(Wydawnictwo_Ciagle)
    baker.make(Wydawnictwo_Ciagle_Autor, autor=malo_publikacji, rekord=pub_a)
    for _ in range(3):
        pub_b = baker.make(Wydawnictwo_Ciagle)
        baker.make(Wydawnictwo_Ciagle_Autor, autor=duzo_publikacji, rekord=pub_b)

    kandydaci = znajdz_fn("Eva", "Maranda")
    assert len(kandydaci) == 2
    assert kandydaci[0].autor == duzo_publikacji
    assert kandydaci[0].publikacji == 3
    assert kandydaci[1].autor == malo_publikacji
    assert kandydaci[1].publikacji == 1


@pytest.mark.django_db
def test_max_wyniki_obcina_liste(znajdz_fn):
    """Limit max_wyniki — nie zwracamy nieograniczonej listy."""
    for i in range(5):
        baker.make(Autor, imiona=f"Ewa {i}", nazwisko="Maranda")
    baker.make(Autor, imiona="Ewa", nazwisko="Marańda")  # +1 przez PL↔EN

    kandydaci = znajdz_fn("Ewa", "Marańda", max_wyniki=3)
    assert len(kandydaci) == 3


@pytest.mark.django_db
def test_deduplikacja_po_pk_najwyzsza_pewnosc(znajdz_fn):
    """Autor wpadający w wiele strategii zwracany raz, z najwyższą pewnością.

    'Jan Kowalski' jest exact (1.0) ORAZ pierwsze imię (0.95) ORAZ
    PL↔EN match self (Jan↔Jan, 0.85). Powinien zwrócić się 1 raz z 1.0.
    """
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    kandydaci = znajdz_fn("Jan", "Kowalski")
    assert len(kandydaci) == 1
    assert kandydaci[0].autor == autor
    assert kandydaci[0].pewnosc == 1.0


# ---------------------------------------------------------------------------
# Case z zgłoszenia: Lech-Maranda
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_case_lech_maranda_dwoch_kandydatow(znajdz_fn):
    """Reprodukcja zgłoszenia: 2 autorów w bazie, CrossRef daje 'Eva Lech-Maranda'."""
    z_diakrytykiem = baker.make(Autor, imiona="Ewa", nazwisko="Lech-Marańda")
    bez_diakrytyku = baker.make(Autor, imiona="Ewa", nazwisko="Lech-Maranda")

    kandydaci = znajdz_fn("Eva", "Lech-Maranda")
    autorzy = {k.autor for k in kandydaci}
    assert autorzy == {z_diakrytykiem, bez_diakrytyku}
    # Każdy ma pewność 0.85 (PL↔EN przez v↔w + Unaccent)
    assert all(k.pewnosc == 0.85 for k in kandydaci)


# ---------------------------------------------------------------------------
# BC: matchuj_autora jako thin wrapper
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_matchuj_autora_jeden_kandydat_zwraca_autora():
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    assert matchuj_autora("Jan", "Kowalski") == autor


@pytest.mark.django_db
def test_matchuj_autora_ambiguity_zwraca_none():
    """BC: gdy ≥2 kandydatów, zwraca None (decyzja w UI)."""
    baker.make(Autor, imiona="Ewa", nazwisko="Lech-Marańda")
    baker.make(Autor, imiona="Ewa", nazwisko="Lech-Maranda")
    assert matchuj_autora("Eva", "Lech-Maranda") is None


@pytest.mark.django_db
def test_matchuj_autora_jednostka_nie_jest_hard_filtrem():
    """BC: jednostka nie wyklucza autorów którzy nie mają aktualna_jednostka.

    Stary kod: jeden Jan Kowalski (aktualna_jednostka=None) + jednostka=j1 →
    zwracał autora (jednostka jako disambiguator, nie hard filter). Nowy
    thin wrapper musi zachować to zachowanie.
    """
    from bpp.models import Jednostka

    j1 = baker.make(Jednostka)
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    # aktualna_jednostka domyślnie None, brak historycznego przypisania
    assert autor.aktualna_jednostka is None

    assert matchuj_autora("Jan", "Kowalski", jednostka=j1) == autor


@pytest.mark.django_db
def test_matchuj_autora_tytul_jako_disambiguator():
    """BC: gdy 2 homonimów z różnymi tytułami — tytul_str rozstrzyga.

    Stary kod używał ``Q(tytul__skrot=tytul_str)`` jako filtra w
    ``_try_match_autor_by_name`` żeby rozróżnić "Jan Kowalski dr" od
    "Jan Kowalski prof". Thin wrapper musi to zachować przez
    disambiguator.
    """
    from bpp.models import Tytul

    foo, _ = Tytul.objects.get_or_create(
        nazwa="test-tyt-foo", defaults={"skrot": "foo-skr"}
    )
    bar, _ = Tytul.objects.get_or_create(
        nazwa="test-tyt-bar", defaults={"skrot": "bar-skr"}
    )

    a_foo = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", tytul=foo)
    baker.make(Autor, imiona="Jan", nazwisko="Kowalski", tytul=bar)

    assert matchuj_autora("Jan", "Kowalski", tytul_str="foo-skr") == a_foo


# ---------------------------------------------------------------------------
# KandydatAutora dataclass
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_kandydat_autora_pola(kandydat_autora_cls):
    """Dataclass ma wymagane pola."""
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    k = kandydat_autora_cls(
        autor=autor, pewnosc=0.85, powod="polish_english", publikacji=5
    )
    assert k.autor == autor
    assert k.pewnosc == 0.85
    assert k.powod == "polish_english"
    assert k.publikacji == 5
