"""Reguły widoczności encji w eksporcie CERIF.

Najważniejszy test w tym pliku to ``test_ukryty_autor_nie_wycieka_*``.
Przełącznik ``Uczelnia.eksport_cerif_wlaczony`` jest domyślnie WŁĄCZONY,
a set ``openaire_cris_persons`` wystawia imię, nazwisko, ORCID, płeć
i historię zatrudnienia do publicznego endpointu agregowanego przez
OpenAIRE. Jedynym zabezpieczeniem jest ``Autor.pokazuj`` — i ono musi
działać na OBU drogach: przez własny set i przez encję osadzoną
w publikacji.
"""

import pytest
from django.contrib.sites.models import Site
from model_bakery import baker

from bpp.models import Jednostka, Uczelnia
from bpp.models.konferencja import Konferencja
from bpp.models.praca_doktorska import Praca_Doktorska
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.models.zrodlo import Zrodlo
from cerif_export import const
from cerif_export.cerif import publication
from cerif_export.kontekst import KontekstSerializacji
from cerif_export.providers import provider_dla_setu

NAMESPACE = "cerif.example.org"


def pki(provider, uczelnia):
    obiekty, _ = provider.strona(uczelnia, rozmiar=1000)
    return {o.pk for o in obiekty}


def zserializuj(uczelnia, rekord):
    """Zserializuj publikację w kontekście zbudowanym przez provider."""
    provider = provider_dla_setu(const.SET_PUBLICATIONS)
    obiekty, _ = provider.strona(uczelnia, rozmiar=1000)
    swiezy = next(o for o in obiekty if o.pk == rekord.pk and type(o) is type(rekord))
    kontekst = KontekstSerializacji(
        namespace=NAMESPACE,
        uczelnia=uczelnia,
        widoczne=provider.zbiory_widocznosci(uczelnia, obiekty),
    )
    return publication.serializuj(swiezy, kontekst)


# -- OSOBY: wyciek danych osobowych --------------------------------------


@pytest.mark.django_db
def test_ukryty_autor_nie_wychodzi_w_secie_persons(uczelnia, fabryka_autorow):
    widoczny = fabryka_autorow("Widoczny", pokazuj=True)
    ukryty = fabryka_autorow("Ukryty", pokazuj=False)

    obecni = pki(provider_dla_setu(const.SET_PERSONS), uczelnia)

    assert widoczny.pk in obecni
    assert ukryty.pk not in obecni, "autor z pokazuj=False trafił do eksportu"


@pytest.mark.django_db
def test_ukryty_autor_nie_wycieka_jako_id_w_publikacji(
    uczelnia, fabryka_autorow, fabryka_wydawnictw
):
    """Druga droga wycieku: encja osadzona w ``Publication/Authors``.

    Profil pozwala osadzić osobę bez identyfikatora, więc nazwisko może się
    pojawić w opisie bibliograficznym — ale ``@id`` wskazywałoby rekord,
    którego w secie ``persons`` nie ma. To i psuje integralność
    referencyjną, i publikuje powiązanie, którego autor sobie nie życzy.
    """
    ukryty = fabryka_autorow("Ukryty", pokazuj=False)
    rekord = fabryka_wydawnictw(Wydawnictwo_Ciagle, autor=ukryty)

    element = zserializuj(uczelnia, rekord)

    identyfikatory_osob = [
        el.get("id")
        for el in element.iter()
        if el.tag.endswith("}Person") or el.tag == "Person"
    ]
    assert identyfikatory_osob, "autor w ogóle nie został osadzony"
    assert all(x is None for x in identyfikatory_osob), (
        f"ukryty autor wyciekł jako @id: {identyfikatory_osob}"
    )


@pytest.mark.django_db
def test_widoczny_autor_dostaje_id_w_publikacji(
    uczelnia, fabryka_autorow, fabryka_wydawnictw
):
    """Kontrola pozytywna — inaczej test wycieku przechodziłby na pusto."""
    autor = fabryka_autorow("Widoczny", pokazuj=True)
    rekord = fabryka_wydawnictw(Wydawnictwo_Ciagle, autor=autor)

    element = zserializuj(uczelnia, rekord)

    identyfikatory_osob = [
        el.get("id")
        for el in element.iter()
        if el.tag.endswith("}Person") or el.tag == "Person"
    ]
    assert any(x and x.endswith(f"au-{autor.pk}") for x in identyfikatory_osob)


@pytest.mark.django_db
def test_autor_bez_powiazania_z_uczelnia_nie_wychodzi(uczelnia, fabryka_autorow):
    """Autor spoza uczelni nie jest „nasz" — nie eksportujemy go."""
    obcy = fabryka_autorow("Obcy", pokazuj=True, powiaz=False)

    assert obcy.pk not in pki(provider_dla_setu(const.SET_PERSONS), uczelnia)


@pytest.mark.django_db
def test_autor_innego_tenanta_nie_wychodzi(uczelnia, fabryka_autorow):
    """Wielotenantowość: autor z drugiej uczelni nie może wyjść w naszym
    eksporcie, bo identyfikatory OAI byłyby fałszywie atrybuowane."""
    from bpp.models import Autor_Jednostka

    inne_site = Site.objects.create(domain="inna.example.org", name="inna")
    inna = Uczelnia.objects.create(nazwa="Inna", skrot="INN", site=inne_site)
    jednostka_obca = Jednostka.objects.create(nazwa="Obca", skrot="OBC", uczelnia=inna)
    obcy = baker.make("bpp.Autor", nazwisko="Obcy", imiona="Jan", pokazuj=True)
    Autor_Jednostka.objects.create(autor=obcy, jednostka=jednostka_obca)

    assert obcy.pk not in pki(provider_dla_setu(const.SET_PERSONS), uczelnia)


# -- JEDNOSTKI ------------------------------------------------------------


@pytest.mark.django_db
def test_jednostka_niewidoczna_nie_wychodzi(uczelnia, jednostka):
    ukryta = Jednostka.objects.create(
        nazwa="Ukryta", skrot="UKR", uczelnia=uczelnia, widoczna=False
    )
    obecne = pki(provider_dla_setu(const.SET_ORGUNITS), uczelnia)

    assert jednostka.pk in obecne
    assert ukryta.pk not in obecne


@pytest.mark.django_db
def test_jednostka_z_opt_out_nie_wychodzi(uczelnia, jednostka):
    jednostka.nie_eksportuj_przez_api = True
    jednostka.save()

    assert jednostka.pk not in pki(provider_dla_setu(const.SET_ORGUNITS), uczelnia)


# -- PUBLIKACJE -----------------------------------------------------------


@pytest.mark.django_db
def test_wydawnictwo_z_ukrytym_statusem_nie_wychodzi(
    uczelnia, fabryka_autorow, fabryka_wydawnictw, status_ok
):
    """Kanał ``cerif`` jest niezależny od kanału ``api``."""
    autor = fabryka_autorow()
    rekord = fabryka_wydawnictw(Wydawnictwo_Ciagle, autor=autor)
    provider = provider_dla_setu(const.SET_PUBLICATIONS)

    assert rekord.pk in pki(provider, uczelnia)

    uczelnia.ukryj_status_korekty_set.create(status_korekty=status_ok, cerif=True)

    assert rekord.pk not in pki(provider, uczelnia)


@pytest.mark.django_db
def test_wydawnictwo_z_opt_out_nie_wychodzi(
    uczelnia, fabryka_autorow, fabryka_wydawnictw
):
    autor = fabryka_autorow()
    rekord = fabryka_wydawnictw(
        Wydawnictwo_Zwarte, autor=autor, nie_eksportuj_przez_api=True
    )

    assert rekord.pk not in pki(provider_dla_setu(const.SET_PUBLICATIONS), uczelnia)


@pytest.mark.django_db
def test_praca_dyplomowa_respektuje_opt_out(
    uczelnia, jednostka, fabryka_autorow, status_ok
):
    """Regresja: ``Praca_Doktorska`` MA ``nie_eksportuj_przez_api``.

    Provider początkowo tego nie filtrował, bo specyfikacja twierdziła
    (błędnie), że pole siedzi tylko na wydawnictwach i patentach. Praca
    oznaczona jako niepubliczna szła wtedy prosto do OpenAIRE.
    """
    pola = {f.name for f in Praca_Doktorska._meta.get_fields()}
    assert "nie_eksportuj_przez_api" in pola

    widoczna = baker.make(
        Praca_Doktorska,
        jednostka=jednostka,
        autor=fabryka_autorow("Doktorant"),
        status_korekty=status_ok,
        rok=2020,
        nie_eksportuj_przez_api=False,
    )
    ukryta = baker.make(
        Praca_Doktorska,
        jednostka=jednostka,
        autor=fabryka_autorow("Tajny"),
        status_korekty=status_ok,
        rok=2020,
        nie_eksportuj_przez_api=True,
    )

    obecne = pki(provider_dla_setu(const.SET_PUBLICATIONS), uczelnia)

    assert widoczna.pk in obecne
    assert ukryta.pk not in obecne


# -- SŁOWNIKI WSPÓŁDZIELONE ----------------------------------------------


@pytest.mark.django_db
def test_zrodlo_wychodzi_tylko_gdy_uzywane(
    uczelnia, fabryka_autorow, fabryka_wydawnictw
):
    """``Zrodlo`` nie ma FK do uczelni ani opt-outu.

    Bez warunku „wskazywane przez widoczną publikację" każdy tenant
    wyeksportowałby cały współdzielony słownik czasopism jako własny.
    """
    uzywane = baker.make(Zrodlo, nazwa="Uzywane", skrot="Uz.")
    nieuzywane = baker.make(Zrodlo, nazwa="Nieuzywane", skrot="Nie.")
    fabryka_wydawnictw(Wydawnictwo_Ciagle, autor=fabryka_autorow(), zrodlo=uzywane)

    obecne = pki(provider_dla_setu(const.SET_PUBLICATIONS), uczelnia)

    assert uzywane.pk in obecne
    assert nieuzywane.pk not in obecne


@pytest.mark.django_db
def test_konferencja_wychodzi_tylko_gdy_uzywana(
    uczelnia, fabryka_autorow, fabryka_wydawnictw
):
    uzywana = baker.make(Konferencja, nazwa="Uzywana", skrocona_nazwa="Uz")
    nieuzywana = baker.make(Konferencja, nazwa="Nieuzywana", skrocona_nazwa="Nie")
    fabryka_wydawnictw(Wydawnictwo_Ciagle, autor=fabryka_autorow(), konferencja=uzywana)

    obecne = pki(provider_dla_setu(const.SET_EVENTS), uczelnia)

    assert uzywana.pk in obecne
    assert nieuzywana.pk not in obecne
