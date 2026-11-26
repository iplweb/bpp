"""Dyscypliny z oświadczeń instytucji w PBN (FD#477, decyzja właściciela).

Nowo utworzony rekord dostaje dyscypliny autorów z oświadczeń złożonych na
profilu instytucji w PBN. Reguła jest ŚCISŁA — niczego nie zgadujemy:

* autor rekordu to dokładnie ta osoba z PBN (ten sam PBN UID i rola),
* dyscyplina z oświadczenia istnieje w słowniku BPP,
* autor ma tę dyscyplinę przypisaną w BPP na rok pracy.

Gdy któryś warunek nie jest spełniony, autor zostaje bez dyscypliny,
a raport podaje powód. (Dotychczasowy import oświadczeń robi więcej:
dopasowuje osoby po nazwisku i sam dopisuje autorowi dyscyplinę na dany
rok — dlatego nie jest tu używany.)

W rekordach, które już w BPP były, dyscyplin nie zmieniamy — różnice idą
do raportu.
"""

import datetime
import logging

from django.core.exceptions import ValidationError
from django.db.models import Q

from bpp import const
from bpp.models import Autor_Dyscyplina, Dyscyplina_Naukowa
from pbn_api.exceptions import HttpException
from pbn_integrator.utils.mongodb_ops import zapisz_oswiadczenie_instytucji

logger = logging.getLogger(__name__)

ROLE = {const.TO_AUTOR: "AUTHOR", const.TO_REDAKTOR: "EDITOR"}


def pobierz_oswiadczenia(client, uczelnia, pbn_uid, blad):
    """Oświadczenia instytucji dla jednej publikacji, prosto z PBN.

    Zapisuje je też w lokalnej kopii (dla komparatorów). Zwraca listę
    słowników ``{osoba, rola, dyscyplina, w_orcid, data}`` — to ona, a nie
    lokalna kopia, jest podstawą dalszych decyzji: kopia nie zapomina
    oświadczeń wycofanych w PBN.

    ``blad(opis)`` — zgłoszenie błędu PBN (log z tracebackiem + raport);
    przy błędzie zwraca ``None`` („nie wiadomo”), nie pustą listę.
    """
    try:
        elementy = list(
            client.get_institution_statements_of_single_publication(pbn_uid)
        )
    except HttpException as e:
        blad(f"Nie pobrano oświadczeń: {e}")
        return None

    wynik = []
    for elem in elementy:
        if elem.get("institutionId") != uczelnia.pbn_uid_id:
            continue
        wynik.append(
            {
                "osoba": elem.get("personId"),
                "rola": elem.get("type"),
                "dyscyplina": (elem.get("disciplines") or {}).get("name") or "",
                "w_orcid": bool(elem.get("inOrcid")),
                "data": (elem.get("statedTimestamp") or "").replace(".", "-"),
            }
        )
        try:
            zapisz_oswiadczenie_instytucji(dict(elem), None, client=client)
        except HttpException as e:
            blad(f"Nie zapisano oświadczenia w lokalnej kopii: {e}")
    return wynik


def _po_osobie_i_roli(oswiadczenia):
    return {(o["osoba"], o["rola"]): o for o in oswiadczenia or []}


def _wiersze(rekord):
    if not hasattr(rekord, "autorzy_set"):
        return []
    return list(
        rekord.autorzy_set.select_related(
            "autor", "typ_odpowiedzialnosci", "dyscyplina_naukowa"
        ).order_by("kolejnosc")
    )


def _klucz(wiersz):
    return (
        wiersz.autor.pbn_uid_id,
        ROLE.get(wiersz.typ_odpowiedzialnosci.typ_ogolny),
    )


def _dyscyplina_bpp(nazwa):
    """Dyscyplina ze słownika BPP o DOKŁADNIE tej nazwie albo ``None``."""
    kandydaci = list(Dyscyplina_Naukowa.objects.filter(nazwa=nazwa)[:2])
    return kandydaci[0] if len(kandydaci) == 1 else None


def _data(tekst):
    try:
        return datetime.date.fromisoformat(tekst) if tekst else None
    except ValueError:
        return None


def _przypisz(wiersz, oswiadczenie, rok):
    """Próbuje przypisać dyscyplinę jednemu autorowi → ``(ok, powód)``."""
    nazwa = oswiadczenie["dyscyplina"]
    if not nazwa:
        return False, "Oświadczenie w PBN nie wskazuje dyscypliny."
    dyscyplina = _dyscyplina_bpp(nazwa)
    if dyscyplina is None:
        return False, f"Dyscypliny „{nazwa}” nie ma w słowniku dyscyplin BPP."
    if not Autor_Dyscyplina.objects.filter(
        Q(dyscyplina_naukowa=dyscyplina) | Q(subdyscyplina_naukowa=dyscyplina),
        autor=wiersz.autor,
        rok=rok,
    ).exists():
        return False, (
            f"Autor nie ma w BPP przypisanej dyscypliny „{nazwa}” na rok {rok} — "
            "uzupełnij dyscypliny autora i przypisz ją w rekordzie."
        )

    wiersz.dyscyplina_naukowa = dyscyplina
    wiersz.profil_orcid = oswiadczenie["w_orcid"]
    data = _data(oswiadczenie["data"])
    if data:
        wiersz.data_oswiadczenia = data
    try:
        wiersz.save()
    except ValidationError as e:
        # Reguły rekordu (np. dyscyplina tylko przy afiliacji) — nie obchodzimy.
        wiersz.refresh_from_db()
        return False, f"BPP nie przyjął dyscypliny: {'; '.join(e.messages)}"
    return True, ""


def zastosuj_do_nowego_rekordu(rekord, oswiadczenia):
    """Ustawia dyscypliny w NOWYM rekordzie; zwraca wpisy do raportu.

    Wpis: ``{osoba, dyscyplina, przypisano: bool, powod}`` — po jednym na
    autora afiliowanego albo mającego oświadczenie, plus oświadczenia osób,
    których w rekordzie nie ma.
    """
    if oswiadczenia is None:
        return [
            {
                "osoba": "(wszyscy)",
                "dyscyplina": "",
                "przypisano": False,
                "powod": "Nie udało się pobrać oświadczeń z PBN — dyscyplin "
                "nie przypisano.",
            }
        ]

    po_kluczu = _po_osobie_i_roli(oswiadczenia)
    wpisy = []
    for wiersz in _wiersze(rekord):
        oswiadczenie = po_kluczu.pop(_klucz(wiersz), None)
        if oswiadczenie is None:
            if wiersz.afiliuje:
                wpisy.append(
                    {
                        "osoba": str(wiersz.autor),
                        "dyscyplina": "",
                        "przypisano": False,
                        "powod": "Brak oświadczenia tej osoby na profilu "
                        "instytucji w PBN.",
                    }
                )
            continue
        ok, powod = _przypisz(wiersz, oswiadczenie, rekord.rok)
        wpisy.append(
            {
                "osoba": str(wiersz.autor),
                "dyscyplina": oswiadczenie["dyscyplina"],
                "przypisano": ok,
                "powod": powod,
            }
        )

    for oswiadczenie in po_kluczu.values():
        wpisy.append(
            {
                "osoba": f"osoba PBN {oswiadczenie['osoba']}",
                "dyscyplina": oswiadczenie["dyscyplina"],
                "przypisano": False,
                "powod": "W PBN jest oświadczenie osoby, której nie ma wśród "
                "autorów/redaktorów rekordu w tej roli.",
            }
        )
    return wpisy


def roznice_dyscyplin(rekord, oswiadczenia):
    """Różnice dyscyplin ISTNIEJĄCEGO rekordu względem oświadczeń (raport)."""
    if oswiadczenia is None:
        return []
    po_kluczu = _po_osobie_i_roli(oswiadczenia)
    roznice = []
    for wiersz in _wiersze(rekord):
        if not wiersz.autor.pbn_uid_id:
            continue
        oswiadczenie = po_kluczu.get(_klucz(wiersz))
        w_pbn = oswiadczenie["dyscyplina"] if oswiadczenie else ""
        w_bpp = wiersz.dyscyplina_naukowa.nazwa if wiersz.dyscyplina_naukowa else ""
        if w_pbn != w_bpp:
            roznice.append(
                {
                    "pole": f"Dyscyplina ({wiersz.autor})",
                    "bpp": w_bpp,
                    "pbn": w_pbn,
                    # Pusta wartość mówi coś konkretnego — piszemy to słowami.
                    "brak_bpp": "brak dyscypliny w rekordzie BPP",
                    "brak_pbn": "brak oświadczenia w PBN"
                    if oswiadczenie is None
                    else "oświadczenie w PBN bez dyscypliny",
                }
            )
    return roznice
