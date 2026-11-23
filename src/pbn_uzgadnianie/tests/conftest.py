"""Wspólne dane testowe: uczelnia z PBN, fałszywy klient PBN, fabryki."""

import uuid

import pytest
from model_bakery import baker

from bpp import const
from bpp.models import Autor, Charakter_Formalny, Jednostka
from pbn_api.exceptions import PublicationNotFound
from pbn_api.models import Institution, Publication, Scientist
from pbn_uzgadnianie.models import UzgodnienieZPBN


class FalszywyKlientPBN:
    """Klient PBN bez sieci. Każde nieprzewidziane wywołanie (w szczególności
    WYSYŁKA czegokolwiek do PBN) wywraca test."""

    def __init__(self, uczelnia):
        self.uczelnia = uczelnia
        self.profil_v1 = []
        self.profil_v2 = []
        self.publikacje = {}
        self.oswiadczenia = {}
        #: Co PBN „znajduje” po DOI/ISBN: ``{"doi:10.x/y": [pbn_uid, …]}``.
        self.wyszukiwalne = {}
        self.wywolania = []

    def get_institution_publications(self, page_size=10):
        self.wywolania.append("get_institution_publications")
        return list(self.profil_v1)

    def get_institution_publications_v2(self):
        self.wywolania.append("get_institution_publications_v2")
        return list(self.profil_v2)

    def get_publication_by_id(self, pbn_uid):
        self.wywolania.append(f"get_publication_by_id:{pbn_uid}")
        if pbn_uid not in self.publikacje:
            raise PublicationNotFound(422, "/x", "Publication was not exists!")
        return self.publikacje[pbn_uid]

    def get_institution_statements_of_single_publication(self, pbn_uid, page_size=50):
        self.wywolania.append(f"get_institution_statements:{pbn_uid}")
        return [dict(o) for o in self.oswiadczenia.get(pbn_uid, [])]

    def search_publications(self, **kryteria):
        ((pole, wartosc),) = kryteria.items()
        self.wywolania.append(f"search_publications:{pole}:{wartosc}")
        return [{"mongoId": u} for u in self.wyszukiwalne.get(f"{pole}:{wartosc}", [])]

    def oswiadcz(self, pbn_uid, osoba, dyscyplina, rola="AUTHOR"):
        """Oświadczenie osoby na profilu instytucji (z dyscypliną)."""
        self.oswiadczenia.setdefault(pbn_uid, []).append(
            {
                "id": str(uuid.uuid4()),
                "institutionId": self.uczelnia.pbn_uid_id,
                "personId": osoba,
                "publicationId": pbn_uid,
                "addedTimestamp": "2026.03.01",
                "statedTimestamp": "2026.03.02",
                "area": None,
                "inOrcid": True,
                "type": rola,
                "disciplines": {"name": dyscyplina} if dyscyplina else None,
            }
        )

    def __getattr__(self, nazwa):
        # Samo sięgnięcie po metodę jest niewinne (kod przekazuje np.
        # ``fetch=client.get_institution_by_id``) — wywraca dopiero wywołanie.
        def nieoczekiwane(*args, **kwargs):
            raise AssertionError(f"Nieoczekiwane wywołanie klienta PBN: {nazwa}")

        return nieoczekiwane

    # -- budowanie stanu „po stronie PBN” ----------------------------------

    def dodaj(self, pbn_uid, obiekt, *, na_profilu=True, przypnij=True, osoba=None):
        """Praca w PBN (jedna wersja, bieżąca) — domyślnie na profilu uczelni."""
        wersja_id = str(uuid.uuid4())
        self.publikacje[pbn_uid] = {
            "mongoId": pbn_uid,
            "status": "ACTIVE",
            "verificationLevel": "VERIFIED",
            "verified": True,
            "versions": [
                {"current": True, "versionHash": wersja_id, "object": dict(obiekt)}
            ],
        }
        if na_profilu:
            self.profil_v1.append(
                {
                    "institutionId": self.uczelnia.pbn_uid_id,
                    "publicationId": pbn_uid,
                    "insPersonId": osoba or baker.make(Scientist).pk,
                    "publicationVersion": wersja_id if przypnij else None,
                    "publicationYear": obiekt.get("year"),
                    "publicationType": obiekt.get("type"),
                    "userType": "AUTHOR",
                    "snapshot": None,
                }
            )
        return wersja_id

    def dodaj_wersje_biezaca(self, pbn_uid, obiekt):
        """Ktoś zmienił pracę w repozytorium PBN: nowa wersja bieżąca,
        profil instytucji dalej wskazuje poprzednią."""
        wersje = self.publikacje[pbn_uid]["versions"]
        for wersja in wersje:
            wersja["current"] = False
        wersje.append(
            {"current": True, "versionHash": str(uuid.uuid4()), "object": dict(obiekt)}
        )


@pytest.fixture(autouse=True)
def swiezy_cache_importera():
    """Importer trzyma słowniki (charakter formalny, status korekty…) w
    ``lru_cache`` na cały proces. Między testami wiersze słowników bywają
    odtwarzane z innymi kluczami — bez czyszczenia importer wstawiałby
    klucz obcy do wiersza, którego już nie ma."""
    from pbn_integrator.importer import cache

    cache.clear_cache()
    yield
    cache.clear_cache()


@pytest.fixture
def slowniki(
    jezyki, charaktery_formalne, typy_kbn, typy_odpowiedzialnosci, statusy_korekt
):
    Charakter_Formalny.objects.filter(nazwa="Książka").update(
        rodzaj_pbn=const.RODZAJ_PBN_KSIAZKA
    )
    Charakter_Formalny.objects.filter(nazwa="Artykuł w czasopismie").update(
        rodzaj_pbn=const.RODZAJ_PBN_ARTYKUL
    )


@pytest.fixture
def uczelnia_pbn(uczelnia, slowniki):
    uczelnia.pbn_uid = baker.make(Institution)
    uczelnia.pbn_integracja = True
    uczelnia.obca_jednostka = baker.make(
        Jednostka, uczelnia=uczelnia, skupia_pracownikow=False, nazwa="Obca jednostka"
    )
    uczelnia.save()
    return uczelnia


@pytest.fixture
def jednostka_uczelni(uczelnia_pbn):
    return baker.make(Jednostka, uczelnia=uczelnia_pbn, nazwa="Katedra Testowa")


@pytest.fixture
def klient(uczelnia_pbn):
    return FalszywyKlientPBN(uczelnia_pbn)


@pytest.fixture
def autor_pbn(db):
    """Fabryka: autor BPP powiązany z osobą w PBN → zwraca PBN UID osoby."""

    def zrob(nazwisko="Kowalski"):
        osoba = baker.make(Scientist)
        baker.make(Autor, nazwisko=nazwisko, imiona="Jan", pbn_uid=osoba)
        return osoba.pk

    return zrob


@pytest.fixture
def ksiazka_pbn(uczelnia_pbn, autor_pbn):
    """Fabryka obiektu książki z PBN z jednym afiliowanym autorem."""

    def zrob(tytul, rok=2026, **pola):
        osoba = autor_pbn()
        obiekt = {
            "type": "BOOK",
            "title": tytul,
            "year": rok,
            "mainLanguage": "pol",
            "authors": {osoba: {"lastName": "Kowalski", "name": "Jan"}},
            "affiliations": {
                osoba: [{"type": "AUTHOR", "institutionId": uczelnia_pbn.pbn_uid_id}]
            },
        }
        obiekt.update(pola)
        return obiekt

    return zrob


@pytest.fixture
def przebieg(uczelnia_pbn, django_user_model):
    """Fabryka przebiegów uzgadniania."""
    user = baker.make(django_user_model)

    def zrob(tryb="wykonanie", rok_od=2026, rok_do=2026, **pola):
        return UzgodnienieZPBN.objects.create(
            uczelnia=pola.pop("uczelnia", uczelnia_pbn),
            user=user,
            tryb=tryb,
            rok_od=rok_od,
            rok_do=rok_do,
            **pola,
        )

    return zrob


def kategorie(przebieg):
    """``{pbn_uid albo tytuł BPP: kategoria}`` — do zwięzłych asercji."""
    return {
        wpis.get("pbn_uid") or wpis.get("bpp_tytul"): wpis["kategoria"]
        for wpis in przebieg.wynik
    }


def publikacja_w_kopii(pbn_uid):
    return Publication.objects.get(pk=pbn_uid)
