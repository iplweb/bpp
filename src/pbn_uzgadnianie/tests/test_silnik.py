"""Reguły operacji „Uzgodnij z PBN” (FD#477) na danych testowych.

Wywołania PBN są zamockowane (``FalszywyKlientPBN``) — klient wywraca test
przy każdym wywołaniu innym niż trzy odczyty, więc te testy pilnują też,
że uzgadnianie NICZEGO do PBN nie wysyła.
"""

import pytest
from model_bakery import baker

from bpp.models import (
    Charakter_Formalny,
    Rekord,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from pbn_api.models import Publication, PublikacjaInstytucji
from pbn_export_queue.models import PBN_Export_Queue
from pbn_uzgadnianie import silnik
from pbn_uzgadnianie.silnik import uzgodnij
from pbn_uzgadnianie.wersje import BIEZACA_BRAK_PRZYPIETEJ, PRZYPIETA
from pbn_uzgadnianie.zakres import Anulowano

from .conftest import FalszywyKlientPBN, kategorie

pytestmark = pytest.mark.django_db


def _rekord_bpp(model, jednostka, autor_pbn, **pola):
    """Rekord BPP z afiliowanym autorem uczelni, wysyłany do PBN."""
    from bpp.models import Autor

    nazwa = "Książka" if model is Wydawnictwo_Zwarte else "Artykuł w czasopismie"
    pola.setdefault("charakter_formalny", Charakter_Formalny.objects.get(nazwa=nazwa))
    rekord = baker.make(model, **pola)
    autor = Autor.objects.get(pbn_uid_id=autor_pbn())
    rekord.dodaj_autora(autor, jednostka)
    return rekord


def test_praca_tylko_w_pbn_jest_tworzona_w_bpp(klient, ksiazka_pbn, przebieg):
    klient.dodaj("pbn-nowa", ksiazka_pbn("Monografia, której nie ma w BPP"))

    wynik = uzgodnij(przebieg(), klient)

    assert kategorie(wynik) == {"pbn-nowa": silnik.UTWORZONO}
    rekord = Wydawnictwo_Zwarte.objects.get(pbn_uid_id="pbn-nowa")
    assert rekord.tytul_oryginalny == "Monografia, której nie ma w BPP"
    assert rekord.autorzy_set.count() == 1
    assert wynik.podsumowanie[silnik.UTWORZONO] == 1
    assert wynik.status == "zakonczone"


def test_idempotencja_drugie_uruchomienie_nic_nie_zmienia(
    klient, ksiazka_pbn, przebieg
):
    klient.dodaj("pbn-nowa", ksiazka_pbn("Monografia do utworzenia tylko raz"))
    uzgodnij(przebieg(), klient)

    drugi = uzgodnij(przebieg(), klient)

    assert kategorie(drugi) == {"pbn-nowa": silnik.ZGODNE}
    assert Wydawnictwo_Zwarte.objects.count() == 1
    assert drugi.podsumowanie[silnik.UTWORZONO] == 0
    assert drugi.podsumowanie[silnik.POWIAZANO] == 0


def test_rekord_bez_pbn_uid_pasujacy_po_doi_jest_wiazany_nie_dublowany(
    klient, ksiazka_pbn, przebieg, jednostka_uczelni, autor_pbn
):
    istniejacy = _rekord_bpp(
        Wydawnictwo_Zwarte,
        jednostka_uczelni,
        autor_pbn,
        tytul_oryginalny="Monografia wpisana wcześniej ręcznie w BPP",
        rok=2026,
        doi="10.1234/monografia",
        pbn_uid=None,
    )
    klient.dodaj(
        "pbn-ta-sama",
        ksiazka_pbn(
            "Monografia wpisana wcześniej ręcznie w BPP", doi="10.1234/MONOGRAFIA"
        ),
    )

    wynik = uzgodnij(przebieg(), klient)

    assert kategorie(wynik) == {"pbn-ta-sama": silnik.POWIAZANO}
    assert Wydawnictwo_Zwarte.objects.count() == 1, "powstał duplikat"
    istniejacy.refresh_from_db()
    assert istniejacy.pbn_uid_id == "pbn-ta-sama"
    # Powiązany rekord nie ląduje na liście „bez odpowiednika w PBN”.
    assert wynik.podsumowanie[silnik.TYLKO_W_BPP] == 0


def test_niepewne_dopasowanie_po_tytule_ani_nie_tworzy_ani_nie_wiaze(
    klient, ksiazka_pbn, przebieg, jednostka_uczelni, autor_pbn
):
    podobny = _rekord_bpp(
        Wydawnictwo_Zwarte,
        jednostka_uczelni,
        autor_pbn,
        tytul_oryginalny="Zarys historii medycyny w Polsce w dwudziestym wieku",
        rok=2026,
        pbn_uid=None,
    )
    klient.dodaj(
        "pbn-podobna",
        ksiazka_pbn("Zarys historii medycyny w Polsce w dwudziestym wieku"),
    )

    wynik = uzgodnij(przebieg(), klient)

    wpis = next(w for w in wynik.wynik if w.get("pbn_uid") == "pbn-podobna")
    assert wpis["kategoria"] == silnik.DO_DECYZJI
    assert wpis["bpp_pk"] == podobny.pk
    assert Wydawnictwo_Zwarte.objects.count() == 1
    podobny.refresh_from_db()
    assert podobny.pbn_uid_id is None
    # …i nadal jest wykazany wśród rekordów BPP bez powiązania — ze
    # wskazaniem pasującej pracy (jest na profilu) i dopiskiem „niepewne”.
    (bez,) = [w for w in wynik.wynik if w["kategoria"] == silnik.W_PBN_NIEPOWIAZANA]
    assert bez["pbn_uid"] == "pbn-podobna" and bez["na_profilu"] is True
    assert "niepewne" in bez["dopasowanie"]


def test_pasujacy_rekord_z_innym_pbn_uid_to_konflikt(
    klient, ksiazka_pbn, przebieg, jednostka_uczelni, autor_pbn
):
    inna = baker.make(Publication, mongoId="pbn-inna", status="ACTIVE")
    _rekord_bpp(
        Wydawnictwo_Zwarte,
        jednostka_uczelni,
        autor_pbn,
        tytul_oryginalny="Monografia zdublowana w repozytorium PBN",
        rok=2026,
        doi="10.1234/dubel",
        pbn_uid=inna,
    )
    klient.dodaj(
        "pbn-dubel",
        ksiazka_pbn("Monografia zdublowana w repozytorium PBN", doi="10.1234/dubel"),
    )

    wynik = uzgodnij(przebieg(), klient)

    assert kategorie(wynik)["pbn-dubel"] == silnik.KONFLIKT
    assert Wydawnictwo_Zwarte.objects.count() == 1


def test_praca_po_obu_stronach_rozniaca_sie_tylko_w_raporcie(
    klient, ksiazka_pbn, przebieg
):
    klient.dodaj("pbn-wspolna", ksiazka_pbn("Tytuł pierwotny", isbn="9788300000001"))
    uzgodnij(przebieg(), klient)
    # Redaktor poprawia rekord w BPP; w PBN zostaje po staremu.
    rekord = Wydawnictwo_Zwarte.objects.get(pbn_uid_id="pbn-wspolna")
    rekord.tytul_oryginalny = "Tytuł poprawiony ręcznie przez redaktora"
    rekord.save()

    wynik = uzgodnij(przebieg(), klient)

    wpis = wynik.wynik[0]
    assert wpis["kategoria"] == silnik.ROZNI_SIE
    assert [r["pole"] for r in wpis["roznice"]] == ["Tytuł"]
    rekord.refresh_from_db()
    assert rekord.tytul_oryginalny == "Tytuł poprawiony ręcznie przez redaktora", (
        "uzgadnianie nadpisało ręczną pracę redaktora"
    )


def test_praca_spoza_profilu_instytucji_nie_jest_importowana(
    klient, ksiazka_pbn, przebieg
):
    """FD#552: lokalna kopia PBN zawiera też prace obce — nie ruszamy ich."""
    obca = ksiazka_pbn("Praca innej uczelni obecna w lokalnej kopii PBN")
    klient.dodaj("pbn-obca", obca, na_profilu=False)
    baker.make(
        Publication,
        mongoId="pbn-obca",
        status="ACTIVE",
        versions=klient.publikacje["pbn-obca"]["versions"],
    )

    wynik = uzgodnij(przebieg(), klient)

    assert wynik.wynik == []
    assert not Wydawnictwo_Zwarte.objects.exists()


def test_praca_spoza_zakresu_lat_jest_pomijana(klient, ksiazka_pbn, przebieg):
    klient.dodaj("pbn-2019", ksiazka_pbn("Monografia sprzed lat", rok=2019))
    klient.dodaj("pbn-2026", ksiazka_pbn("Monografia z bieżącego roku", rok=2026))

    wynik = uzgodnij(przebieg(rok_od=2026, rok_do=2026), klient)

    assert kategorie(wynik) == {"pbn-2026": silnik.UTWORZONO}
    assert not Wydawnictwo_Zwarte.objects.filter(pbn_uid_id="pbn-2019").exists()
    # Publikacji spoza zakresu nawet nie odświeżamy.
    assert "get_publication_by_id:pbn-2019" not in klient.wywolania[2:]


def test_rekordy_bpp_bez_odpowiednika_w_pbn_sa_w_raporcie(
    klient, przebieg, jednostka_uczelni, autor_pbn
):
    _rekord_bpp(
        Wydawnictwo_Ciagle,
        jednostka_uczelni,
        autor_pbn,
        tytul_oryginalny="Artykuł znany tylko w BPP",
        rok=2026,
        pbn_uid=None,
    )
    poza = baker.make(Publication, mongoId="pbn-poza-profilem", status="ACTIVE")
    _rekord_bpp(
        Wydawnictwo_Ciagle,
        jednostka_uczelni,
        autor_pbn,
        tytul_oryginalny="Artykuł w PBN, ale nie na profilu instytucji",
        rok=2026,
        pbn_uid=poza,
    )
    skasowana = baker.make(Publication, mongoId="pbn-skasowana", status="DELETED")
    _rekord_bpp(
        Wydawnictwo_Ciagle,
        jednostka_uczelni,
        autor_pbn,
        tytul_oryginalny="Artykuł skasowany po stronie PBN",
        rok=2026,
        pbn_uid=skasowana,
    )
    _rekord_bpp(
        Wydawnictwo_Ciagle,
        jednostka_uczelni,
        autor_pbn,
        tytul_oryginalny="Artykuł z innego roku",
        rok=2020,
        pbn_uid=None,
    )

    wynik = uzgodnij(przebieg(), klient)

    assert {w["bpp_tytul"]: w["kategoria"] for w in wynik.wynik} == {
        "Artykuł znany tylko w BPP": silnik.NIE_SPRAWDZONO,
        "Artykuł w PBN, ale nie na profilu instytucji": silnik.POZA_PROFILEM,
        "Artykuł skasowany po stronie PBN": silnik.SKASOWANA_W_PBN,
    }
    assert Wydawnictwo_Ciagle.objects.count() == 4, "uzgadnianie coś skasowało"


def test_praca_skasowana_w_pbn_nie_jest_tworzona(klient, ksiazka_pbn, przebieg):
    klient.dodaj("pbn-skasowana", ksiazka_pbn("Monografia wycofana z PBN"))
    klient.publikacje["pbn-skasowana"]["status"] = "DELETED"

    wynik = uzgodnij(przebieg(), klient)

    assert kategorie(wynik) == {"pbn-skasowana": silnik.SKASOWANA_W_PBN}
    assert not Wydawnictwo_Zwarte.objects.exists()


def test_rekord_w_koszu_nie_jest_wskrzeszany(klient, ksiazka_pbn, przebieg):
    klient.dodaj("pbn-kosz", ksiazka_pbn("Monografia usunięta świadomie w BPP"))
    uzgodnij(przebieg(), klient)
    Wydawnictwo_Zwarte.objects.get(pbn_uid_id="pbn-kosz").delete()

    wynik = uzgodnij(przebieg(), klient)

    assert kategorie(wynik) == {"pbn-kosz": silnik.POMINIETO}
    assert not Wydawnictwo_Zwarte.objects.exists()
    assert Wydawnictwo_Zwarte.global_objects.count() == 1


# -- wersja przypięta na profilu instytucji (FD#511) --------------------------


def test_rekord_powstaje_z_wersji_przypietej_a_nie_biezacej(
    klient, ksiazka_pbn, przebieg
):
    przypieta = ksiazka_pbn("Tytuł zatwierdzony przez uczelnię")
    klient.dodaj("pbn-wersje", przypieta)
    klient.dodaj_wersje_biezaca(
        "pbn-wersje", {**przypieta, "title": "Tytuł zmieniony przez kogoś obcego"}
    )

    wynik = uzgodnij(przebieg(), klient)

    rekord = Wydawnictwo_Zwarte.objects.get(pbn_uid_id="pbn-wersje")
    assert rekord.tytul_oryginalny == "Tytuł zatwierdzony przez uczelnię"
    wpis = wynik.wynik[0]
    assert wpis["wersja"] == PRZYPIETA
    assert "nowsza wersja" in wpis["uwaga"]
    # W kopii danych PBN są obie wersje.
    assert len(Publication.objects.get(pk="pbn-wersje").versions) == 2


def test_brak_wersji_przypietej_bierze_biezaca_i_mowi_o_tym(
    klient, ksiazka_pbn, przebieg
):
    klient.dodaj("pbn-bez", ksiazka_pbn("Monografia bez przypiętej"), przypnij=False)

    wynik = uzgodnij(przebieg(), klient)

    assert wynik.wynik[0]["kategoria"] == silnik.UTWORZONO
    assert wynik.wynik[0]["wersja"] == BIEZACA_BRAK_PRZYPIETEJ


def test_kopia_danych_pbn_jest_odswiezana(klient, ksiazka_pbn, przebieg):
    """„Pobieranie danych z PBN” nie odświeża publikacji już pobranych —
    uzgadnianie musi, inaczej nie widziałoby zmian wprowadzonych w PBN."""
    obiekt = ksiazka_pbn("Tytuł po poprawce w PBN")
    klient.dodaj("pbn-stara", obiekt)
    baker.make(
        Publication,
        mongoId="pbn-stara",
        status="ACTIVE",
        versions=[{"current": True, "object": {**obiekt, "title": "Tytuł stary"}}],
    )

    uzgodnij(przebieg(), klient)

    assert Publication.objects.get(pk="pbn-stara").title == "Tytuł po poprawce w PBN"
    assert PublikacjaInstytucji.objects.filter(publicationId_id="pbn-stara").exists()


# -- bezpieczniki FD#535 -----------------------------------------------------


def test_praca_bez_autorow_i_redaktorow_nie_jest_tworzona(
    klient, ksiazka_pbn, przebieg
):
    obiekt = ksiazka_pbn("Monografia bez osób w PBN")
    obiekt.pop("authors")
    obiekt.pop("affiliations")
    klient.dodaj("pbn-bez-osob", obiekt)

    wynik = uzgodnij(przebieg(), klient)

    assert kategorie(wynik) == {"pbn-bez-osob": silnik.POMINIETO}
    assert "ani autorów, ani redaktorów" in wynik.wynik[0]["powod"]
    assert not Wydawnictwo_Zwarte.objects.exists()


def test_redaktor_zapisany_jako_autor_wycofuje_utworzenie(
    klient, uczelnia_pbn, autor_pbn, przebieg
):
    """PBN: osoba jest REDAKTOREM, ale wpis afiliacji ma typ AUTHOR — importer
    zapisałby ją jako autora (FD#535). Takiego rekordu nie zostawiamy."""
    osoba = autor_pbn("Redaktorski")
    klient.dodaj(
        "pbn-redaktor",
        {
            "type": "EDITED_BOOK",
            "title": "Praca zbiorowa pod redakcją",
            "year": 2026,
            "mainLanguage": "pol",
            "editors": {osoba: {"lastName": "Redaktorski", "name": "Jan"}},
            "affiliations": {
                osoba: [{"type": "AUTHOR", "institutionId": uczelnia_pbn.pbn_uid_id}]
            },
        },
    )

    wynik = uzgodnij(przebieg(), klient)

    assert kategorie(wynik) == {"pbn-redaktor": silnik.POMINIETO}
    assert "a w PBN jest ich 0" in wynik.wynik[0]["powod"]
    assert not Wydawnictwo_Zwarte.objects.exists(), "został rekord z błędnymi rolami"


def test_blad_jednej_pracy_nie_przerywa_przebiegu(
    klient, ksiazka_pbn, przebieg, mocker
):
    klient.dodaj("pbn-a-zla", ksiazka_pbn("Monografia, na której importer pada"))
    klient.dodaj("pbn-b-dobra", ksiazka_pbn("Monografia poprawna"))
    prawdziwy = silnik.importuj_publikacje_po_pbn_uid_id

    def importer(pbn_uid, **kw):
        if pbn_uid == "pbn-a-zla":
            raise KeyError("pole, którego PBN nie przysłał")
        return prawdziwy(pbn_uid, **kw)

    mocker.patch.object(silnik, "importuj_publikacje_po_pbn_uid_id", importer)
    log = mocker.patch.object(silnik.logger, "exception")

    wynik = uzgodnij(przebieg(), klient)

    assert kategorie(wynik) == {
        "pbn-a-zla": silnik.BLAD,
        "pbn-b-dobra": silnik.UTWORZONO,
    }
    assert "KeyError" in wynik.wynik[0]["powod"]
    log.assert_called_once()  # błąd zalogowany z tracebackiem
    assert Wydawnictwo_Zwarte.objects.count() == 1


# -- podgląd ------------------------------------------------------------------


def _bez_identyfikatorow(wpisy):
    return [{k: v for k, v in w.items() if k != "bpp_pk"} for w in wpisy]


def test_podglad_nic_nie_zmienia_i_pokazuje_to_co_zrobi_wykonanie(
    klient, ksiazka_pbn, przebieg, jednostka_uczelni, autor_pbn
):
    """Podgląd i wykonanie dają TEN SAM raport — także tam, gdzie wynik jednej
    pracy zależy od poprzedniej (dwie prace PBN z tym samym ISBN)."""
    klient.dodaj("pbn-1-nowa", ksiazka_pbn("Monografia do utworzenia"))
    zdublowana = "Monografia wprowadzona do repozytorium PBN dwukrotnie"
    klient.dodaj("pbn-2-dubel-a", ksiazka_pbn(zdublowana, isbn="978-83-00-00002-8"))
    klient.dodaj("pbn-3-dubel-b", ksiazka_pbn(zdublowana, isbn="978-83-00-00002-8"))
    do_powiazania = _rekord_bpp(
        Wydawnictwo_Zwarte,
        jednostka_uczelni,
        autor_pbn,
        tytul_oryginalny="Monografia wpisana ręcznie",
        rok=2026,
        doi="10.1234/recznie",
        pbn_uid=None,
    )
    klient.dodaj(
        "pbn-4-do-powiazania",
        ksiazka_pbn("Monografia wpisana ręcznie", doi="10.1234/recznie"),
    )

    podglad = uzgodnij(przebieg(tryb="podglad"), klient)

    # Podgląd nie zostawił śladu w rekordach BPP…
    assert Wydawnictwo_Zwarte.objects.count() == 1
    do_powiazania.refresh_from_db()
    assert do_powiazania.pbn_uid_id is None
    assert not Rekord.objects.exclude(pbn_uid_id=None).exists()
    # …ale kopię danych PBN odświeżył.
    assert Publication.objects.filter(pk="pbn-1-nowa").exists()

    wykonanie = uzgodnij(przebieg(tryb="wykonanie", na_podstawie=podglad), klient)

    assert _bez_identyfikatorow(podglad.wynik) == _bez_identyfikatorow(wykonanie.wynik)
    assert podglad.podsumowanie == wykonanie.podsumowanie
    assert kategorie(wykonanie) == {
        "pbn-1-nowa": silnik.UTWORZONO,
        "pbn-2-dubel-a": silnik.UTWORZONO,
        "pbn-3-dubel-b": silnik.KONFLIKT,
        "pbn-4-do-powiazania": silnik.POWIAZANO,
    }
    assert Wydawnictwo_Zwarte.objects.count() == 3


def test_wykonanie_podgladu_nie_pobiera_danych_ponownie(klient, ksiazka_pbn, przebieg):
    klient.dodaj("pbn-nowa", ksiazka_pbn("Monografia z podglądu"))
    podglad = uzgodnij(przebieg(tryb="podglad"), klient)
    klient.wywolania.clear()
    # Po podglądzie ktoś dopisał w PBN kolejną pracę — „wykonaj ten podgląd”
    # ma zrobić dokładnie to, co pokazano, więc jej nie zobaczy.
    klient.dodaj("pbn-pozniejsza", ksiazka_pbn("Monografia dopisana po podglądzie"))

    wykonanie = uzgodnij(przebieg(na_podstawie=podglad), klient)

    assert klient.wywolania == []
    assert kategorie(wykonanie) == {"pbn-nowa": silnik.UTWORZONO}


# -- ślad, ping-pong, anulowanie ---------------------------------------------


def test_utworzenie_i_powiazanie_zostawiaja_slad_w_historii(
    klient, ksiazka_pbn, przebieg, jednostka_uczelni, autor_pbn
):
    from django.contrib.admin.models import ADDITION, CHANGE, LogEntry

    powiazany = _rekord_bpp(
        Wydawnictwo_Zwarte,
        jednostka_uczelni,
        autor_pbn,
        tytul_oryginalny="Monografia do powiązania",
        rok=2026,
        doi="10.1234/slad",
        pbn_uid=None,
    )
    klient.dodaj("pbn-nowa", ksiazka_pbn("Monografia do utworzenia"))
    klient.dodaj(
        "pbn-powiazana", ksiazka_pbn("Monografia do powiązania", doi="10.1234/slad")
    )
    p = przebieg()

    uzgodnij(p, klient)

    nowy = Wydawnictwo_Zwarte.objects.get(pbn_uid_id="pbn-nowa")
    dodanie = LogEntry.objects.get(object_id=str(nowy.pk), action_flag=ADDITION)
    assert dodanie.user == p.user
    zmiana = LogEntry.objects.get(object_id=str(powiazany.pk), action_flag=CHANGE)
    assert zmiana.user == p.user
    assert "pbn-powiazana" in zmiana.change_message


def test_uzgadnianie_niczego_nie_wysyla_do_pbn(
    klient, ksiazka_pbn, przebieg, jednostka_uczelni, autor_pbn
):
    """Ochrona przed ping-pongiem: wysyłka z BPP nadpisuje w PBN autorów,
    więc uzgadnianie nie może niczego wysyłać ani kolejkować."""
    _rekord_bpp(
        Wydawnictwo_Zwarte,
        jednostka_uczelni,
        autor_pbn,
        tytul_oryginalny="Monografia do powiązania",
        rok=2026,
        doi="10.1234/ping",
        pbn_uid=None,
    )
    klient.dodaj("pbn-nowa", ksiazka_pbn("Monografia do utworzenia"))
    klient.dodaj(
        "pbn-powiazana", ksiazka_pbn("Monografia do powiązania", doi="10.1234/ping")
    )

    uzgodnij(przebieg(), klient)

    assert not PBN_Export_Queue.objects.exists()
    assert {w.split(":")[0] for w in klient.wywolania} == {
        "get_institution_publications",
        "get_institution_publications_v2",
        "get_publication_by_id",
        "get_institution_statements",
        "search_publications",
    }


class _AnulujPo:
    def __init__(self, ile):
        self.ile = ile

    def etap(self, opis, procent):
        pass

    def zamknij(self):
        pass

    def sprawdz_anulowanie(self):
        self.ile -= 1
        if self.ile < 0:
            raise Anulowano()


def test_anulowane_wykonanie_zachowuje_zrobione_i_da_sie_dokonczyc(
    klient, ksiazka_pbn, przebieg
):
    klient.dodaj("pbn-a", ksiazka_pbn("Monografia pierwsza"))
    klient.dodaj("pbn-b", ksiazka_pbn("Monografia druga"))
    podglad = uzgodnij(przebieg(tryb="podglad"), klient)

    # Anulowanie po pierwszej pracy (zakres z podglądu → liczymy tylko pętlę).
    przerwany = uzgodnij(przebieg(na_podstawie=podglad), klient, _AnulujPo(1))

    assert przerwany.status == "anulowane"
    assert kategorie(przerwany) == {"pbn-a": silnik.UTWORZONO}
    assert Wydawnictwo_Zwarte.objects.count() == 1

    dokonczony = uzgodnij(przebieg(), klient)

    assert kategorie(dokonczony) == {
        "pbn-a": silnik.ZGODNE,
        "pbn-b": silnik.UTWORZONO,
    }
    assert Wydawnictwo_Zwarte.objects.count() == 2


def test_anulowany_podglad_niczego_nie_zostawia(klient, ksiazka_pbn, przebieg):
    klient.dodaj("pbn-a", ksiazka_pbn("Monografia pierwsza"))
    klient.dodaj("pbn-b", ksiazka_pbn("Monografia druga"))
    pelny = uzgodnij(przebieg(tryb="podglad"), klient)
    kopia = przebieg(tryb="podglad", na_podstawie=pelny)

    przerwany = uzgodnij(kopia, klient, _AnulujPo(1))

    assert przerwany.status == "anulowane"
    assert przerwany.wynik == []
    assert not Wydawnictwo_Zwarte.objects.exists()


# -- multi-hosted -------------------------------------------------------------


def test_uzgadnianie_dotyczy_tylko_wskazanej_uczelni(
    klient, ksiazka_pbn, przebieg, jednostka_uczelni, autor_pbn
):
    from bpp.models import Jednostka, Uczelnia
    from pbn_api.models import Institution

    druga = baker.make(Uczelnia, skrot="DRU", pbn_uid=baker.make(Institution))
    jednostka_drugiej = baker.make(Jednostka, uczelnia=druga)
    _rekord_bpp(
        Wydawnictwo_Ciagle,
        jednostka_drugiej,
        autor_pbn,
        tytul_oryginalny="Artykuł drugiej uczelni, bez PBN UID",
        rok=2026,
        pbn_uid=None,
    )
    # Wpis profilu INNEJ instytucji w odpowiedzi PBN — nie nasz.
    klient.dodaj("pbn-cudza", ksiazka_pbn("Monografia drugiej uczelni"))
    klient.profil_v1[-1]["institutionId"] = druga.pbn_uid_id
    klient.dodaj("pbn-nasza", ksiazka_pbn("Monografia naszej uczelni"))

    wynik = uzgodnij(przebieg(), klient)

    assert kategorie(wynik) == {"pbn-nasza": silnik.UTWORZONO}
    assert not Wydawnictwo_Zwarte.objects.filter(pbn_uid_id="pbn-cudza").exists()


# -- pozostałe typy prac ------------------------------------------------------


def test_artykul_jest_tworzony_z_doi_i_zrodlem(klient, ksiazka_pbn, przebieg):
    from bpp.models import Zrodlo
    from pbn_api.models import Journal

    zrodlo = baker.make(Zrodlo, pbn_uid=baker.make(Journal))
    obiekt = ksiazka_pbn("Artykuł, którego nie ma w BPP", doi="10.1234/artykul")
    obiekt.update(type="ARTICLE", journal={"id": zrodlo.pbn_uid_id})
    klient.dodaj("pbn-artykul", obiekt)

    wynik = uzgodnij(przebieg(), klient)

    assert kategorie(wynik) == {"pbn-artykul": silnik.UTWORZONO}
    rekord = Wydawnictwo_Ciagle.objects.get(pbn_uid_id="pbn-artykul")
    assert (rekord.zrodlo, rekord.doi) == (zrodlo, "10.1234/artykul")
    # Drugi przebieg: nic do zrobienia i żadnych różnic.
    assert kategorie(uzgodnij(przebieg(), klient)) == {"pbn-artykul": silnik.ZGODNE}


def test_rozdzial_tworzy_tez_ksiazke_nadrzedna_i_mowi_o_tym(
    klient, ksiazka_pbn, przebieg
):
    """Książka nadrzędna nie jest na profilu instytucji, ale rozdział musi
    być do czegoś przypięty — raport mówi wprost, że ją utworzono."""
    klient.dodaj(
        "pbn-ksiazka",
        {"type": "EDITED_BOOK", "title": "Księga zbiorowa innej uczelni", "year": 2026},
        na_profilu=False,
    )
    rozdzial = ksiazka_pbn("Rozdział naszego autora w cudzej księdze")
    rozdzial.update(type="CHAPTER", book={"id": "pbn-ksiazka"})
    klient.dodaj("pbn-rozdzial", rozdzial)

    wynik = uzgodnij(przebieg(), klient)

    assert kategorie(wynik) == {"pbn-rozdzial": silnik.UTWORZONO}
    assert "książkę nadrzędną (PBN pbn-ksiazka)" in wynik.wynik[0]["uwaga"]
    rekord = Wydawnictwo_Zwarte.objects.get(pbn_uid_id="pbn-rozdzial")
    assert rekord.wydawnictwo_nadrzedne.pbn_uid_id == "pbn-ksiazka"
    assert kategorie(uzgodnij(przebieg(), klient)) == {"pbn-rozdzial": silnik.ZGODNE}


# -- rekordy BPP bez powiązania z PBN: cztery podgrupy --------------------------


def test_duplikat_rekordu_powiazanego_z_pbn_jest_wskazany_nie_scalany(
    klient, przebieg, jednostka_uczelni, autor_pbn
):
    """Ktoś wpisał pracę ręcznie, a potem z PBN powstał drugi rekord."""
    z_pbn = _rekord_bpp(
        Wydawnictwo_Ciagle,
        jednostka_uczelni,
        autor_pbn,
        tytul_oryginalny="Wpływ <i>Apis mellifera</i> na plony: przegląd.",
        rok=2026,
        pbn_uid=baker.make(Publication, mongoId="pbn-oryginal", status="ACTIVE"),
    )
    reczny = _rekord_bpp(
        Wydawnictwo_Ciagle,
        jednostka_uczelni,
        autor_pbn,
        tytul_oryginalny="WPŁYW APIS MELLIFERA NA PLONY — PRZEGLĄD",
        rok=2026,
        pbn_uid=None,
    )

    wynik = uzgodnij(przebieg(), klient)

    (wpis,) = [w for w in wynik.wynik if w["kategoria"] == silnik.DUPLIKAT_W_BPP]
    assert wpis["bpp_pk"] == reczny.pk
    assert wpis["blizniak"]["bpp_pk"] == z_pbn.pk
    assert wpis["dopasowanie"] == "ten sam tytuł i rok"
    assert Wydawnictwo_Ciagle.objects.count() == 2, "coś scalono"


def test_praca_znaleziona_w_pbn_po_doi_poza_profilem_to_propozycja_bez_automatu(
    klient, ksiazka_pbn, przebieg, jednostka_uczelni, autor_pbn
):
    rekord = _rekord_bpp(
        Wydawnictwo_Ciagle,
        jednostka_uczelni,
        autor_pbn,
        tytul_oryginalny="Artykuł, który w PBN jest poza profilem instytucji",
        rok=2026,
        doi="10.5555/Poza.Profilem",
        pbn_uid=None,
    )
    klient.dodaj(
        "pbn-poza",
        ksiazka_pbn(
            "Artykuł, który w PBN jest poza profilem", doi="10.5555/poza.profilem"
        ),
        na_profilu=False,
    )
    klient.wyszukiwalne["doi:10.5555/poza.profilem"] = ["pbn-poza"]

    wynik = uzgodnij(przebieg(), klient)

    (wpis,) = [w for w in wynik.wynik if w.get("bpp_pk") == rekord.pk]
    assert wpis["kategoria"] == silnik.W_PBN_NIEPOWIAZANA
    assert (wpis["pbn_uid"], wpis["na_profilu"]) == ("pbn-poza", False)
    assert wpis["dopasowanie"] == "ten sam DOI (w PBN)"
    assert "dodaj pracę w PBN do profilu instytucji" in wpis["powod"]
    rekord.refresh_from_db()
    assert rekord.pbn_uid_id is None, "powiązano automatycznie"
    # Znaleziona praca trafiła do lokalnej kopii danych PBN.
    assert Publication.objects.filter(pk="pbn-poza").exists()


def test_pracy_o_tym_doi_nie_ma_w_pbn_kandydat_do_wyslania_z_historia(
    klient, przebieg, jednostka_uczelni, autor_pbn, uczelnia_pbn
):
    from django.contrib.contenttypes.models import ContentType
    from django.utils import timezone

    from pbn_api.models import SentData

    nigdy = _rekord_bpp(
        Wydawnictwo_Ciagle,
        jednostka_uczelni,
        autor_pbn,
        tytul_oryginalny="Artykuł nigdy niewysłany do PBN",
        rok=2026,
        doi="10.5555/nigdy",
        pbn_uid=None,
    )
    nieudana = _rekord_bpp(
        Wydawnictwo_Ciagle,
        jednostka_uczelni,
        autor_pbn,
        tytul_oryginalny="Artykuł z nieudaną wysyłką do PBN",
        rok=2026,
        doi="10.5555/nieudana",
        pbn_uid=None,
    )
    SentData.objects.create(
        content_type=ContentType.objects.get_for_model(Wydawnictwo_Ciagle),
        object_id=nieudana.pk,
        uczelnia=uczelnia_pbn,
        data_sent={},
        submitted_successfully=False,
        submitted_at=timezone.now(),
        exception="HttpException 400: brak afiliacji autora",
    )

    wynik = uzgodnij(przebieg(), klient)

    po_pk = {w["bpp_pk"]: w for w in wynik.wynik}
    assert po_pk[nigdy.pk]["kategoria"] == silnik.TYLKO_W_BPP
    assert po_pk[nigdy.pk]["wysylka"] == "nigdy nie wysyłany z BPP do PBN"
    assert po_pk[nieudana.pk]["kategoria"] == silnik.TYLKO_W_BPP
    assert po_pk[nieudana.pk]["wysylka"].startswith("wysyłka nieudana ")
    assert "brak afiliacji autora" in po_pk[nieudana.pk]["wysylka"]
    # Po jednym zapytaniu na DOI; niczego nie wysłano.
    assert sorted(w for w in klient.wywolania if w.startswith("search")) == [
        "search_publications:doi:10.5555/nieudana",
        "search_publications:doi:10.5555/nigdy",
    ]


def test_ksiazka_jest_szukana_takze_po_isbn_a_rozdzial_nie(
    klient, przebieg, jednostka_uczelni, autor_pbn
):
    ksiazka = _rekord_bpp(
        Wydawnictwo_Zwarte,
        jednostka_uczelni,
        autor_pbn,
        tytul_oryginalny="Monografia szukana po numerze ISBN",
        rok=2026,
        isbn="978-83-00-00009-7",
        pbn_uid=None,
    )
    _rekord_bpp(
        Wydawnictwo_Zwarte,
        jednostka_uczelni,
        autor_pbn,
        tytul_oryginalny="Rozdział w tej monografii, z jej numerem ISBN",
        rok=2026,
        isbn="978-83-00-00009-7",
        wydawnictwo_nadrzedne=ksiazka,
        pbn_uid=None,
    )

    wynik = uzgodnij(przebieg(), klient)

    assert [w for w in klient.wywolania if w.startswith("search")] == [
        "search_publications:isbn:9788300000097"
    ]
    po_tytule = {w["bpp_tytul"]: w["kategoria"] for w in wynik.wynik}
    assert po_tytule["Monografia szukana po numerze ISBN"] == silnik.TYLKO_W_BPP
    assert (
        po_tytule["Rozdział w tej monografii, z jej numerem ISBN"]
        == silnik.NIE_SPRAWDZONO
    )


def test_swieze_wyniki_wyszukiwania_nie_sa_pobierane_ponownie(
    klient, przebieg, jednostka_uczelni, autor_pbn, settings
):
    _rekord_bpp(
        Wydawnictwo_Ciagle,
        jednostka_uczelni,
        autor_pbn,
        tytul_oryginalny="Artykuł pytany w PBN tylko raz",
        rok=2026,
        doi="10.5555/raz",
        pbn_uid=None,
    )
    pierwsze = uzgodnij(przebieg(tryb="pobranie"), klient)
    klient.wywolania.clear()

    drugie = uzgodnij(przebieg(tryb="pobranie"), klient)

    assert not [w for w in klient.wywolania if w.startswith("search")]
    assert drugie.zakres["szukane"] == pierwsze.zakres["szukane"]
    assert (
        drugie.zakres["pobrano"]["wyszukiwanie"]
        == pierwsze.zakres["pobrano"]["wyszukiwanie"]
    ), "data źródła ma być datą faktycznego zapytania"

    # Po upływie progu świeżości pytamy ponownie.
    settings.PBN_UZGADNIANIE_DANE_AKTUALNE_GODZIN = 0
    uzgodnij(przebieg(tryb="pobranie"), klient)

    assert [w for w in klient.wywolania if w.startswith("search")]


# -- prace spoza profilu a inne uczelnie instalacji ---------------------------------


def test_praca_z_profilu_innej_uczelni_instalacji_jest_odrozniona(
    klient, przebieg, jednostka_uczelni, autor_pbn
):
    from bpp.models import Uczelnia
    from pbn_api.models import Institution, Scientist

    druga = baker.make(Uczelnia, skrot="DRUGA", pbn_uid=baker.make(Institution))
    u_drugiej = baker.make(Publication, mongoId="pbn-u-drugiej", status="ACTIVE")
    baker.make(
        PublikacjaInstytucji,
        institutionId=druga.pbn_uid,
        publicationId=u_drugiej,
        insPersonId=baker.make(Scientist),
    )
    _rekord_bpp(
        Wydawnictwo_Ciagle,
        jednostka_uczelni,
        autor_pbn,
        tytul_oryginalny="Artykuł współautorski, na profilu drugiej uczelni",
        rok=2026,
        pbn_uid=u_drugiej,
    )
    _rekord_bpp(
        Wydawnictwo_Ciagle,
        jednostka_uczelni,
        autor_pbn,
        tytul_oryginalny="Artykuł, którego nie ma na żadnym profilu",
        rok=2026,
        pbn_uid=baker.make(Publication, mongoId="pbn-nigdzie", status="ACTIVE"),
    )

    wynik = uzgodnij(przebieg(), klient)

    po_tytule = {w["bpp_tytul"]: w for w in wynik.wynik}
    inna = po_tytule["Artykuł współautorski, na profilu drugiej uczelni"]
    assert inna["kategoria"] == silnik.NA_PROFILU_INNEJ_UCZELNI
    assert inna["inna_uczelnia"] == "DRUGA"
    assert (
        po_tytule["Artykuł, którego nie ma na żadnym profilu"]["kategoria"]
        == silnik.POZA_PROFILEM
    )


def test_rekord_wspolautorski_dwoch_uczelni_jest_w_zakresie_kazdej(
    klient, przebieg, jednostka_uczelni, autor_pbn
):
    """Zamierzone: każda uczelnia powinna mieć taką pracę na SWOIM profilu."""
    from bpp.models import Autor, Jednostka, Uczelnia
    from pbn_api.models import Institution

    druga = baker.make(Uczelnia, skrot="DRUGA", pbn_uid=baker.make(Institution))
    rekord = _rekord_bpp(
        Wydawnictwo_Ciagle,
        jednostka_uczelni,
        autor_pbn,
        tytul_oryginalny="Artykuł współautorski dwóch uczelni instalacji",
        rok=2026,
        pbn_uid=None,
    )
    rekord.dodaj_autora(
        Autor.objects.get(pbn_uid_id=autor_pbn("Drugi")),
        baker.make(Jednostka, uczelnia=druga),
    )

    u_nas = uzgodnij(przebieg(), klient)
    u_drugiej = uzgodnij(przebieg(uczelnia=druga), FalszywyKlientPBN(druga))

    assert [w["bpp_pk"] for w in u_nas.wynik] == [rekord.pk]
    assert [w["bpp_pk"] for w in u_drugiej.wynik] == [rekord.pk]


# -- pobieranie: licznik i pominięcie profilu ---------------------------------------


class _Zapisuj:
    def __init__(self):
        self.etapy = []

    def etap(self, opis, procent):
        self.etapy.append(opis)

    def sprawdz_anulowanie(self):
        pass

    def zamknij(self):
        pass


def test_pobieranie_profilu_pokazuje_licznik(klient, ksiazka_pbn, przebieg):
    for nr in range(30):
        klient.dodaj(f"pbn-{nr:02}", ksiazka_pbn(f"Monografia numer {nr} z profilu"))
    nadzorca = _Zapisuj()

    uzgodnij(przebieg(tryb="pobranie"), klient, nadzorca)

    assert "Pobieranie profilu instytucji z PBN — lista prac i osób: 1 z 30" in (
        nadzorca.etapy
    )
    assert "Pobieranie profilu instytucji z PBN — lista prac i osób: 25 z 30" in (
        nadzorca.etapy
    )
    assert "Pobieranie publikacji z PBN: 30 z 30" in nadzorca.etapy


def test_pobranie_ze_swiezym_profilem_pomija_liste_profilu_i_zachowuje_jej_date(
    klient, ksiazka_pbn, przebieg
):
    obiekt = ksiazka_pbn("Monografia z profilu pobranego wcześniej")
    klient.dodaj("pbn-nowa", obiekt)
    pelne = uzgodnij(przebieg(tryb="pobranie"), klient)
    klient.wywolania.clear()
    klient.publikacje["pbn-nowa"]["versions"][0]["object"]["title"] = "Po poprawce"

    szybkie = uzgodnij(przebieg(tryb="pobranie", na_podstawie=pelne), klient)

    assert not [w for w in klient.wywolania if "institution_publications" in w]
    assert "get_publication_by_id:pbn-nowa" in klient.wywolania
    assert Publication.objects.get(pk="pbn-nowa").title == "Po poprawce"
    assert szybkie.zakres["pobrano"]["profil"] == pelne.zakres["pobrano"]["profil"]
    assert (
        szybkie.zakres["pobrano"]["publikacje"] > pelne.zakres["pobrano"]["publikacje"]
    )
    assert szybkie.zakres["w_zakresie"] == ["pbn-nowa"]
