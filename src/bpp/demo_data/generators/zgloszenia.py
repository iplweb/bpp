"""Generator zgłoszeń publikacji (zglos_publikacje) dla danych demo.

Tworzy ``Zgloszenie_Publikacji`` + ``Zgloszenie_Publikacji_Autor`` rozłożone
po wszystkich statusach obiegu zgłoszenia. Zgłoszenia zaakceptowane
i zaimportowane są podpięte (``odpowiednik_w_bpp``) do wygenerowanych
wcześniej prac WC/WZ — dziedziczą po nich tytuł, rok, DOI i autorów.
Pozostałe (nowe, do poprawy, odrzucone, spam) mają własne tytuły z motywu.

Pliki załączników NIE są tworzone: pole ``plik`` wskazywałoby na
nieistniejący plik w chronionym storage, a cleanup musiałby go kasować.
"""

from __future__ import annotations

import datetime
import random
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.utils.text import slugify

from bpp.demo_data.db import bulk_create_retry
from bpp.demo_data.generators._publikacje_common import (
    autor_dyscyplina_mapping,
    autor_jednostka_mapping,
    make_doi,
)
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.progress import make_progress
from bpp.demo_data.themes.base import Theme
from bpp.demo_data.themes.compose import compose_tytul
from bpp.models import (
    Autor,
    Typ_Odpowiedzialnosci,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)
from zglos_publikacje.models import Zgloszenie_Publikacji, Zgloszenie_Publikacji_Autor

Statusy = Zgloszenie_Publikacji.Statusy
Rodzaje = Zgloszenie_Publikacji.Rodzaje
FormyDostepu = Zgloszenie_Publikacji.FormyDostepu

#: Wagi statusów — mniej więcej tak wygląda kolejka zgłoszeń na uczelni:
#: sporo nowych i zaakceptowanych, garść zwrotów, odrzuceń i spamu.
WAGI_STATUSOW: dict[int, int] = {
    Statusy.NOWY: 30,
    Statusy.ZAAKCEPTOWANY: 25,
    Statusy.ZAIMPORTOWANY: 10,
    Statusy.WYMAGA_ZMIAN: 10,
    Statusy.PO_ZMIANACH: 10,
    Statusy.ODRZUCONO: 10,
    Statusy.SPAM: 5,
}

#: Statusy, w których zgłoszenie ma już odpowiednik w BPP.
STATUSY_PODPIETE = (Statusy.ZAAKCEPTOWANY, Statusy.ZAIMPORTOWANY)

#: Rodzaje z nowego formularza (legacy 1/2 pomijamy) i ich wagi.
WAGI_RODZAJOW: dict[int, int] = {
    Rodzaje.ARTYKUL: 50,
    Rodzaje.ROZDZIAL_W_MONOGRAFII: 20,
    Rodzaje.MONOGRAFIA: 15,
    Rodzaje.INNE: 15,
}

DOMENA_EMAIL = "demo.example.org"

PRZYCZYNY_ZWROTU = (
    "Proszę uzupełnić afiliację drugiego autora.",
    "Brak informacji o opłacie za publikację — proszę uzupełnić.",
    "Proszę podać DOI lub adres pełnego tekstu publikacji.",
    "Tytuł w zgłoszeniu różni się od tytułu w czasopiśmie — proszę poprawić.",
    "Proszę wskazać dyscyplinę dla wszystkich autorów z uczelni.",
)

TYTULY_SPAMU = (
    "Tanie pozycjonowanie stron — kup teraz!",
    "Wygrałeś nagrodę, kliknij w link",
    "Najlepsze kasyno online 2026",
    "Kredyt bez BIK w 15 minut",
)


def rozklad_statusow(n: int, rng: random.Random) -> list[int]:
    """Lista n statusów: przy n >= liczby statusów każdy wystąpi co najmniej
    raz (demo ma pokazać cały obieg), reszta losowana wg ``WAGI_STATUSOW``."""
    statusy = list(WAGI_STATUSOW)
    wynik = statusy[:n] if n < len(statusy) else list(statusy)
    reszta = n - len(wynik)
    if reszta > 0:
        wynik += rng.choices(statusy, weights=list(WAGI_STATUSOW.values()), k=reszta)
    rng.shuffle(wynik)
    return wynik


def _email(imiona: str, nazwisko: str) -> str:
    login = slugify(f"{imiona.split()[0]}.{nazwisko}").replace("-", ".")
    return f"{login or 'autor'}@{DOMENA_EMAIL}"


def _oplaty(rng: random.Random, rodzaj: int) -> dict:
    """Pola opłat zgodne z ``ModelZOplataZaPublikacje.clean`` (albo puste)."""
    if rodzaj not in (Rodzaje.ARTYKUL, Rodzaje.MONOGRAFIA) or rng.random() < 0.4:
        return {}
    if rng.random() < 0.5:
        return {
            "opl_pub_cost_free": True,
            "opl_pub_research_potential": False,
            "opl_pub_research_or_development_projects": False,
            "opl_pub_other": False,
            "opl_pub_amount": Decimal("0.00"),
        }
    zrodlo = rng.choice(
        (
            "opl_pub_research_potential",
            "opl_pub_research_or_development_projects",
            "opl_pub_other",
        )
    )
    out = {
        "opl_pub_cost_free": False,
        "opl_pub_research_potential": False,
        "opl_pub_research_or_development_projects": False,
        "opl_pub_other": False,
        "opl_pub_amount": Decimal(rng.randrange(500, 12000, 50)),
    }
    out[zrodlo] = True
    return out


def _dostep(rng: random.Random, idx: int, rok: int, doi: str | None) -> dict:
    """Adres „Dostępna w sieci pod adresem" + forma dostępu."""
    r = rng.random()
    if doi and r < 0.4:
        strona_www = f"https://doi.org/{doi}"
    elif r < 0.75:
        strona_www = f"https://repozytorium.{DOMENA_EMAIL}/handle/demo/{rok}/{idx}"
    else:
        strona_www = ""
    return {
        "strona_www": strona_www,
        "forma_dostepu": rng.choice(
            (FormyDostepu.OTWARTY, FormyDostepu.OGRANICZONY, None)
        ),
        "zgoda_na_publikacje_pelnego_tekstu": rng.random() < 0.5,
    }


def _autorzy_prac(prace: list) -> dict[tuple[type, int], list[tuple]]:
    """(klasa pracy, pk) → [(autor_id, jednostka_id, dyscyplina_id), ...]."""
    out: dict[tuple[type, int], list[tuple]] = {}
    for model, through in (
        (Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor),
        (Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor),
    ):
        pks = [p.pk for p in prace if isinstance(p, model)]
        if not pks:
            continue
        rows = (
            through.objects.filter(rekord_id__in=pks)
            .order_by("rekord_id", "kolejnosc")
            .values_list(
                "rekord_id", "autor_id", "jednostka_id", "dyscyplina_naukowa_id"
            )
        )
        for rekord_id, autor_id, jednostka_id, dyscyplina_id in rows:
            out.setdefault((model, rekord_id), []).append(
                (autor_id, jednostka_id, dyscyplina_id)
            )
    return out


@dataclass
class _Kontekst:
    """Wspólne dane wejściowe budowy pojedynczego zgłoszenia."""

    theme: Theme
    prefix: str
    lata: list[int]
    autorzy_z_jednostka: list[Autor]
    autor_to_jednostka: dict[int, int]
    autor_dyscyplina: dict[tuple[int, int], int]
    autorzy_po_pk: dict[int, Autor]
    autorzy_prac: dict[tuple[type, int], list[tuple]]
    content_types: dict[type, ContentType]


def _pola_podpiete(praca, status: int, k: _Kontekst, pola: dict):
    """Zgłoszenie z odpowiednikiem w BPP: dane i autorzy z pracy."""
    model = type(praca)
    if model is Wydawnictwo_Ciagle:
        rodzaj = Rodzaje.ARTYKUL
    elif praca.wydawnictwo_nadrzedne_id:
        rodzaj = Rodzaje.ROZDZIAL_W_MONOGRAFII
        pola["wydawnictwo_nadrzedne_bpp_id"] = praca.wydawnictwo_nadrzedne_id
    else:
        rodzaj = Rodzaje.MONOGRAFIA
    if model is Wydawnictwo_Zwarte and praca.wydawca_id:
        pola["wydawca_bpp_id"] = praca.wydawca_id
    pola.update(
        tytul_oryginalny=praca.tytul_oryginalny,
        rok=praca.rok,
        doi=praca.doi,
        content_type=k.content_types[model],
        object_id=praca.pk,
    )
    if status == Statusy.ZAIMPORTOWANY:
        pola["zaimportowano"] = pola["ostatnio_zmieniony"]
    return rodzaj, k.autorzy_prac.get((model, praca.pk), [])[:8]


def _pola_wlasne(status: int, idx: int, k: _Kontekst, rng: random.Random, pola: dict):
    """Zgłoszenie bez odpowiednika: tytuł z motywu, losowi autorzy demo."""
    rodzaj = rng.choices(list(WAGI_RODZAJOW), weights=list(WAGI_RODZAJOW.values()))[0]
    rok = rng.choice(k.lata)
    pola.update(
        tytul_oryginalny=f"{k.prefix}{compose_tytul(k.theme, rng)}",
        rok=rok,
        doi=make_doi(rng, rok, 10000 + idx) if rng.random() < 0.5 else None,
    )
    if rodzaj == Rodzaje.ROZDZIAL_W_MONOGRAFII:
        pola["wydawnictwo_nadrzedne_tekst"] = f"{k.prefix}{compose_tytul(k.theme, rng)}"
    zwarte = (Rodzaje.MONOGRAFIA, Rodzaje.ROZDZIAL_W_MONOGRAFII)
    if rodzaj in zwarte and k.theme.wydawcy:
        pola["wydawca_zgloszenia"] = rng.choice(k.theme.wydawcy)
    if status == Statusy.WYMAGA_ZMIAN:
        pola["przyczyna_zwrotu"] = rng.choice(PRZYCZYNY_ZWROTU)
        pola["kod_do_edycji"] = uuid.UUID(int=rng.getrandbits(128), version=4)

    autorzy = []
    if k.autorzy_z_jednostka:
        ile = rng.randint(1, min(5, len(k.autorzy_z_jednostka)))
        autorzy = [
            (
                autor.pk,
                k.autor_to_jednostka[autor.pk],
                k.autor_dyscyplina.get((autor.pk, rok)),
            )
            for autor in rng.sample(k.autorzy_z_jednostka, ile)
        ]
    return rodzaj, autorzy


def _zbuduj_zgloszenie(
    *,
    idx: int,
    status: int,
    praca,
    k: _Kontekst,
    rng: random.Random,
    teraz: datetime.datetime,
) -> tuple[Zgloszenie_Publikacji, list[tuple]]:
    """Jedno (niezapisane) zgłoszenie + lista (autor, jednostka, dyscyplina)."""
    utworzono = teraz - datetime.timedelta(
        days=rng.randint(1, 365), minutes=rng.randint(0, 24 * 60)
    )
    pola: dict = {
        "status": status,
        "utworzono": utworzono,
        "ostatnio_zmieniony": utworzono
        + datetime.timedelta(minutes=rng.randint(5, 14 * 24 * 60)),
    }

    if praca is not None:
        rodzaj, autorzy = _pola_podpiete(praca, status, k, pola)
    elif status == Statusy.SPAM:
        rodzaj, autorzy = Rodzaje.INNE, []
        pola.update(
            tytul_oryginalny=f"{k.prefix}{rng.choice(TYTULY_SPAMU)}",
            rok=rng.choice(k.lata),
            strona_www=f"https://spam-{idx}.example.com/",
        )
    else:
        rodzaj, autorzy = _pola_wlasne(status, idx, k, rng, pola)

    if status != Statusy.SPAM:
        pola.update(_dostep(rng, idx, pola["rok"], pola.get("doi")))
        pola.update(_oplaty(rng, rodzaj))

    pierwszy = k.autorzy_po_pk.get(autorzy[0][0]) if autorzy else None
    pola["email"] = (
        _email(pierwszy.imiona, pierwszy.nazwisko)
        if pierwszy
        else f"zglaszajacy{idx}@{DOMENA_EMAIL}"
    )
    return Zgloszenie_Publikacji(rodzaj_zglaszanej_publikacji=rodzaj, **pola), autorzy


def _zapisz_zgloszenia(
    zgloszenia: list[Zgloszenie_Publikacji],
    *,
    manifest: Manifest,
    batch_size: int,
    disable_progress: bool,
) -> None:
    pbar = make_progress(
        range(0, len(zgloszenia), batch_size),
        desc="Zgłoszenia publikacji",
        total=(len(zgloszenia) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    for start in pbar:
        chunk = zgloszenia[start : start + batch_size]
        # Pola auto_now(_add) bulk_create nadpisuje bieżącym czasem — zapamiętaj
        # wylosowane daty i przywróć je bulk_update-em (on nie woła pre_save).
        daty = [(z.utworzono, z.ostatnio_zmieniony) for z in chunk]
        bulk_create_retry(Zgloszenie_Publikacji.objects, chunk)
        manifest.append("zglos_publikacje.Zgloszenie_Publikacji", [z.pk for z in chunk])
        manifest.save()
        for z, (utworzono, zmieniony) in zip(chunk, daty, strict=True):
            z.utworzono, z.ostatnio_zmieniony = utworzono, zmieniony
        Zgloszenie_Publikacji.objects.bulk_update(
            chunk, ["utworzono", "ostatnio_zmieniony"]
        )


def create_zgloszenia(
    *,
    n: int,
    autorzy: Iterable[Autor],
    prace_wc: Iterable[Wydawnictwo_Ciagle],
    prace_wz: Iterable[Wydawnictwo_Zwarte],
    lata: Iterable[int],
    theme: Theme,
    manifest: Manifest,
    rng: random.Random,
    prefix: str = "",
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list[Zgloszenie_Publikacji]:
    """Tworzy n zgłoszeń publikacji + ich autorów."""
    if n <= 0:
        return []
    autorzy = list(autorzy)
    lata = list(lata)
    if not lata:
        raise ValueError("Brak lat — pusty zakres.")

    aut_typ = (
        Typ_Odpowiedzialnosci.objects.filter(skrot="aut.").first()
        or Typ_Odpowiedzialnosci.objects.first()
    )
    if aut_typ is None:
        raise ValueError("Brak Typ_Odpowiedzialnosci w bazie.")

    statusy = rozklad_statusow(n, rng)
    # Zaakceptowane/zaimportowane dostają WŁASNĄ (unikalną) pracę z bazy.
    # Brak prac → takie zgłoszenie zostaje „nowe" (nie ma czego podpiąć).
    prace = list(prace_wc) + list(prace_wz)
    ile_podpietych = sum(1 for s in statusy if s in STATUSY_PODPIETE)
    do_podpiecia = rng.sample(prace, min(ile_podpietych, len(prace)))

    autor_to_jednostka = autor_jednostka_mapping(autorzy)
    autorzy_z_jednostka = [a for a in autorzy if a.pk in autor_to_jednostka]
    k = _Kontekst(
        theme=theme,
        prefix=prefix,
        lata=lata,
        autorzy_z_jednostka=autorzy_z_jednostka,
        autor_to_jednostka=autor_to_jednostka,
        autor_dyscyplina=autor_dyscyplina_mapping(autorzy_z_jednostka),
        autorzy_po_pk={a.pk: a for a in autorzy},
        autorzy_prac=_autorzy_prac(do_podpiecia),
        content_types={
            m: ContentType.objects.get_for_model(m)
            for m in (Wydawnictwo_Ciagle, Wydawnictwo_Zwarte)
        },
    )

    teraz = timezone.now()
    zgloszenia: list[Zgloszenie_Publikacji] = []
    autorzy_zgloszen: list[list[tuple]] = []
    for idx, status in enumerate(statusy, start=1):
        praca = None
        if status in STATUSY_PODPIETE:
            if do_podpiecia:
                praca = do_podpiecia.pop()
            else:
                status = Statusy.NOWY
        zgl, autorzy_zgl = _zbuduj_zgloszenie(
            idx=idx, status=status, praca=praca, k=k, rng=rng, teraz=teraz
        )
        zgloszenia.append(zgl)
        autorzy_zgloszen.append(autorzy_zgl)

    _zapisz_zgloszenia(
        zgloszenia,
        manifest=manifest,
        batch_size=batch_size,
        disable_progress=disable_progress,
    )

    def zapisany_jako(autor_id: int) -> str:
        autor = k.autorzy_po_pk.get(autor_id)
        return f"{autor.imiona} {autor.nazwisko}" if autor else ""

    powiazania = [
        Zgloszenie_Publikacji_Autor(
            rekord=zgl,
            autor_id=autor_id,
            jednostka_id=jednostka_id,
            dyscyplina_naukowa_id=dyscyplina_id,
            typ_odpowiedzialnosci=aut_typ,
            kolejnosc=kolejnosc,
            zapisany_jako=zapisany_jako(autor_id),
            afiliuje=True,
            rok=zgl.rok,
        )
        for zgl, lista in zip(zgloszenia, autorzy_zgloszen, strict=True)
        for kolejnosc, (autor_id, jednostka_id, dyscyplina_id) in enumerate(lista)
    ]
    for start in range(0, len(powiazania), batch_size):
        chunk = powiazania[start : start + batch_size]
        bulk_create_retry(Zgloszenie_Publikacji_Autor.objects, chunk)
        manifest.append(
            "zglos_publikacje.Zgloszenie_Publikacji_Autor", [p.pk for p in chunk]
        )
        manifest.save()

    return zgloszenia
