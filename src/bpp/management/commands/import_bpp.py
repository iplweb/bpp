# -*- encoding: utf-8 -*-
"""Importuje bazę danych BPP z istniejącego serwera PostgreSQL"""

import os
import sys
import lxml.html
import traceback
from collections import defaultdict
from pathlib import Path
from time import time

import psycopg2.extensions
from django.db import IntegrityError

from bpp.models.abstract import (
    ILOSC_ZNAKOW_NA_ARKUSZ,
    parse_informacje,
    wez_zakres_stron,
)
from bpp.models.cache import Rekord
from bpp.models.konferencja import Konferencja
from bpp.models.seria_wydawnicza import Seria_Wydawnicza
from bpp.models.struktura import Uczelnia
from bpp.templatetags.prace import close_tags
from bpp.util import get_fixture, set_seq

psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)

import decimal
import json
from datetime import datetime

from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction, DatabaseError
from django.contrib.auth.models import Group
import psycopg2
from psycopg2 import extras

import bpp
from bpp.models.autor import Autor_Jednostka
from bpp.models.system import (
    Typ_KBN,
    Status_Korekty,
    Jezyk,
    Zrodlo_Informacji,
    Typ_Odpowiedzialnosci,
    Charakter_Formalny,
)
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor
from bpp.models.profile import BppUser as User
from bpp.models import (
    Jednostka,
    Wydzial,
    Rodzaj_Zrodla,
    Zrodlo,
    Tytul,
    Autor,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Patent,
    Patent_Autor,
)

from django.db.models import Model
from django.conf import settings

settings.DEBUG = False


# Put this on your base model (or monkey patch it onto django's Model if that's your thing)
def reload(self):
    new_self = self.__class__.objects.get(pk=self.pk)
    # You may want to clear out the old dict first or perform a selective merge
    self.__dict__.update(new_self.__dict__)


Model.reload = reload

_user_cache = None


def find_user(login):
    if login is None or login == "":
        return None

    global _user_cache

    if _user_cache is None:
        _user_cache = dict([(x.pk, x) for x in User.objects.all()])

    return _user_cache[login]


def convert_www(s):
    if s is None:
        return

    if not s:
        return

    s = s.strip()

    if not s:
        return

    if s.lower().startswith("http://"):
        return s

    return "http://" + s


def punktacja(dct, kw):
    kw.update(
        dict(
            # ModelPunktowany
            impact_factor=dct["impact"] or 0.00,
            punkty_kbn=dct["pk"] or 0.00,
            index_copernicus=dct["ind_cop"] or 0.00,
            punktacja_wewnetrzna=dct["pkt_wewn"] or 0.00,
            weryfikacja_punktacji=dct["weryfikacja_punktacji"],
            kc_impact_factor=dct["kc_impact"],
            kc_punkty_kbn=dct["kc_pk"],
            kc_index_copernicus=dct["kc_ind_cop"],
        )
    )


def afiliacja(dct, kw):
    kw.update(
        dict(
            # ModelAfiliowanyRecenzowany
            recenzowana=dct["recenzowana"]
        )
    )

    for field in ["recenzowana"]:
        if kw[field] == None:
            # print "Ustawiam %s=False dla pracy z ID: %s " % (field, dct['id'])
            kw[field] = False


def szczegoly_i_inne(dct, kw, zrodlowe_pole_dla_informacji):
    d = dict(
        pk=dct["id"],
        # ModelZeSzczegolami
        # informacje=
        szczegoly=dct["szczegoly"],
        uwagi=dct["uwagi"],
        slowa_kluczowe=dct["slowa_kluczowe"],
        tom=dct["tom"],
        # ModelZRokiem
        rok=dct["rok_publikacji"],
        # ModelZWWW
        www=convert_www(dct["www_old"]),
    )

    if zrodlowe_pole_dla_informacji is not None:
        d["informacje"] = dct[zrodlowe_pole_dla_informacji] or ""
        d["informacje"] = d["informacje"].strip()

    if "informacje" in d:
        if d["informacje"]:
            if not d["tom"]:
                d["tom"] = parse_informacje(d["informacje"], "tom")

    if d["szczegoly"]:
        d["strony"] = wez_zakres_stron(d["szczegoly"])

    kw.update(d)


def idx(klass, attr="pk"):
    "Pobiera wszystkie modele klasy 'klass' do słownika wg. indeksu atrybuty 'attr'"
    return dict([(getattr(x, attr), x) for x in klass.objects.all()])


class Cache:
    def __init__(self):
        pass

    def initialize(self):
        self.typy_kbn = idx(Typ_KBN)
        self.jezyki = idx(Jezyk)
        self.statusy_korekty = idx(Status_Korekty)
        self.informacje_z = idx(Zrodlo_Informacji, "nazwa")
        self.typy_odpowiedzialnosci = idx(Typ_Odpowiedzialnosci)
        self.charaktery = idx(Charakter_Formalny, "skrot")
        self.jednostki = idx(Jednostka)
        self.zrodla = idx(Zrodlo)
        try:
            self.obca_jednostka = Jednostka.objects.get(nazwa="Obca Jednostka")
        except Jednostka.DoesNotExist:
            pass


cache = Cache()

NOWE_CHARAKTERY_MAPPING = {
    "AP": "AC",
    "API": "AC",
    "AZ": "AC",
    "PRI": "PRZ",
    "PSI": "PSZ",
    "S": None,
    "PW": None,
    "DOK": "D",
    "HAB": "H",
    "PODR": "PA",
    "PSUM": "PSZ",
    "ZSUM": None,
    "BPEX": None,
}


def nowy_charakter_formalny(skrot):
    """Przemapuj 'stary' charakter formalny na nowy charakter formalny,
    wg. zmian ustalonych w listopadzie 2014 r.
    """
    try:
        # !!!! WYŁĄCZONE !!!!
        # return cache.charaktery[NOWE_CHARAKTERY_MAPPING.get(skrot, skrot)]
        return cache.charaktery[skrot]
    except KeyError as e:
        print("KEY ERROR DLA SKROTU %r" % skrot)
        raise e


def jezyki_statusy(dct, kw):
    kw.update(
        dict(
            # ModelTypowany
            jezyk=cache.jezyki[dct["jezyk"]],
            typ_kbn=cache.typy_kbn.get(dct["kbn"], cache.typy_kbn[12]),
            # ModelZeStatusem
            status_korekty=cache.statusy_korekty[int(dct["status"])],
            # ModelZInformacjaZ
            informacja_z=cache.informacje_z.get(dct["info_src"], None),
        )
    )


def dwa_tytuly(dct, kw):
    kw.update(
        dict(
            # ModelZTytulem
            tytul_oryginalny=close_tags(dct["tytul_or"]),
            tytul=close_tags(dct["title"]),
        )
    )


def doi(dct, kw):
    kw.update(dict(doi=dct["doi"]))


def poprzestawiaj_wartosci_pol(kw, bib, zakazane, docelowe):
    for field in zakazane:
        if bib[field]:
            op = lambda x, y: (x + " " + y).strip()
            _docelowe = docelowe
            if field == "new_zrodlo":
                try:
                    # Dla habilitacji, tytuł źródła do pola "Informacje"
                    bib["new_zrodlo"] = cache.zrodla[bib["new_zrodlo"]].nazwa
                    _docelowe = "new_zrodlo_src"  # informacje"
                    op = lambda x, y: (y + " " + x).strip()
                except IndexError:
                    bib["new_zrodlo"] = (
                        "Zrodlo o id %s nie znalezione" % bib["new_zrodlo"]
                    )

            if hasattr(bib[field], "strip"):
                bib[field] = bib[field].strip()

            skrot = charakter.get(bib["charakter"])["skrot"].strip()

            msg = [
                "REKORD: \t",
                str(bib["id"]),
                "\tchar: ",
                str(bib["charakter"]),
                "\t",
                skrot,
                "\tZAWIERA WARTOSC DLA POLA \t",
                field,
                "PRZENOSZE DO POLA '",
                _docelowe,
                "' (wartosc: ",
                str(bib[field]),
                ")",
            ]

            print("%r" % " ".join(msg))

            if kw.get("legacy_data") is None:
                kw["legacy_data"] = {}

            kw["legacy_data"] = {field: bib[field]}

            if bib[_docelowe] is None:
                bib[_docelowe] = ""

            if type(bib[field]) == int:
                bib[field] = str(bib[field])

            bib[_docelowe] = op(bib[_docelowe], bib[field])
            bib[field] = ""


def skoryguj_wartosci_pol(bib):
    if bib["new_zrodlo"] == 0:
        bib["new_zrodlo"] = -1


_wez_autorow_cache = None


def wez_autorow(pk, pgsql_conn):
    global _wez_autorow_cache

    if _wez_autorow_cache is None:
        _wez_autorow_cache = defaultdict(lambda: [])

        print("Cache fetch")
        cur2 = pgsql_conn.cursor(cursor_factory=extras.DictCursor)
        cur2.execute(
            """
            SELECT 
              idt,
              id, 
              idt_aut, 
              idt_jed, 
              lp, 
              naz_zapis, 
              typ_autora,
              afiliuje,
              zatrudniony
            FROM 
              b_a
              """
        )
        #    """)
        # WHERE
        #   idt = %s
        #   """ % pk)
        while True:
            elem = cur2.fetchone()
            if elem is None:
                break
            _wez_autorow_cache[elem["idt"]].append(elem)
        cur2.close()
        print("Fetch done")

    return _wez_autorow_cache[pk]


def zrob_autorow_dla(wc, klass, pgsql_conn):
    for row in wez_autorow(wc.pk, pgsql_conn):
        if row["idt_jed"] == 0:
            row["idt_jed"] = -1

        # autor = Autor.objects.get(pk=row['idt_aut'])

        if row["typ_autora"] == 0 or row["typ_autora"] is None:
            print("REKORD", row["id"], "TYP AUTORA == 0 lub None USTAWIAM NA 1")
            row["typ_autora"] = 1

        typ = cache.typy_odpowiedzialnosci[row["typ_autora"]]
        jednostka = cache.jednostki[row["idt_jed"]]
        zatrudniony = row["zatrudniony"] or False
        afiliuje = row["afiliuje"] or False

        try:
            klass.objects.create(
                rekord=wc,
                autor_id=row["idt_aut"],
                jednostka=jednostka,
                kolejnosc=row["lp"],
                zapisany_jako=row["naz_zapis"],
                typ_odpowiedzialnosci=typ,
                afiliuje=afiliuje,
                zatrudniony=zatrudniony,
            )
        except IntegrityError as e:
            print("ERROR dla pracy %r, row=%r" % (wc, row))
            raise e


def zrob_wydzialy(cur):
    cur.execute(
        """
    SELECT id, skrot, nazwa, opis, skr_nazwy, id_polon, sort
    FROM wyd"""
    )

    while True:
        l = cur.fetchone()
        if l is None:
            break
        Wydzial.objects.create(
            pk=l["id"],
            uczelnia_id=Uczelnia.objects.all().first().pk,
            nazwa=l["nazwa"],
            skrot=l["skrot"],
            skrot_nazwy=l["skr_nazwy"],
            poprzednie_nazwy=l["opis"],
            pbn_id=l["id_polon"],
            kolejnosc=l["sort"],
        )


def zrob_userow(cur):
    cur.execute(
        """SELECT login, haslo, nazwisko_i_imie, e_mail, 
      COALESCE(adnotacje, '') as adnotacje,
            uprawnienia, id, created_on, last_access, created_by, edited_by
            FROM users ORDER BY id"""
    )
    later = []
    while True:
        l = cur.fetchone()
        if l is None:
            break

        print(l["nazwisko_i_imie"])
        try:
            imie, nazwisko = l["nazwisko_i_imie"].split(" ", 1)
        except ValueError:
            nazwisko = l["nazwisko_i_imie"]
            imie = ""

        uprawnienia = l["uprawnienia"].split(":")

        u = User.objects.create(
            pk=l["id"],
            username=l["login"],
            is_staff=True,
            first_name=imie,
            last_name=nazwisko,
            email=l["e_mail"] or "brak@email.pl",
        )
        u.set_password(l["haslo"])
        u.save()

        for letter, name in list(
            dict(
                S="dane systemowe",
                E="wprowadzanie danych",
                B="przeglądanie",
                I="indeks autorów",
                A="administracja",
            ).items()
        ):
            if letter in uprawnienia:
                if letter == "B":
                    # Ignorujemy grupę "przeglądanie" totalnie
                    continue
                u.groups.add(Group.objects.get(name=name))
                # dołóż wszystkim którzy mogą wprowadzać
                # dane opcje edycji struktury uczelni:
                if letter == "E":
                    u.groups.add(Group.objects.get(name="struktura"))
                # administratorzy i mogący edytować dane systemowe dostają
                # grupę "web"
                if letter in ["S", "A"]:
                    u.groups.add(Group.objects.get(name="web"))
                    u.groups.add(Group.objects.get(name="raporty"))

        u.utworzony = l["created_on"]
        if l["created_by"] is not None:
            try:
                u.utworzony_przez = User.objects.get(pk=l["created_by"])
            except User.DoesNotExist:
                later.append((u.pk, "utworzony_przez", l["created_by"]))
                pass

        u.zmieniony = l["last_access"]
        if l["edited_by"] is not None:
            try:
                u.zmieniony_przez = User.objects.get(pk=l["edited_by"])
            except User.DoesNotExist:
                later.append((u.pk, "zmieniony_przez", l["edited_by"]))

        u.adnotacje = l["adnotacje"] or ""
        u.save()

    for pk, attribute, value in later:
        u = User.objects.get(pk=pk)
        setattr(u, attribute, User.objects.get(pk=value))
        u.save()


def utworzono(model, bib):
    model.utworzono = bib["created_on"]
    model.save()


def admin_log_history(obj, dct):
    user = find_user(dct["created_by"])
    if user is not None:
        # obj.reload()
        kw = dict(
            user_id=user.pk,
            content_type_id=ContentType.objects.get_for_model(obj).pk,
            object_id=obj.pk,
            object_repr=str(obj),
            change_message="Import z poprzedniej wersji bazy danych",
            action_flag=ADDITION,
        )
        try:
            LogEntry.objects.log_action(**kw)
        except DatabaseError as e:
            print(e)
            print(kw)
            raise e

    user = find_user(dct["edited_by"])
    if user is not None:
        # obj.reload()
        LogEntry.objects.log_action(
            user_id=user.pk,
            content_type_id=ContentType.objects.get_for_model(obj).pk,
            object_id=obj.pk,
            object_repr=str(obj),
            change_message="Ostatnia edycja w poprzedniej wersji bazy danych",
            action_flag=CHANGE,
        )
    utworzono(obj, dct)


def zrob_jednostki(cur, initial_offset, skip):
    cur.execute(
        """SELECT id, skrot, nazwa, wyd, to_print, email, www,
            created_on, last_access, created_by, edited_by, opis
            FROM jed OFFSET %s"""
        % initial_offset
    )

    while True:
        jed = cur.fetchone()
        if jed is None:
            break

        wyd = Wydzial.objects.get(pk=jed["wyd"])

        # Jest to konieczne, bo coś potem autocomplete się psuje... i podobnie
        # dla innych ID w bazie
        if jed["id"] == 0:
            jed["id"] = -1

        kw = dict(
            pk=jed["id"],
            nazwa=jed["nazwa"],
            skrot=jed["skrot"],
            wydzial=wyd,
            widoczna=jed["to_print"] == "*",
            email=jed["email"],
            www=convert_www(jed["www"]),
            adnotacje=jed["opis"] or "",
        )
        j = Jednostka.objects.create(**kw)
        admin_log_history(j, jed)

        for _skip in range(skip):
            cur.fetchone()


def zrob_zrodla(cur, initial_offset, skip):
    cur.execute(
        """SELECT 
              rodzaj, 
              skrot, 
              www, 
              nazwa, 
              adnotacje,
              id, 
              created_on, last_access, created_by, edited_by, 
              issn, 
              e_issn, 
              issn2, 
              doi,
              wydawca,
              wlasciwy
            FROM zrodla OFFSET %s"""
        % initial_offset
    )

    while True:
        zrod = cur.fetchone()
        if zrod is None:
            break

        if zrod["id"] == 0:
            # źródło nieindeksowane
            continue

        try:
            rodzaj = Rodzaj_Zrodla.objects.get(pk=zrod["rodzaj"])
        except Rodzaj_Zrodla.DoesNotExist as e:
            print("Brak rodzaju zrodla: %s" % zrod["rodzaj"])
            raise e

        issn = (zrod["issn"] or "").strip()
        issn2 = (zrod["issn2"] or "").strip()
        issn = issn or issn2

        kw = dict(
            pk=zrod["id"],
            rodzaj=rodzaj,
            skrot=zrod["skrot"],
            www=zrod["www"],
            nazwa=zrod["nazwa"],
            adnotacje=zrod["adnotacje"] or "",
            issn=issn,
            e_issn=zrod["e_issn"],
            doi=zrod["doi"],
            wydawca=zrod["wydawca"] or "",
            nazwa_alternatywna=zrod["wlasciwy"],
        )

        z = Zrodlo.objects.create(**kw)
        admin_log_history(z, zrod)

        for _skip in range(skip):
            cur.fetchone()


@transaction.atomic
def zrob_autorow(cur, initial_offset=0, skip=0):
    tytuly = dict([(x.skrot, x) for x in Tytul.objects.all()])

    cur.execute(
        """SELECT id, imiona, nazwisko, idt_jed, email, www, tytul,
            stanowisko, urodzony, zmarl, created_on, created_by, last_access,
            edited_by, adnotacje, haslo, hide_on_unit, dawne_nazwisko
            FROM aut ORDER BY nazwisko, imiona OFFSET %s"""
        % initial_offset
    )

    while True:
        aut = cur.fetchone()
        if aut is None:
            break

        aut["tytul"] = (aut["tytul"] or "").strip()

        tytul = None
        if aut["tytul"]:
            try:
                tytul = tytuly[aut["tytul"]]
            except KeyError:
                tytul = Tytul.objects.create(nazwa=aut["tytul"], skrot=aut["tytul"])
                print("UTWORZYLEM TYTUL", tytul)

        imiona = aut["imiona"]
        if imiona is None:
            imiona = ""

        kw = dict(
            pk=aut["id"],
            imiona=imiona,
            nazwisko=aut["nazwisko"].strip(),
            tytul=tytul,
            email=aut["email"],
            adnotacje=aut["adnotacje"] or "",
            www=convert_www(aut["www"]),
            urodzony=aut["urodzony"],
            zmarl=aut["zmarl"],
            pokazuj=int(aut["hide_on_unit"]) == 0,
            poprzednie_nazwiska=aut["dawne_nazwisko"],
        )

        a = Autor.objects.create(**kw)
        admin_log_history(a, aut)

        for _skip in range(skip):
            cur.fetchone()


def zrob_powiazania(cur, initial_offset, skip):
    # W "starym" systemie istnieje powiązanie autora do jednostki na obiekcie
    # autora. W "nowym" jest wiele miejsc pracy i tak dalej. ALE potrzebujemy
    # aktualnego przypisania autora do jednostki. ZATEM: bierzemy to przypisanie
    # ze "starego" i w dniu importu danych nadajemy mu pozory aktualności,
    # nadając datę POCZATEK PRACY W DANYM MIEJSCU dla tego miejsca.

    # Powiązania autor-jednostka
    cur.execute(
        """SELECT DISTINCT
                b_a.idt_aut,
                b_a.idt_jed,
                aut.idt_jed AS current_idt_jed
            FROM
                b_a,
                aut
            WHERE
                aut.id = idt_aut
                AND b_a.zatrudniony = 't'
            OFFSET %s"""
        % initial_offset
    )

    while True:
        b_a = cur.fetchone()
        if b_a is None:
            break

        if b_a["idt_jed"] == 0:
            b_a["idt_jed"] = -1

        try:
            jednostka = Jednostka.objects.get(pk=b_a["idt_jed"])
        except:
            raise Exception("BRAK JEDNOSTKI O ID: ", b_a["idt_jed"])

        try:
            autor = Autor.objects.get(pk=b_a["idt_aut"])
        except:
            raise Exception("BRAK AUTORA O ID: ", b_a["idt_aut"])

        rozpoczal_prace = None
        if b_a["current_idt_jed"] == b_a["idt_jed"]:
            rozpoczal_prace = datetime.now().date()

        Autor_Jednostka.objects.create(
            autor=autor,
            jednostka=jednostka,
            rozpoczal_prace=rozpoczal_prace,
            zakonczyl_prace=None,
            funkcja=None,
        )

        for _skip in range(skip):
            cur.fetchone()


def openaccess(bib, kw):
    kw.update(
        dict(
            openaccess_czas_publikacji_id=bib["oa_data"],
            openaccess_licencja_id=bib["oa_licencja"],
            openaccess_tryb_dostepu_id=bib["oa_sposob"],
            openaccess_wersja_tekstu_id=bib["oa_wersja"],
            public_www=bib["oa_link"],
        )
    )


def zrob_import_z_tabeli(kw, bib, zakazane, docelowe, zrodlowe_pole_dla_informacji):
    # Tych pól wydawnictwo ma nie mieć
    poprzestawiaj_wartosci_pol(kw, bib, zakazane, docelowe)
    skoryguj_wartosci_pol(bib)

    punktacja(bib, kw)
    afiliacja(bib, kw)
    dwa_tytuly(bib, kw)
    szczegoly_i_inne(bib, kw, zrodlowe_pole_dla_informacji)
    jezyki_statusy(bib, kw)

    for pole in ["nrbibl", "typ_polon", "cechy_polon", "afiliowana"]:
        if bib[pole]:
            if "legacy_data" not in kw:
                kw["legacy_data"] = {}

            kw["legacy_data"][pole] = bib[pole]

    kw["pbn_id"] = bib["id"]


def zrob_wydawnictwo(
    kw,
    bib,
    klass,
    autor_klass,
    zakazane,
    docelowe,
    pgsql_conn,
    zrodlowe_pole_dla_informacji,
    usun_przed=None,
):
    zrob_import_z_tabeli(kw, bib, zakazane, docelowe, zrodlowe_pole_dla_informacji)
    if usun_przed:
        for field in usun_przed:
            del kw[field]

    if bib["konf_nazwa"]:
        kw["konferencja"] = Konferencja.objects.get(nazwa=bib["konf_nazwa"].strip())

    try:
        wc = klass.objects.create(**kw)
    except decimal.InvalidOperation as e:
        print(kw)
        raise e
    admin_log_history(wc, bib)
    zrob_autorow_dla(wc, autor_klass, pgsql_conn)
    return wc


@transaction.atomic
def zrob_wydawnictwo_ciagle(bib, skrot, pgsql_conn):
    kw = dict(
        # Wydawnictwo_Ciagle
        zrodlo_id=bib["new_zrodlo"],
        charakter_formalny=nowy_charakter_formalny(skrot),
        nr_zeszytu=bib["nr_zeszytu"],
    )

    bib["nr_zeszytu"] = None

    doi(bib, kw)
    openaccess(bib, kw)

    w = zrob_wydawnictwo(
        kw,
        bib,
        Wydawnictwo_Ciagle,
        Wydawnictwo_Ciagle_Autor,
        zakazane=["redakcja", "mceirok", "wydawnictwo", "isbn", "nr_zeszytu"],
        docelowe="uwagi",
        pgsql_conn=pgsql_conn,
        zrodlowe_pole_dla_informacji="new_zrodlo_src",
    )

    if not w.nr_zeszytu and w.informacje:
        _old = w.nr_zeszytu
        w.nr_zeszytu = parse_informacje(w.informacje, "numer")
        if w.nr_zeszytu != _old:
            w.save()

    zrob_znaki_wydawnicze(bib, w)

    # admin_log_history(w, bib)


def zrob_baze_wydawnictwa_zwartego(bib):
    kw = dict(
        miejsce_i_rok=bib["mceirok"],
        wydawnictwo=bib["wydawnictwo"],
        redakcja=bib["redakcja"],
        isbn=bib["isbn"],
        informacje=bib["new_zrodlo_src"],
    )

    return kw


def zrob_znaki_wydawnicze(bib, wc):
    modified = False
    if bib["ilosc_znakow_wydawnicznych"] is not None:
        wc.liczba_znakow_wydawniczych = bib["ilosc_znakow_wydawnicznych"]
        modified = True

    if bib["ilosc_arkuszy_wydawniczych"] is not None:
        wc.liczba_znakow_wydawniczych = (
            bib["ilosc_arkuszy_wydawniczych"] * ILOSC_ZNAKOW_NA_ARKUSZ
        )
        modified = True

    if modified:
        wc.save()


@transaction.atomic
def zrob_wydawnictwo_zwarte(bib, skrot, pgsql_conn):
    kw = zrob_baze_wydawnictwa_zwartego(bib)
    kw["charakter_formalny"] = nowy_charakter_formalny(skrot)
    bib["new_zrodlo_src"] = None
    doi(bib, kw)
    openaccess(bib, kw)

    wc = zrob_wydawnictwo(
        kw,
        bib,
        Wydawnictwo_Zwarte,
        Wydawnictwo_Zwarte_Autor,
        zakazane=["new_zrodlo", "new_zrodlo_src", "nr_zeszytu"],
        docelowe="uwagi",
        pgsql_conn=pgsql_conn,
        zrodlowe_pole_dla_informacji=None,
    )

    if bib["seria"]:
        wc.seria_wydawnicza = Seria_Wydawnicza.objects.get(nazwa=bib["seria"])

    zrob_znaki_wydawnicze(bib, wc)


@transaction.atomic
def zrob_doktorat_lub_habilitacje(bib, pgsql_conn):
    kw = zrob_baze_wydawnictwa_zwartego(bib)

    zrob_import_z_tabeli(
        kw,
        bib,
        zakazane=["new_zrodlo", "nr_zeszytu"],
        docelowe="uwagi",
        zrodlowe_pole_dla_informacji="new_zrodlo_src",
    )

    autor = wez_autorow(bib["id"], pgsql_conn)
    if len(autor) != 1:
        print(
            (
                "dla pracy doktorskiej/habilitacyjnej z id %s ilosc autorow jest rowna %s, IGNORUJE TEN WPIS"
                % (bib["id"], len(autor))
            )
        )
        return

    kw["autor"] = Autor.objects.get(pk=autor[0]["idt_aut"])
    kw["jednostka"] = Jednostka.objects.get(pk=autor[0]["idt_jed"])

    # 20140714 brak doktoratów w UP
    # if bib['charakter'] == 21:  # praca doktorska
    #    klass = Praca_Doktorska
    # el
    if bib["charakter"] == 5:  # praca habilitacyjna
        klass = Praca_Habilitacyjna
    else:
        raise Exception(
            "Probuje zaimportowac doktorat lub habilitacje, a charakter to %s"
            % bib["charakter"]
        )

    try:
        r = klass.objects.create(**kw)
    except decimal.InvalidOperation as e:
        print(kw)
        raise e

    admin_log_history(r, bib)


def zrob_jezyki(cursor):
    Jezyk.objects.all().delete()
    cursor.execute("SELECT id, trim(skrot) as skrot, nazwa FROM jez")
    for elem in cursor.fetchall():
        kw = {}
        if elem["skrot"] == "POL":
            elem["skrot"] = "pol."
            kw["skrot_dla_pbn"] = "PL"
        if elem["skrot"] == "ENG":
            kw["skrot_dla_pbn"] = "EN"
        Jezyk.objects.create(
            pk=elem["id"],
            nazwa=elem["nazwa"].strip(),
            skrot=elem["skrot"].strip(),
            **kw
        )
    set_seq("bpp_jezyk")


def zrob_kbn(cursor):
    artykuly_pbn = ["cr", "pak", "mon", "po", "pp", "pnp", "rc"]
    Typ_KBN.objects.all().delete()
    cursor.execute("SELECT id, skrot, nazwa FROM kbn")
    for elem in cursor.fetchall():
        skrot = elem["skrot"].strip()
        if skrot == "MON":
            skrot = "mon"
        Typ_KBN.objects.create(
            pk=elem["id"],
            nazwa=elem["nazwa"].strip(),
            skrot=skrot,
            artykul_pbn=elem["skrot"].strip().lower() in artykuly_pbn,
        )
    set_seq("bpp_typ_kbn")


def zrob_typy_odpowiedzialnosci(cursor):
    Typ_Odpowiedzialnosci.objects.all().delete()
    cursor.execute("SELECT id, skrot2, nazwa FROM typy_autorow")
    for elem in cursor.fetchall():
        Typ_Odpowiedzialnosci.objects.create(
            pk=elem["id"],
            nazwa=elem["nazwa"],
            skrot=elem["skrot2"].replace("[", "").replace("]", "").lower(),
        )


def zrob_charaktery_formalne(cursor):
    Charakter_Formalny.objects.all().delete()
    cursor.execute("SELECT id, skrot, nazwa FROM pub")

    f = get_fixture("charakter_formalny")
    artykul_pbn = ["ac", "supl", "l", "ap", "az", "api"]
    ksiazka_pbn = ["ks", "ksz", "ksp", "skr", "pa"]
    rozdzial_pbn = ["frg", "roz", "rozs", "pa", "rozp"]

    for elem in cursor.fetchall():
        kw = {"nazwa": elem["nazwa"]}

        skrot_l = elem["skrot"].lower().strip()
        extra = f.get(skrot_l)
        if extra:
            del extra["skrot"]
            kw.update(extra)
        else:
            print(
                "Dla charakteru formalnego %s nie ma ekstra-informacji"
                % (elem["skrot"] + elem["nazwa"])
            )

        Charakter_Formalny.objects.create(
            pk=elem["id"],
            skrot=elem["skrot"].strip(),
            artykul_pbn=skrot_l in artykul_pbn,
            ksiazka_pbn=skrot_l in ksiazka_pbn,
            rozdzial_pbn=skrot_l in rozdzial_pbn,
            **kw
        )
    set_seq("bpp_charakter_formalny")
    Charakter_Formalny.objects.create(
        skrot="ROZS",
        nazwa="Rozdział skryptu",
        nazwa_w_primo="Rozdział",
        rozdzial_pbn=True,
    )


@transaction.atomic
def zrob_indeksy(cursor):
    zrob_jezyki(cursor=cursor)
    zrob_kbn(cursor)
    zrob_charaktery_formalne(cursor)
    zrob_typy_odpowiedzialnosci(cursor)


# @transaction.atomic
def zrob_patent(bib, pgsql_conn):
    kw = zrob_baze_wydawnictwa_zwartego(bib)
    p = zrob_wydawnictwo(
        kw,
        bib,
        Patent,
        Patent_Autor,
        zakazane=["new_zrodlo", "new_zrodlo_src", "konf_nazwa"],
        docelowe="uwagi",
        pgsql_conn=pgsql_conn,
        zrodlowe_pole_dla_informacji=None,
        usun_przed=[
            "tytul",
            "isbn",
            "wydawnictwo",
            "redakcja",
            "typ_kbn",
            "jezyk",
            "miejsce_i_rok",
        ],
    )

    # admin_log_history(p, bib)


charakter = {}


def zrob_publikacje(cur, pgsql_conn, initial_offset, skip):
    global charakter

    cur.execute("SELECT * FROM pub")
    charakter = dict([(x["id"], x) for x in cur.fetchall()])

    cur.execute(
        """SELECT 
          id, 
          tytul_or, 
          title, 
          zrodlo, 
          szczegoly, 
          uwagi,
          charakter, 
          impact, 
          redakcja, 
          status, 
          rok, 
          rok_publikacji, 
          edited_by,
          kbn, 
          afiliowana, 
          recenzowana, 
          jezyk, 
          pk, 
          created_on, 
          last_access,
          created_by, 
          edited_by, 
          new_zrodlo, 
          new_zrodlo_src, 
          mceirok,
          wydawnictwo, 
          slowa_kluczowe, 
          www_old, 
          ind_cop, 
          pkt_wewn,
          auto_pk, 
          isbn, 
          nr_zeszytu, 
          NULL AS info_src, 
          impact AS kc_impact, 
          pk AS kc_pk, 
          ind_cop AS kc_ind_cop,
          false AS weryfikacja_punktacji, 
          NULL AS ilosc_znakow_wydawnicznych,
          arkusze AS ilosc_arkuszy_wydawniczych,
          
          doi,
          
          oa_sposob,
          oa_licencja,
          oa_wersja, 
          oa_data,
          oa_link,
          
          tom,
          
          nrbibl,
          seria,
          
          typ_polon,
          cechy_polon,
          
          konf_nazwa
          
      FROM 
        bib 
        
      WHERE
        charakter IS NOT NULL
        
      ORDER BY id OFFSET %s"""
        % initial_offset
    )

    # Charakter 5 => praca habilitacyjna
    # Charakter 16 => patent

    # start_time = None
    cnt = 0
    while True:
        # if start_time is None:
        #     start_time = time()
        bib = cur.fetchone()
        if bib is None:
            break

        try:
            skrot = charakter.get(bib["charakter"])["skrot"].strip()
            if skrot == "T\xc5\x81":
                skrot = "TŁ"

            # if skrot == 'D' or skrot == 'H':
            #     # doktorat lub habilitacja
            #     zrob_doktorat_lub_habilitacje(bib, pgsql_conn)

            if skrot == "PAT":
                zrob_patent(bib, pgsql_conn)

            else:
                if bib["new_zrodlo"] and skrot not in ["D", "H"]:
                    zrob_wydawnictwo_ciagle(bib, skrot, pgsql_conn)
                else:
                    zrob_wydawnictwo_zwarte(bib, skrot, pgsql_conn)

        except:
            print("*** BLAD REKORD: %i" % bib["id"])
            traceback.print_exc(file=sys.stdout)

        # cnt += 1
        # if cnt % 100 == 0:
        #     print("%.2f recs/sec" % (cnt/(time()-start_time)))
        for _skip in range(skip):
            cur.fetchone()


class ColumnNotIndexed(Exception):
    def __init__(self, table, col, *args, **kw):
        super(ColumnNotIndexed, self).__init__(*args, **kw)
        self.table = table
        self.col = col

    def __str__(self):
        return (
            "No index. Create one with CREATE INDEX %(table)s_%(col)s_idx ON %(table)s(%(col)s)"
            % dict(table=self.table, col=self.col)
        )


def make_clusters():
    """Za pomocą CLUSTER układa tabele wg najczęściej stosowanych
    (czyli defaultowych) indeksów.
    """

    from django.db import connection

    django_cur = connection.cursor()

    def idx_name(table, col):
        django_cur.execute("SELECT pg_find_index('%s', '%s')" % (table, col))
        try:
            return django_cur.fetchall()[0][0]
        except IndexError:
            raise ColumnNotIndexed(table, col)

    def cluster(table, by):
        idx = idx_name(table, by)
        django_cur.execute("CLUSTER %s USING %s" % (table, idx))

    cluster("bpp_autor", "nazwisko")
    cluster("bpp_zrodlo", "nazwa")
    cluster("bpp_jednostka", "nazwa")
    for table in [
        "bpp_wydawnictwo_ciagle",
        "bpp_patent",
        "bpp_wydawnictwo_zwarte",
        "bpp_praca_doktorska",
        "bpp_praca_habilitacyjna",
    ]:
        cluster(table, "tytul_oryginalny")
    cluster("bpp_rekord_mat", "rok")


def zrob_rodzaje_zrodel(cur):
    Rodzaj_Zrodla.objects.all().delete()
    cur.execute("SELECT id, nazwa FROM zrodla_rodzaje")
    for elem in cur.fetchall():
        Rodzaj_Zrodla.objects.create(pk=elem["id"], nazwa=elem["nazwa"])


def zrob_konferencje(cur):
    Konferencja.objects.all().delete()
    cur.execute(
        """
        SELECT DISTINCT 
          konf_nazwa, 
          konf_nazwa2, 
          konf_od, 
          konf_do, 
          konf_miasto, 
          konf_panstwo, 
          bazy_scopus, 
          bazy_wos, 
          bazy_inna
        FROM bib
        WHERE COALESCE(konf_nazwa, '')!=''
        ORDER BY konf_nazwa, konf_od DESC
                """
    )
    for elem in cur.fetchall():
        Konferencja.objects.get_or_create(
            nazwa=elem["konf_nazwa"].strip(),
            defaults=dict(
                rozpoczecie=elem["konf_od"],
                skrocona_nazwa=elem["konf_nazwa2"],
                zakonczenie=elem["konf_do"],
                miasto=elem["konf_miasto"],
                panstwo=elem["konf_panstwo"],
                baza_scopus=elem["bazy_scopus"] or False,
                baza_wos=elem["bazy_wos"] or False,
                baza_inna=elem["bazy_inna"],
            ),
        )


def db_connect():
    pgsql_conn = psycopg2.connect(
        database=os.getenv("BPP_DB_REBUILD_SOURCE_DB_NAME", "prace-ar"),
        user=os.getenv("BPP_DB_REBUILD_SOURCE_DB_USER", "bpp"),
        password=os.getenv("BPP_DB_REBUILD_SOURCE_DB_PASSWORD", ""),
        host=os.getenv("BPP_DB_REBUILD_SOURCE_DB_HOST", "localhost"),
        port=int(os.getenv("BPP_DB_REBUILD_SOURCE_DB_PORT", "5432")),
    )
    pgsql_conn.set_client_encoding("UTF8")
    return pgsql_conn


def db_disconnect(cur):
    cur.close()


class Command(BaseCommand):
    help = "Importuje baze danych BPP z istniejacego serwera PostgreSQL"

    def add_arguments(self, parser):
        parser.add_argument("--uzytkownicy", action="store_true")

        parser.add_argument("--uczelnia", action="store_true")
        parser.add_argument("--nazwa-uczelni", action="store", type=str)
        parser.add_argument("--nazwa-uczelni-skrot", action="store", type=str)
        parser.add_argument("--nazwa-uczelni-w-dopelniaczu", action="store", type=str)

        parser.add_argument("--wydzialy", action="store_true")
        parser.add_argument("--jednostki", action="store_true")
        parser.add_argument("--zrodla", action="store_true")
        parser.add_argument("--autorzy", action="store_true")
        parser.add_argument("--powiazania", action="store_true")
        parser.add_argument("--indeksy", action="store_true")
        parser.add_argument("--konferencje", action="store_true")

        parser.add_argument("--korekty", action="store_true")
        parser.add_argument("--serie", action="store_true")
        parser.add_argument("--publikacje", action="store_true")
        parser.add_argument("--clusters", action="store_true")
        parser.add_argument("--initial-offset", action="store", type=int, default=0)
        parser.add_argument("--skip", action="store", type=int, default=0)

    def handle(self, *args, **options):
        """
        Podajemy temu poleceniu
        argumenty np. --uzytkownicy, --jednostki, --autorzy, --zrodla,
        --korekty, --publikacje, --sekwencje, do tego podajemy parametr
        --skip=N (co ile rekordów przeskakiwać) oraz --initial-offset=M
        (ile rekordów przeskoczyć inicjalnie) i to polecenie zacznie
        importować konkretne rekordy do bazy danych, przeskakując co
        N-ty rekord.
        """

        print("Initial cache fill")
        cache.initialize()
        print("Cache fill done")
        pgsql_conn = db_connect()
        cur = pgsql_conn.cursor(cursor_factory=extras.DictCursor)

        if options["uzytkownicy"]:
            zrob_userow(cur)  # , options['initial_offset'], options['skip'])
            set_seq("bpp_bppuser")

        if options["uczelnia"]:
            Uczelnia.objects.create(
                nazwa=options["nazwa_uczelni"],
                nazwa_dopelniacz_field=options["nazwa_uczelni_w_dopelniaczu"],
                skrot=options["nazwa_uczelni_skrot"],
            )
            set_seq("bpp_uczelnia")

        if options["wydzialy"]:
            zrob_wydzialy(cur)  # , options['initial_offset'], options['skip'])
            set_seq("bpp_wydzial")

        if options["jednostki"]:
            print("JEDNOSTKI", options["initial_offset"])
            zrob_jednostki(cur, options["initial_offset"], options["skip"])
            set_seq("bpp_jednostka")

        if options["autorzy"]:
            zrob_autorow(cur, options["initial_offset"], options["skip"])
            set_seq("bpp_autor")

        if options["powiazania"]:
            zrob_powiazania(cur, options["initial_offset"], options["skip"])

        if options["indeksy"]:
            zrob_indeksy(cur)

        if options["konferencje"]:
            zrob_konferencje(cur)

        if options["serie"]:
            cur.execute("SELECT DISTINCT seria FROM bib WHERE seria IS NOT NULL")
            for elem in cur.fetchall():
                Seria_Wydawnicza.objects.create(nazwa=elem["seria"])

        if options["zrodla"]:
            zrob_rodzaje_zrodel(cur)
            set_seq("bpp_rodzaj_zrodla")

            zrob_zrodla(cur, options["initial_offset"], options["skip"])
            set_seq("bpp_zrodlo")

        # Publikacje
        if options["publikacje"]:
            from bpp.models.cache import disable as cache_disable

            cache_disable()

            try:
                zrob_publikacje(
                    cur, pgsql_conn, options["initial_offset"], options["skip"]
                )
            finally:
                set_seq("bpp_wydawnictwo_ciagle")
                set_seq("bpp_wydawnictwo_zwarte")
                set_seq("bpp_patent")
                set_seq("bpp_praca_doktorska")
                set_seq("bpp_praca_habilitacyjna")

        if options["korekty"]:
            # Uzupełnij charaktery formalne i typy KBN o to, czego
            # tam jeszcze nie ma:

            for obj, fixture in [
                (Charakter_Formalny, "um_lublin_charakter_formalny"),
                (Typ_KBN, "um_lublin_typ_kbn"),
            ]:
                f = get_fixture(fixture)
                for elem in f.values():
                    if obj == Charakter_Formalny:
                        elem["charakter_pbn_id"] = elem["charakter_pbn"]
                        del elem["charakter_pbn"]

                    try:
                        c = obj.objects.get(skrot=elem["skrot"])
                    except obj.DoesNotExist:
                        obj.objects.create(**elem)
                        continue

                    for key, value in elem.items():
                        setattr(c, key, value)

                    c.save()

            for klass in Wydawnictwo_Zwarte, Wydawnictwo_Ciagle:
                for stary, nowy in NOWE_CHARAKTERY_MAPPING.items():

                    try:
                        stary = Charakter_Formalny.objects.get(skrot=stary)
                    except Charakter_Formalny.DoesNotExist:
                        continue

                    if nowy is not None:
                        nowy = Charakter_Formalny.objects.get(skrot=nowy)

                    stare = klass.objects.filter(charakter_formalny=stary).order_by(
                        "pk"
                    )

                    for obj in stare:
                        if nowy is None:
                            print("*** KASUJE", obj.pk, obj)
                            obj.delete()
                            continue

                        print(stary.skrot, nowy.skrot, obj.pk, obj)

                        if obj.legacy_data is None:
                            obj.legacy_data = {}
                        obj.legacy_data["charakter_formalny__skrot"] = stary.skrot
                        obj.charakter_formalny = nowy
                        obj.save()

            for skrot in [
                "AP",
                "AZ",
                "API",
                "PRI",
                "BPEX",
                "KOM",
                "CZ",
                "SKR",
                "PZ",
                "BR",
                "WYN",
            ]:
                c = Charakter_Formalny.objects.get(skrot=skrot)
                if Rekord.objects.filter(charakter_formalny=c).count():
                    print("*** NIE KASUJE %s, ma rekordy" % skrot)
                else:
                    c.delete()

        if options["clusters"]:
            make_clusters()

        for nazwa in ["Obca jednostka", "Studenci Uniwersytetu Medycznego w Lublinie"]:
            try:
                x = Jednostka.objects.get(nazwa=nazwa)
            except Jednostka.DoesNotExist:
                pass
            else:
                x.wchodzi_do_raportow = False
                x.save()

        for nazwa in [
            "Jednostki Dawne",
            "Bez Wydziału",
            "Poza Wydziałem",
            "Brak wpisanego wydziału",
            "Wydział Lekarski",
            "Jednostka międzywydziałowa",
        ]:
            try:
                x = Wydzial.objects.get(nazwa=nazwa)
            except Wydzial.DoesNotExist:
                pass
            else:
                x.zezwalaj_na_ranking_autorow = False
                x.save()

        db_disconnect(cur)
