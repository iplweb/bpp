"""Lokalne lustro PBN dla danych demo — bez sieci i bez tokenu.

Wypełnia tabele ``pbn_api`` tak, jakby BPP pobrało je z PBN, i łączy je
z rekordami demo (``pbn_uid``):

- instytucja (uczelnia demo), czasopisma (punkty i dyscypliny z punktacji
  demo), wydawcy (punkty z poziomów), naukowcy (autorzy z dyscypliną),
  publikacje (ok. 70% prac), oświadczenia instytucji (dyscypliny autorów),
  historia wysyłki (``SentData``: wysłane, błąd, w toku);
- celowe różnice, żeby komparatory miały co pokazać: inna punktacja lub
  dodatkowa dyscyplina czasopisma, literówka w tytule / brakujący autor /
  inny DOI publikacji, inna dyscyplina w oświadczeniu, oświadczenie autora
  spoza publikacji, publikacje i naukowcy obecni tylko w PBN, czasopisma
  usunięte w PBN (z aktywnym następcą o tym samym ISSN — do przemapowania).

Porównań BPP↔PBN generator nie uruchamia — robi to użytkownik (przyciski
„Przebuduj”/„Przelicz” na ekranach rozbieżności). Wpisy „pobrano z PBN”
(czasopisma, publikacje, osoby z instytucji) mają datę wygenerowania danych
demo i nie mają użytkownika („system”), więc ekrany PBN traktują dane jako
świeżo pobrane (przez 7 dni, jak po prawdziwym pobraniu).
"""

from __future__ import annotations

import datetime
import random
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from bpp.demo_data.db import bulk_create_z_manifestem
from bpp.demo_data.manifest import Manifest
from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Dyscyplina_Naukowa,
    Dyscyplina_Zrodla,
    Punktacja_Zrodla,
    Uczelnia,
    Wydawca,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
    Zrodlo,
)

PROCENT_PRAC_W_PBN = 70
PROCENT_ROZNIC_PUBLIKACJI = 5
PROCENT_ROZNIC_OSWIADCZEN = 4
PUNKTY_POZIOMU_WYDAWCY = {1: 80, 2: 200}

BLAD_WYSYLKI = (
    '{"code": 400, "message": "Bad Request", "description": "Validation '
    'failed.", "details": {"doi": "Nieprawidłowy format DOI"}}'
)


def mongo_id(rng: random.Random) -> str:
    """24 znaki hex — jak identyfikatory obiektów PBN (MongoDB)."""
    return f"{rng.getrandbits(96):024x}"


def kod_pbn(kod_bpp: str) -> str:
    """Kod dyscypliny BPP („5.3", „10.1") → kod PBN („503", „1001")."""
    dziedzina, nr = kod_bpp.split(".")
    return f"{dziedzina}{int(nr):02d}"


def _wersja(obiekt: dict) -> list[dict]:
    return [{"current": True, "object": obiekt}]


@dataclass
class LustroPBN:
    journals: list = field(default_factory=list)
    publishers: list = field(default_factory=list)
    scientists: list = field(default_factory=list)
    publications: list = field(default_factory=list)
    oswiadczenia: list = field(default_factory=list)
    sentdata: list = field(default_factory=list)

    def tekst(self) -> str:
        return (
            f"[OK] Lustro PBN: {len(self.journals)} czasopism, "
            f"{len(self.publishers)} wydawców, {len(self.scientists)} naukowców, "
            f"{len(self.publications)} publikacji, "
            f"{len(self.oswiadczenia)} oświadczeń, "
            f"{len(self.sentdata)} wpisów historii wysyłki.\n"
        )


def _instytucja(uczelnia, rng, bulk):
    from pbn_api.models import Institution

    obiekt = {
        "name": uczelnia.nazwa,
        "addressCity": "Demo",
        "addressStreet": "ul. Przykładowa",
        "addressStreetNumber": "1",
        "addressPostalCode": "00-001",
        "polonUid": "",
    }
    instytucja = Institution(
        mongoId=mongo_id(rng),
        status="ACTIVE",
        verificationLevel="MODERATOR",
        verified=True,
        versions=_wersja(obiekt),
        **obiekt,
    )
    bulk_create_z_manifestem(
        [instytucja],
        model=Institution,
        label="pbn_api.Institution",
        desc="PBN — instytucja",
        **bulk,
    )
    if uczelnia.pbn_uid_id is None:
        Uczelnia.objects.filter(pk=uczelnia.pk).update(pbn_uid=instytucja)
    return instytucja


def _czasopisma(zrodla, rng, bulk, wynik):
    """Journal dla każdego czasopisma demo. 2 z nich „usunięte w PBN" mają
    aktywnego następcę (ten sam ISSN) bez odpowiednika w BPP."""
    from pbn_api.models import Journal

    punkty = defaultdict(dict)
    for zrodlo_id, rok, p in Punktacja_Zrodla.objects.filter(
        zrodlo__in=zrodla
    ).values_list("zrodlo_id", "rok", "punkty_kbn"):
        punkty[zrodlo_id][rok] = int(p)
    ostatnie_dyscypliny = {}
    for zrodlo_id, rok, kod, nazwa in (
        Dyscyplina_Zrodla.objects.filter(zrodlo__in=zrodla)
        .order_by("zrodlo_id", "rok")
        .values_list("zrodlo_id", "rok", "dyscyplina__kod", "dyscyplina__nazwa")
    ):
        lista = ostatnie_dyscypliny.setdefault(zrodlo_id, {})
        lista.setdefault(rok, []).append({"code": kod_pbn(kod), "name": nazwa})
    wszystkie = [
        {"code": kod_pbn(kod), "name": nazwa}
        for kod, nazwa in Dyscyplina_Naukowa.objects.order_by("pk").values_list(
            "kod", "nazwa"
        )
        if kod and "." in kod
    ]

    usuniete = set(rng.sample(range(len(zrodla)), min(2, len(zrodla) // 10)))
    journals, nastepcy = [], []
    for i, zrodlo in enumerate(zrodla):
        punkty_zrodla = {
            str(rok): {"points": p, "accepted": True}
            for rok, p in punkty[zrodlo.pk].items()
        }
        roczne = ostatnie_dyscypliny.get(zrodlo.pk, {})
        dyscypliny = list(roczne[max(roczne)]) if roczne else []
        los = rng.randint(1, 100)
        if punkty_zrodla and los <= 10:
            # Różnica punktacji w jednym roku:
            rok = rng.choice(sorted(punkty_zrodla))
            punkty_zrodla[rok] = {
                "points": punkty_zrodla[rok]["points"] + 20,
                "accepted": True,
            }
        elif wszystkie and los <= 15:
            # Dodatkowa dyscyplina w PBN (rozbieżność w każdym roku):
            dyscypliny.append(rng.choice(wszystkie))
        obiekt = {
            "title": zrodlo.nazwa,
            "issn": zrodlo.issn or "",
            "eissn": "",
            "websiteLink": "",
            "mniswId": 100000 + i,
            "points": punkty_zrodla,
            "disciplines": dyscypliny,
        }
        journals.append(
            Journal(
                mongoId=mongo_id(rng),
                status="DELETED" if i in usuniete else "ACTIVE",
                verificationLevel="MODERATOR",
                verified=True,
                versions=_wersja(obiekt),
                title=obiekt["title"],
                issn=obiekt["issn"],
                eissn="",
                websiteLink="",
                mniswId=obiekt["mniswId"],
            )
        )
        if i in usuniete:
            obiekt = dict(obiekt, mniswId=200000 + i)
            nastepcy.append(
                Journal(
                    mongoId=mongo_id(rng),
                    status="ACTIVE",
                    verificationLevel="MODERATOR",
                    verified=True,
                    versions=_wersja(obiekt),
                    title=obiekt["title"],
                    issn=obiekt["issn"],
                    eissn="",
                    websiteLink="",
                    mniswId=obiekt["mniswId"],
                )
            )
    bulk_create_z_manifestem(
        journals + nastepcy,
        model=Journal,
        label="pbn_api.Journal",
        desc="PBN — czasopisma",
        **bulk,
    )
    for zrodlo, journal in zip(zrodla, journals, strict=True):
        zrodlo.pbn_uid = journal
    Zrodlo.objects.bulk_update(zrodla, ["pbn_uid"], batch_size=500)
    wynik.journals = journals + nastepcy
    return dict(zip([z.pk for z in zrodla], journals, strict=True))


def _wydawcy(wydawcy, lata, rng, bulk, wynik):
    from bpp.demo_data.generators.punktacja import poziomy_wydawcow_mapping
    from pbn_api.models import Publisher

    poziomy = poziomy_wydawcow_mapping([w.pk for w in wydawcy])
    publishers = []
    for i, wydawca in enumerate(wydawcy):
        punkty = {
            str(rok): {"points": PUNKTY_POZIOMU_WYDAWCY[p], "accepted": True}
            for rok in lata
            if (p := poziomy.get((wydawca.pk, rok))) in PUNKTY_POZIOMU_WYDAWCY
        }
        obiekt = {
            "publisherName": wydawca.nazwa,
            "mniswId": 300000 + i if punkty else None,
            "points": punkty,
        }
        publishers.append(
            Publisher(
                mongoId=mongo_id(rng),
                status="ACTIVE",
                verificationLevel="MODERATOR",
                verified=True,
                versions=_wersja(obiekt),
                publisherName=wydawca.nazwa,
                mniswId=obiekt["mniswId"],
            )
        )
    bulk_create_z_manifestem(
        publishers,
        model=Publisher,
        label="pbn_api.Publisher",
        desc="PBN — wydawcy",
        **bulk,
    )
    for wydawca, publisher in zip(wydawcy, publishers, strict=True):
        wydawca.pbn_uid = publisher
    Wydawca.objects.bulk_update(wydawcy, ["pbn_uid"], batch_size=500)
    wynik.publishers = publishers


def _scientist(imiona, nazwisko, instytucja, uczelnia, rng):
    from pbn_api.models import Scientist

    obiekt = {
        "name": imiona,
        "lastName": nazwisko,
        "qualifications": "",
        "orcid": "",
        "polonUid": "",
        "currentEmployments": [
            {
                "institutionId": instytucja.mongoId,
                "institutionDisplayName": uczelnia.nazwa,
                "from": "2015-10-01",
            }
        ],
    }
    return Scientist(
        mongoId=mongo_id(rng),
        status="ACTIVE",
        verificationLevel="MODERATOR",
        verified=True,
        versions=_wersja(obiekt),
        from_institution_api=True,
        name=imiona,
        lastName=nazwisko,
        pbnId=str(rng.randint(10_000_000, 99_999_999)),
    )


def _naukowcy(autorzy, instytucja, uczelnia, theme_nazwy, rng, bulk, wynik):
    """Scientist dla autorów z dyscypliną + 3 naukowców tylko w PBN."""
    from pbn_api.models import Scientist

    z_dyscyplina = set(
        Autor_Dyscyplina.objects.filter(autor__in=autorzy).values_list(
            "autor_id", flat=True
        )
    )
    autorzy = [a for a in autorzy if a.pk in z_dyscyplina]
    scientists = [
        _scientist(a.imiona, a.nazwisko, instytucja, uczelnia, rng) for a in autorzy
    ]
    tylko_w_pbn = [
        _scientist(imiona, nazwisko, instytucja, uczelnia, rng)
        for imiona, nazwisko in theme_nazwy
    ]
    bulk_create_z_manifestem(
        scientists + tylko_w_pbn,
        model=Scientist,
        label="pbn_api.Scientist",
        desc="PBN — naukowcy",
        **bulk,
    )
    for autor, scientist in zip(autorzy, scientists, strict=True):
        autor.pbn_uid = scientist
    Autor.objects.bulk_update(autorzy, ["pbn_uid"], batch_size=500)
    wynik.scientists = scientists + tylko_w_pbn
    return {a.pk: s for a, s in zip(autorzy, scientists, strict=True)}


def _autorzy_prac(model_autora, prace):
    """rekord_id -> [(autor_id, nazwisko, imiona, dyscyplina, afiliuje)]."""
    wynik = defaultdict(list)
    for rekord_id, autor_id, nazwisko, imiona, dyscyplina, afiliuje in (
        model_autora.objects.filter(rekord__in=prace)
        .order_by("rekord_id", "kolejnosc")
        .values_list(
            "rekord_id",
            "autor_id",
            "autor__nazwisko",
            "autor__imiona",
            "dyscyplina_naukowa__nazwa",
            "afiliuje",
        )
    ):
        wynik[rekord_id].append((autor_id, nazwisko, imiona, dyscyplina, afiliuje))
    return wynik


def _publication(obiekt: dict, rng):
    from pbn_api.models import Publication

    return Publication(
        mongoId=mongo_id(rng),
        status="ACTIVE",
        verificationLevel="MODERATOR",
        verified=True,
        versions=_wersja(obiekt),
        title=obiekt["title"],
        doi=obiekt.get("doi", ""),
        year=obiekt["year"],
        isbn=obiekt.get("isbn", ""),
        publicUri="",
    )


def _obiekt_publikacji(model, praca, autorzy, zrodlo_journal, rng) -> dict:
    """JSON publikacji PBN dla pracy; ~5% z celową różnicą (tytuł, DOI albo
    brakujący autor) — do pokazania w komparatorze publikacji."""
    tytul, doi = praca.tytul_oryginalny, praca.doi or ""
    autorzy_pbn = [{"lastName": n, "firstName": i} for _a, n, i, _d, _f in autorzy]
    if rng.randint(1, 100) <= PROCENT_ROZNIC_PUBLIKACJI:
        roznica = rng.choice(("tytul", "doi", "autor"))
        if roznica == "tytul":
            tytul = tytul.replace("a", "ą", 1)
        elif roznica == "doi" and doi:
            doi = doi + "0"
        elif len(autorzy_pbn) > 1:
            autorzy_pbn = autorzy_pbn[:-1]
    obiekt = {"title": tytul, "year": praca.rok, "doi": doi, "authors": autorzy_pbn}
    if model is Wydawnictwo_Zwarte:
        obiekt["type"] = "CHAPTER" if praca.wydawnictwo_nadrzedne_id else "BOOK"
        obiekt["isbn"] = praca.isbn or ""
        return obiekt
    obiekt["type"] = "ARTICLE"
    journal = zrodlo_journal.get(praca.zrodlo_id)
    if journal is not None:
        obiekt["journal"] = {
            "id": journal.mongoId,
            "title": journal.title,
            "issn": journal.issn,
        }
    return obiekt


def _publikacje(prace_wc, prace_wz, zrodlo_journal, rng, bulk, wynik):
    """Publication dla ~70% prac (z celowymi różnicami) + 5 tylko w PBN.

    Zwraca listę (model, praca, publication, autorzy_pracy)."""
    from pbn_api.models import Publication

    powiazane = []
    for model, model_autora, prace in (
        (Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor, prace_wc),
        (Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor, prace_wz),
    ):
        wybrane = [p for p in prace if rng.randint(1, 100) <= PROCENT_PRAC_W_PBN]
        autorzy_prac = _autorzy_prac(model_autora, wybrane)
        for praca in wybrane:
            autorzy = autorzy_prac.get(praca.pk, [])
            obiekt = _obiekt_publikacji(model, praca, autorzy, zrodlo_journal, rng)
            powiazane.append((model, praca, _publication(obiekt, rng), autorzy))

    lata = sorted({p.rok for _m, p, _pub, _a in powiazane}) or [2023]
    tylko_w_pbn = [
        _publication(
            {
                "title": f"Publikacja obecna tylko w PBN nr {i + 1}",
                "year": rng.choice(lata),
                "type": "ARTICLE",
            },
            rng,
        )
        for i in range(5)
    ]
    bulk_create_z_manifestem(
        [pub for _m, _p, pub, _a in powiazane] + tylko_w_pbn,
        model=Publication,
        label="pbn_api.Publication",
        desc="PBN — publikacje",
        **bulk,
    )
    for model in (Wydawnictwo_Ciagle, Wydawnictwo_Zwarte):
        prace = []
        for m, praca, publication, _a in powiazane:
            if m is model:
                praca.pbn_uid = publication
                prace.append(praca)
        model.objects.bulk_update(prace, ["pbn_uid"], batch_size=500)
    wynik.publications = [pub for _m, _p, pub, _a in powiazane] + tylko_w_pbn
    return powiazane


def _oswiadczenia(powiazane, autor_scientist, instytucja, uczelnia, rng, bulk, wynik):
    from pbn_api.models import OswiadczenieInstytucji

    nazwy_dyscyplin = list(
        Dyscyplina_Naukowa.objects.order_by("pk").values_list("nazwa", flat=True)
    )
    scientists = list(autor_scientist.values())
    oswiadczenia = []
    for _model, praca, publication, autorzy in powiazane:
        for autor_id, _n, _i, dyscyplina, afiliuje in autorzy:
            scientist = autor_scientist.get(autor_id)
            if not (dyscyplina and afiliuje and scientist):
                continue
            los = rng.randint(1, 100)
            if los <= PROCENT_ROZNIC_OSWIADCZEN and len(nazwy_dyscyplin) > 1:
                dyscyplina = rng.choice([d for d in nazwy_dyscyplin if d != dyscyplina])
            elif los == 100:
                # Oświadczenie naukowca, którego w BPP nie ma przy tej pracy:
                scientist = rng.choice(scientists)
            oswiadczenia.append(
                OswiadczenieInstytucji(
                    addedTimestamp=datetime.date(min(praca.rok + 1, 2026), 1, 15),
                    statedTimestamp=datetime.date(min(praca.rok + 1, 2026), 1, 15),
                    inOrcid=False,
                    institutionId=instytucja,
                    personId=scientist,
                    publicationId=publication,
                    uczelnia=uczelnia,
                    type="AUTHOR",
                    disciplines={"name": dyscyplina},
                )
            )
    bulk_create_z_manifestem(
        oswiadczenia,
        model=OswiadczenieInstytucji,
        label="pbn_api.OswiadczenieInstytucji",
        desc="PBN — oświadczenia",
        **bulk,
    )
    wynik.oswiadczenia = oswiadczenia


def _historia_wysylki(powiazane, uczelnia, rng, bulk, wynik):
    """SentData: ~85% wysłane, ~10% błąd, ~5% w toku."""
    from pbn_api.models import SentData

    ct = {
        m: ContentType.objects.get_for_model(m)
        for m in (Wydawnictwo_Ciagle, Wydawnictwo_Zwarte)
    }
    teraz = timezone.now()
    wpisy = []
    for model, praca, publication, _a in powiazane:
        typ = publication.versions[0]["object"]["type"]
        kiedy = teraz - datetime.timedelta(days=rng.randint(1, 400))
        los = rng.randint(1, 100)
        wpis = SentData(
            content_type=ct[model],
            object_id=praca.pk,
            uczelnia=uczelnia,
            data_sent={"type": typ, "title": publication.title, "year": praca.rok},
            typ_rekordu=typ,
            submitted_at=kiedy,
            api_url="/api/v1/publications",
        )
        if los <= 85:
            wpis.uploaded_okay = True
            wpis.submitted_successfully = True
            wpis.api_response_status = "200"
            wpis.pbn_uid = publication
        elif los <= 95:
            wpis.uploaded_okay = False
            wpis.submitted_successfully = False
            wpis.api_response_status = "400"
            wpis.exception = BLAD_WYSYLKI
        else:
            wpis.uploaded_okay = False
            wpis.submitted_successfully = False
        wpisy.append(wpis)
    bulk_create_z_manifestem(
        wpisy,
        model=SentData,
        label="pbn_api.SentData",
        desc="PBN — historia wysyłki",
        **bulk,
    )
    wynik.sentdata = wpisy


def _znaczniki_pobrania(bulk) -> None:
    """Wpisy „pobrano z PBN” (publikacje, osoby z instytucji, czasopisma)
    z chwilą wygenerowania danych demo — jakbyśmy właśnie pobrali dane.
    Bez użytkownika (ekrany pokazują „system”): na świeżej instalacji
    (bpp-wsl) nie ma jeszcze żadnego konta."""
    from pbn_downloader_app.models import (
        PbnDownloadTask,
        PbnInstitutionPeopleTask,
        PbnJournalsDownloadTask,
    )

    teraz = timezone.now()
    for model in (PbnDownloadTask, PbnInstitutionPeopleTask, PbnJournalsDownloadTask):
        bulk_create_z_manifestem(
            [model(user=None, status="completed", completed_at=teraz)],
            model=model,
            label=f"pbn_downloader_app.{model.__name__}",
            desc=f"PBN — {model.__name__}",
            **bulk,
        )


def create_lustro_pbn(
    *,
    uczelnia,
    autorzy: Iterable[Autor],
    zrodla: Iterable[Zrodlo],
    wydawcy: Iterable[Wydawca],
    prace_wc: Iterable[Wydawnictwo_Ciagle],
    prace_wz: Iterable[Wydawnictwo_Zwarte],
    lata: Iterable[int],
    theme,
    manifest: Manifest,
    rng: random.Random,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> LustroPBN:
    from bpp.demo_data.themes.compose import compose_autor

    bulk = {
        "manifest": manifest,
        "batch_size": batch_size,
        "disable_progress": disable_progress,
    }
    wynik = LustroPBN()
    instytucja = _instytucja(uczelnia, rng, bulk)
    zrodlo_journal = _czasopisma(list(zrodla), rng, bulk, wynik)
    _wydawcy(list(wydawcy), list(lata), rng, bulk, wynik)
    autor_scientist = _naukowcy(
        list(autorzy),
        instytucja,
        uczelnia,
        [compose_autor(theme, rng) for _ in range(3)],
        rng,
        bulk,
        wynik,
    )
    powiazane = _publikacje(
        list(prace_wc), list(prace_wz), zrodlo_journal, rng, bulk, wynik
    )
    _oswiadczenia(powiazane, autor_scientist, instytucja, uczelnia, rng, bulk, wynik)
    _historia_wysylki(powiazane, uczelnia, rng, bulk, wynik)
    _znaczniki_pobrania(bulk)
    return wynik
