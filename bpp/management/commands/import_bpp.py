# -*- encoding: utf-8 -*-
"""Importuje bazę danych BPP z istniejącego serwera PostgreSQL"""

import sys

from django.db import IntegrityError
import psycopg2.extensions


psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)

import decimal
from optparse import make_option
from datetime import datetime

from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction, DatabaseError
from django.contrib.auth.models import Group
import psycopg2
from psycopg2 import extras

from bpp.models.autor import Autor_Jednostka
from bpp.models.system import Typ_KBN, Status_Korekty, Jezyk, \
    Zrodlo_Informacji, Typ_Odpowiedzialnosci, Charakter_Formalny
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle, \
    Wydawnictwo_Ciagle_Autor
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte, \
    Wydawnictwo_Zwarte_Autor
from bpp.models.profile import BppUser as User
from bpp.models import Jednostka, Wydzial, Rodzaj_Zrodla, Zrodlo, Tytul, \
    Autor, Praca_Doktorska, Praca_Habilitacyjna, Patent, Patent_Autor
from bpp.jezyk_polski import warianty_zapisanego_nazwiska

from django.db.models import Model
from django.conf import settings

settings.DEBUG = False

# Put this on your base model (or monkey patch it onto django's Model if that's your thing)
def reload(self):
    new_self = self.__class__.objects.get(pk=self.pk)
    # You may want to clear out the old dict first or perform a selective merge
    self.__dict__.update(new_self.__dict__)


Model.reload = reload


def find_user(login):
    if login is None or login == '':
        return None
    return User.objects.get(pk=login)

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

    return u"http://" + s

def set_seq(s):
    if settings.DATABASES['default']['ENGINE'].find('postgresql') >= 0:
        from django.db import connection

        cursor = connection.cursor()
        cursor.execute(
            "SELECT setval('%s_id_seq', (SELECT MAX(id) FROM %s))" % (s, s))


def punktacja(dct, kw):
    kw.update(dict(
        # ModelPunktowany
        impact_factor=dct['impact'] or 0.00,
        punkty_kbn=dct['pk'] or 0.00,
        index_copernicus=dct['ind_cop'] or 0.00,
        punktacja_wewnetrzna=dct['pkt_wewn'] or 0.00,
        weryfikacja_punktacji=dct['weryfikacja_punktacji'],
        kc_impact_factor=dct['kc_impact'],
        kc_punkty_kbn=dct['kc_pk'],
        kc_index_copernicus=dct['kc_ind_cop']))


def afiliacja(dct, kw):
    kw.update(dict(
        # ModelAfiliowanyRecenzowany
        afiliowana=dct['afiliowana'],
        recenzowana=dct['recenzowana']
    ))

    for field in ['afiliowana', 'recenzowana']:
        if kw[field] == None:
            print "Ustawiam %s=False dla pracy z ID: %s " % (field, dct['id'])
            kw[field] = False


def szczegoly_i_inne(dct, kw, zrodlowe_pole_dla_informacji):
    d = dict(
        pk=dct['id'],

        # ModelZeSzczegolami
        # informacje=
        szczegoly=dct['szczegoly'],
        uwagi=dct['uwagi'],
        slowa_kluczowe=dct['slowa_kluczowe'],

        # ModelZRokiem
        rok=dct['rok'],

        # ModelZWWW
        www=convert_www(dct['www']),
    )

    if zrodlowe_pole_dla_informacji is not None:
        d['informacje'] = dct[zrodlowe_pole_dla_informacji]

    kw.update(d)


def idx(klass, attr='pk'):
    "Pobiera wszystkie modele klasy 'klass' do słownika wg. indeksu atrybuty 'attr'"
    return dict([(getattr(x, attr), x) for x in klass.objects.all()])


class Cache:
    def __init__(self):
        pass

    def initialize(self):
        self.typy_kbn = idx(Typ_KBN)
        self.jezyki = idx(Jezyk)
        self.statusy_korekty = idx(Status_Korekty)
        self.informacje_z = idx(Zrodlo_Informacji, 'nazwa')
        self.typy_odpowiedzialnosci = idx(Typ_Odpowiedzialnosci)
        self.charaktery = idx(Charakter_Formalny, 'skrot')


cache = Cache()


def jezyki_statusy(dct, kw):
    kw.update(dict(
        # ModelTypowany
        jezyk=cache.jezyki[dct['jezyk']],
        typ_kbn=cache.typy_kbn.get(dct['kbn'], cache.typy_kbn[3]),

        # ModelZeStatusem
        status_korekty=cache.statusy_korekty[int(dct['status'])],

        # ModelZInformacjaZ
        informacja_z=cache.informacje_z.get(dct['info_src'], None),
    ))


def dwa_tytuly(dct, kw):
    kw.update(dict(
        # ModelZTytulem
        tytul_oryginalny=dct['tytul_or'],
        tytul=dct['title'],
    ))


def poprzestawiaj_wartosci_pol(bib, zakazane, docelowe):
    for field in zakazane:
        if bib[field]:
            if hasattr(bib[field], 'strip'):
                bib[field] = bib[field].strip()

            skrot = charakter.get(bib['charakter'])['skrot'].strip()

            msg = [u"REKORD: \t", unicode(bib['id']),
                   u"\tchar: ", unicode(bib['charakter']),
                   u"\t", skrot,
                   u"\tZAWIERA WARTOSC DLA POLA \t", field,
                   u"PRZENOSZE DO POLA '", docelowe,
                   u"' (wartosc: ", unicode(bib[field]), u")"]

            print "%r" % u" ".join(msg)

            if bib[docelowe] is None:
                bib[docelowe] = u''

            if type(bib[field]) == int:
                bib[field] = str(bib[field])

            try:
                bib[docelowe] += bib[field]
            except UnicodeDecodeError, e:
                raise Exception(type(bib[field]), bib[field])
            bib[field] = ""


def skoryguj_wartosci_pol(bib):
    if bib['new_zrodlo'] == 0:
        bib['new_zrodlo'] = -1

    if bib['jezyk'] == 6:
        bib['jezyk'] = 5


def zrob_korekty(cur):
    zmiany = [
        (95, 'imiona', u'Radzisław J.'),
        (1549, 'imiona', u'Leszek'),
        (9934, 'poprzednie_nazwiska', u'Piętka'),
        (561, 'nazwisko', u'Jakimiec-Kimak'),
        (5437, 'imiona', u'Jamal'),
        (6680, 'imiona', u'Sławomir'),
        (10285, 'nazwisko', u'Kowal'),
        (15791, 'nazwisko', u'Janiszewska-Grzyb'),
        (8164, 'imiona', u'Majda'),
        (174, 'imiona', u'Kinga K.'),
        (907, 'imiona', u'Małgorzata H.'),
        (9793, 'poprzednie_nazwiska', u'Klucha'),
        (11186, 'poprzednie_nazwiska', u'Czarnota'),
        (10418, 'imiona', u'D.H.'),
        (4990, 'imiona', u'Dorota Irena'),
        (8599, 'poprzednie_nazwiska', u'Zawitkowska-Klaczyńska'),
        (440, 'imiona', u'Jerzy B.'),
        (166, 'imiona', u'Tomasz R.'),
        (4335, 'imiona', u'Katarzyna'),
        (11264, 'imiona', u'Krystyna H.'),
        (2718, 'imiona', u'Elżbieta'),
        (1140, 'imiona', u'Beata Z.'),
        (11058, 'imiona', u'Agnieszka'),
        (516, 'imiona', u'Wojciech P.'),
        (10584, 'imiona', u'I.M.'),
        (2221, 'imiona', u'Henryk T.'),
        (175, 'imiona', u'Stanisław Jerzy'),
        (1002, 'nazwiska', u'Jabłońska-Ulbrych'),
        (20, 'poprzednie_nazwiska', u'Adamczyk-Cioch'),
        (5099, 'imiona', u'Jean-Pierre')
    ]

    for pk, atrybut, wartosc in zmiany:
        aut = Autor.objects.get(pk=pk)
        setattr(aut, atrybut, wartosc)
        aut.save()

    # Artur J. Jakimiuk
    cur.execute("UPDATE b_a SET idt_aut = 17955 WHERE id = 77174")

    cur.execute(
        "UPDATE bib SET szczegoly = 's. 78', mceirok = '' WHERE id = 59665")
    cur.execute("""UPDATE bib SET
        uwagi = uwagi || 'Lengerich 2004. Pabst Sci. Pub.', mceirok = '', wydawnictwo = ''
        WHERE id = 31284""")

    cur.execute("UPDATE b_a SET idt_aut = 6903 WHERE id = 21550")
    cur.execute(
        "UPDATE b_a SET naz_zapis = 'Jolanta Kitlińska' WHERE id = 21255")
    cur.execute("UPDATE b_a SET naz_zapis = 'Anna Bednarek' WHERE id = 43796")
    cur.execute("UPDATE b_a SET naz_zapis = 'Bogusław Helon' WHERE id = 87974")


def wez_autorow(pk, pgsql_conn):
    cur2 = pgsql_conn.cursor(cursor_factory=extras.DictCursor)
    cur2.execute(
        "SELECT id, idt_aut, idt_jed, lp, naz_zapis, typ_autora FROM b_a WHERE idt = %s" % pk)
    ret = cur2.fetchall()
    cur2.close()
    return ret


def zrob_autorow_dla(wc, klass, pgsql_conn):
    for row in wez_autorow(wc.pk, pgsql_conn):
        if row['idt_jed'] == 0:
            row['idt_jed'] = -1

        if row['id'] == 107513:
            a = Autor.objects.create(imiona=u'J.', nazwisko=u'Posłuszna')
            row['idt_aut'] = a.pk

        autor = Autor.objects.get(pk=row['idt_aut'])
        wzn = list(warianty_zapisanego_nazwiska(autor.imiona, autor.nazwisko,
                                                autor.poprzednie_nazwiska))

        if row['typ_autora'] == 0:
            print "REKORD", row['id'], "TYP AUTORA= 0, ustawiam 1"
            row['typ_autora'] = 1

        typ = cache.typy_odpowiedzialnosci[row['typ_autora']]

        try:
            klass.objects.create(
                rekord=wc,
                autor=autor,
                jednostka=Jednostka.objects.get(pk=row['idt_jed']),
                kolejnosc=row['lp'],
                zapisany_jako=row['naz_zapis'],
                typ_odpowiedzialnosci=typ
            )
        except IntegrityError, e:
            print "ERROR dla pracy %r, autor %r, kolejnosc %r, typ_odpowiedzialnosci %r" % (wc, autor, row['lp'], typ)
            raise e


def zrob_userow(cur):
    cur.execute("""SELECT login, haslo, nazwisko_i_imie, e_mail, adnotacje,
            uprawnienia, id, created_on, last_access, created_by, edited_by
            FROM users ORDER BY id""")
    later = []
    while True:
        l = cur.fetchone()
        if l is None:
            break

        imie, nazwisko = l['nazwisko_i_imie'].split(" ", 1)
        uprawnienia = l['uprawnienia'].split(":")

        u = User.objects.create(
            pk=l['id'],
            username=l['login'],
            is_staff=True,
            first_name=imie,
            last_name=nazwisko,
            email=l['e_mail'])
        u.set_password(l['haslo'])
        u.save()

        for letter, name in dict(
                S="dane systemowe", E="wprowadzanie danych",
                B="przeglądanie", I="indeks autorów",
                A="administracja").items():
            if letter in uprawnienia:
                if letter == "B":
                    # Ignorujemy grupę "przeglądanie" totalnie
                    continue
                u.groups.add(Group.objects.get(name=name))
                # W promocji, dołóż wszystkim którzy mogą wprowadzać
                # dane opcje edycji struktury uczelni:
                if letter == "E":
                    u.groups.add(Group.objects.get(name="struktura"))

        u.utworzony = l['created_on']
        if l['created_by'] is not None:
            try:
                u.utworzony_przez = User.objects.get(pk=l['created_by'])
            except User.DoesNotExist:
                later.append((u.pk, 'utworzony_przez', l['created_by']))
                pass

        u.zmieniony = l['last_access']
        if l['edited_by'] is not None:
            try:
                u.zmieniony_przez = User.objects.get(pk=l['edited_by'])
            except User.DoesNotExist:
                later.append((u.pk, 'zmieniony_przez', l['edited_by']))

        u.adnotacje = l['adnotacje']
        u.save()

    for pk, attribute, value in later:
        u = User.objects.get(pk=pk)
        setattr(u, attribute, User.objects.get(pk=value))
        u.save()


def utworzono(model, bib):
    model.utworzono = bib['created_on']
    model.save()


def admin_log_history(obj, dct):
    user = find_user(dct['created_by'])
    if user is not None:
        #obj.reload()
        kw = dict(
            user_id=user.pk,
            content_type_id=ContentType.objects.get_for_model(obj).pk,
            object_id=obj.pk,
            object_repr=unicode(obj),
            change_message="Import z poprzedniej wersji bazy danych",
            action_flag=ADDITION)
        try:
            LogEntry.objects.log_action(**kw)
        except DatabaseError, e:
            print e
            print kw
            raise e

    user = find_user(dct['edited_by'])
    if user is not None:
        #obj.reload()
        LogEntry.objects.log_action(
            user_id=user.pk,
            content_type_id=ContentType.objects.get_for_model(obj).pk,
            object_id=obj.pk,
            object_repr=unicode(obj),
            change_message="Ostatnia edycja w poprzedniej wersji bazy danych",
            action_flag=CHANGE
        )
    utworzono(obj, dct)


def zrob_jednostki(cur, initial_offset, skip):
    cur.execute("""SELECT id, skrot, nazwa, wyd, to_print, email, www,
            created_on, last_access, created_by, edited_by, opis
            FROM jed OFFSET %s""" % initial_offset)

    while True:
        jed = cur.fetchone()
        if jed is None:
            break

        wyd = Wydzial.objects.get(pk=jed['wyd'])

        # Jest to konieczne, bo coś potem autocomplete się psuje... i podobnie
        # dla innych ID w bazie
        if jed['id'] == 0:
            jed['id'] = -1

        kw = dict(pk=jed['id'], nazwa=jed['nazwa'], skrot=jed['skrot'],
                  wydzial=wyd, widoczna=jed['to_print'] == "*",
                  email=jed['email'], www=convert_www(jed['www']), adnotacje=jed['opis'])
        j = Jednostka.objects.create(**kw)
        admin_log_history(j, jed)

        for _skip in range(skip):
            cur.fetchone()


def zrob_zrodla(cur, initial_offset, skip):
    cur.execute("""SELECT rodzaj, skrot, www, nazwa, adnotacje,
            id, created_on, last_access, created_by, edited_by, issn, e_issn
            FROM zrodla OFFSET %s""" % initial_offset)

    while True:
        zrod = cur.fetchone()
        if zrod is None:
            break

        rodzaj = Rodzaj_Zrodla.objects.get(pk=zrod['rodzaj'])

        if zrod['id'] == 0:
            zrod['id'] = -1

        kw = dict(pk=zrod['id'], rodzaj=rodzaj,
                  nazwa=zrod['nazwa'], skrot=zrod['skrot'],
                  issn=zrod['issn'], e_issn=zrod['e_issn'],
                  adnotacje=zrod['adnotacje'])

        @transaction.atomic
        def _txn():
            z = Zrodlo.objects.create(**kw)
            admin_log_history(z, zrod)

        while True:
            try:
                _txn()
                break
            except IntegrityError:
                pass

        for _skip in range(skip):
            cur.fetchone()

@transaction.atomic
def zrob_autorow(cur, initial_offset=0, skip=0):
    tytuly = dict([(x.skrot, x) for x in Tytul.objects.all()])

    cur.execute("""SELECT id, imiona, nazwisko, idt_jed, email, www, tytul,
            stanowisko, urodzony, zmarl, created_on, created_by, last_access,
            edited_by, adnotacje, haslo, hide_on_unit, dawne_nazwisko
            FROM aut ORDER BY nazwisko, imiona OFFSET %s""" % initial_offset)

    while True:
        aut = cur.fetchone()
        if aut is None:
            break

        tytul = None
        if aut['tytul']:
            try:
                tytul = tytuly[aut['tytul']]
            except KeyError:
                tytul = Tytul.objects.create(nazwa=aut['tytul'],
                                             skrot=aut['tytul'])
                print "UTWORZYLEM TYTUL", tytul

        imiona = aut['imiona']
        if imiona is None:
            imiona = ''

        kw = dict(pk=aut['id'], imiona=imiona,
                  nazwisko=aut['nazwisko'].strip(), tytul=tytul,
                  email=aut['email'], www=convert_www(aut['www']), urodzony=aut['urodzony'],
                  zmarl=aut['zmarl'],
                  pokazuj_na_stronach_jednostek=aut['hide_on_unit'] == 0,
                  poprzednie_nazwiska=aut['dawne_nazwisko'])

        @transaction.atomic
        def _txtn():
            a = Autor.objects.create(**kw)
            admin_log_history(a, aut)

        while True:
            try:
                _txtn()
                break
            except IntegrityError:
                continue

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
            OFFSET %s""" % initial_offset)

    while True:
        b_a = cur.fetchone()
        if b_a is None:
            break

        if b_a['idt_jed'] == 0:
            b_a['idt_jed'] = -1

        try:
            jednostka = Jednostka.objects.get(pk=b_a['idt_jed'])
        except:
            raise Exception("BRAK JEDNOSTKI O ID: ", b_a['idt_jed'])

        try:
            autor = Autor.objects.get(pk=b_a['idt_aut'])
        except:
            raise Exception("BRAK AUTORA O ID: ", b_a['idt_aut'])

        rozpoczal_prace = None
        if b_a['current_idt_jed'] == b_a['idt_jed']:
            rozpoczal_prace = datetime.now().date()

        Autor_Jednostka.objects.create(
            autor=autor,
            jednostka=jednostka,
            rozpoczal_prace=rozpoczal_prace,
            zakonczyl_prace=None,
            funkcja=None)

        for _skip in range(skip):
            cur.fetchone()


def zrob_import_z_tabeli(kw, bib, zakazane, docelowe,
                         zrodlowe_pole_dla_informacji):
    # Tych pól wydawnictwo ma nie mieć
    poprzestawiaj_wartosci_pol(bib, zakazane, docelowe)
    skoryguj_wartosci_pol(bib)

    punktacja(bib, kw)
    afiliacja(bib, kw)
    dwa_tytuly(bib, kw)
    szczegoly_i_inne(bib, kw, zrodlowe_pole_dla_informacji)
    jezyki_statusy(bib, kw)


def zrob_wydawnictwo(kw, bib, klass, autor_klass, zakazane, docelowe,
                     pgsql_conn, zrodlowe_pole_dla_informacji, usun_przed=None):
    zrob_import_z_tabeli(kw, bib, zakazane, docelowe,
                         zrodlowe_pole_dla_informacji)
    if usun_przed:
        for field in usun_przed:
            del kw[field]
    try:
        wc = klass.objects.create(**kw)
    except decimal.InvalidOperation, e:
        print kw
        raise e
    admin_log_history(wc, bib)
    zrob_autorow_dla(wc, autor_klass, pgsql_conn)
    return wc


def zrob_wydawnictwo_ciagle(bib, skrot, pgsql_conn):
    kw = dict(
        # Wydawnictwo_Ciagle
        zrodlo=Zrodlo.objects.get(pk=bib['new_zrodlo']),
        charakter_formalny=cache.charaktery[skrot],
    )

    w = zrob_wydawnictwo(kw, bib, Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor,
                         zakazane=['redakcja', 'mceirok', 'wydawnictwo', 'isbn',
                                   'nr_zeszytu'],
                         docelowe='uwagi', pgsql_conn=pgsql_conn,
                         zrodlowe_pole_dla_informacji='new_zrodlo_src')

    # admin_log_history(w, bib)


def zrob_baze_wydawnictwa_zwartego(bib):
    kw = dict(
        miejsce_i_rok=bib['mceirok'],
        wydawnictwo=bib['wydawnictwo'],
        redakcja=bib['redakcja'],
        isbn=bib['isbn'],
        informacje=bib['new_zrodlo_src']
    )
    return kw


def zrob_wydawnictwo_zwarte(bib, skrot, pgsql_conn):
    kw = zrob_baze_wydawnictwa_zwartego(bib)
    kw['charakter_formalny'] = cache.charaktery[skrot]
    bib['new_zrodlo_src'] = None

    wc = zrob_wydawnictwo(kw, bib, Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor,
                          zakazane=['new_zrodlo', 'new_zrodlo_src'],
                          docelowe='uwagi', pgsql_conn=pgsql_conn,
                          zrodlowe_pole_dla_informacji=None)

    if bib['ilosc_znakow_wydawnicznych'] is not None:
        wc.liczba_znakow_wydawniczych = bib['ilosc_znakow_wydawnicznych']
        wc.save()

    # admin_log_history(wc, bib)


def zrob_doktorat_lub_habilitacje(bib, pgsql_conn):
    kw = zrob_baze_wydawnictwa_zwartego(bib)

    zrob_import_z_tabeli(kw, bib,
                         zakazane=['new_zrodlo'],
                         docelowe='uwagi',
                         zrodlowe_pole_dla_informacji=None)

    autor = wez_autorow(bib['id'], pgsql_conn)
    if len(autor) != 1:
        print(
        "dla pracy doktorskiej/habilitacyjnej z id %s ilosc autorow jest rowna %s, IGNORUJE TEN WPIS" % (
            bib['id'], len(autor)))
        return

    kw['autor'] = Autor.objects.get(pk=autor[0]['idt_aut'])
    kw['jednostka'] = Jednostka.objects.get(pk=autor[0]['idt_jed'])

    if bib['charakter'] == 21: # praca doktorska
        klass = Praca_Doktorska
    elif bib['charakter'] == 4: # praca habilitacyjna
        klass = Praca_Habilitacyjna
    else:
        raise Exception(
            "Probuje zaimportowac doktorat lub habilitacje, a charakter to %s" %
            bib['charakter'])

    try:
        r = klass.objects.create(**kw)
    except decimal.InvalidOperation, e:
        print kw
        raise e

    admin_log_history(r, bib)


def zrob_patent(bib, pgsql_conn):
    kw = zrob_baze_wydawnictwa_zwartego(bib)
    p = zrob_wydawnictwo(kw, bib, Patent, Patent_Autor,
                         zakazane=['new_zrodlo', 'new_zrodlo_src'],
                         docelowe='uwagi', pgsql_conn=pgsql_conn,
                         zrodlowe_pole_dla_informacji=None,
                         usun_przed=['tytul', 'isbn', 'wydawnictwo', 'redakcja',
                                     'typ_kbn', 'jezyk', 'miejsce_i_rok'])

    # admin_log_history(p, bib)


charakter = {}


@transaction.atomic
def zrob_publikacje(cur, pgsql_conn, initial_offset, skip):
    global charakter

    cur.execute("SELECT * FROM pub")
    charakter = dict([(x['id'], x) for x in cur.fetchall()])

    for obj in [Wydawnictwo_Zwarte, Wydawnictwo_Ciagle, Patent, Praca_Doktorska,
                Praca_Habilitacyjna]:
        obj.objects.all().delete()

    cur.execute("""SELECT id, tytul_or, title, zrodlo, szczegoly, uwagi,
        charakter, impact, redakcja, status, rok, rok_publikacji, edited_by,
        kbn, afiliowana, recenzowana, jezyk, pk, created_on, last_access,
        created_by, edited_by, new_zrodlo, new_zrodlo_src, mceirok,
        wydawnictwo, slowa_kluczowe, www, ind_cop, pkt_wewn,
        auto_pk, isbn, nr_zeszytu, info_src, kc_impact, kc_pk, kc_ind_cop,
        weryfikacja_punktacji, ilosc_znakow_wydawnicznych FROM bib ORDER BY id OFFSET %s""" % initial_offset)

    # Charakter 21 lub 4 => praca doktorska lub habilitacyjna
    # Charakter 16 => patent

    while True:
        bib = cur.fetchone()
        if bib is None:
            break

        skrot = charakter.get(bib['charakter'])['skrot'].strip()
        if skrot == 'T\xc5\x81':
            skrot = u'TŁ'

        @transaction.atomic
        def _txn():

            if bib['new_zrodlo']:
                zrob_wydawnictwo_ciagle(bib, skrot, pgsql_conn)
            else:
                if skrot == 'D' or skrot == 'H':
                    # doktorat lub habilitacja
                    zrob_doktorat_lub_habilitacje(bib, pgsql_conn)

                elif skrot == 'PAT':
                    zrob_patent(bib, pgsql_conn)

                else:
                    zrob_wydawnictwo_zwarte(bib, skrot, pgsql_conn)

        _txn()
        for _skip in range(skip):
            cur.fetchone()

class ColumnNotIndexed(Exception):
    def __init__(self, table, col, *args, **kw):
        super(ColumnNotIndexed, self).__init__(*args, **kw)
        self.table = table
        self.col = col

    def __str__(self):
        return "No index. Create one with CREATE INDEX %(table)s_%(col)s_idx ON %(table)s(%(col)s)" % dict(
            table=self.table, col=self.col)

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
    for table in ['bpp_wydawnictwo_ciagle', 'bpp_patent', 'bpp_wydawnictwo_zwarte', 'bpp_praca_doktorska', 'bpp_praca_habilitacyjna']:
        cluster(table, "tytul_oryginalny")
    cluster("bpp_rekord_mat", "rok")


def db_connect():
    #print "Trying to connect...",
    if sys.platform == 'win32':
        pgsql_conn = psycopg2.connect(
            database="b_med",
            user="postgres",
            password="",
            host="bpplocal",
            port=5432)
    else:
        pgsql_conn = psycopg2.connect(
            database="b_med",
            user="aml",
            password="1g97r8mhvfsdaoighq329thadsfasd",
            host="localhost",
            port=5432)
        #print " connected!"
    pgsql_conn.set_client_encoding('UTF8')
    return pgsql_conn


def db_disconnect(cur):
    cur.close()


class Command(BaseCommand):
    help = 'Importuje baze danych BPP z istniejacego serwera PostgreSQL'

    option_list = BaseCommand.option_list + (
        make_option("--uzytkownicy", action="store_true"),
        make_option("--jednostki", action="store_true"),
        make_option("--powiazania", action="store_true"),
        make_option("--zrodla", action="store_true"),
        make_option("--autorzy", action="store_true"),
        make_option("--korekty", action="store_true"),
        make_option("--publikacje", action="store_true"),
        make_option("--clusters", action="store_true"),
        make_option("--initial-offset", action="store", type="int", default=0),
        make_option("--skip", action="store", type="int", default=0))

    @transaction.atomic
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

        cache.initialize()
        pgsql_conn = db_connect()
        cur = pgsql_conn.cursor(cursor_factory=extras.DictCursor)

        if options['uzytkownicy']:
            zrob_userow(cur)#  , options['initial_offset'], options['skip'])

        if options['jednostki']:
            print "JEDNOSTKI", options['initial_offset']
            zrob_jednostki(cur, options['initial_offset'], options['skip'])

        if options['autorzy']:
            print "AUTORZY", options['initial_offset']
            zrob_autorow(cur, options['initial_offset'], options['skip'])
            set_seq("bpp_autor")

        if options['powiazania']:
            print "POWIAZANIA", options['initial_offset']
            zrob_powiazania(cur, options['initial_offset'], options['skip'])

        if options['zrodla']:
            zrob_zrodla(cur, options['initial_offset'], options['skip'])
            set_seq("bpp_zrodlo")

        if options['korekty']:
            zrob_korekty(cur)

        # Publikacje
        if options['publikacje']:
            # XXX TODO ---- CZY przypadkiem sekwencje nie powinnismy
            # ustawiac w run_import

            zrob_publikacje(cur, pgsql_conn, options['initial_offset'],
                            options['skip'])

            set_seq("bpp_wydawnictwo_ciagle")
            set_seq("bpp_wydawnictwo_zwarte")
            set_seq("bpp_patent")
            set_seq("bpp_praca_doktorska")
            set_seq("bpp_praca_habilitacyjna")
            set_seq("bpp_bppuser")

        if options['clusters']:
            make_clusters()

        try:
            x = Jednostka.objects.get(nazwa="Obca jednostka")
        except Jednostka.DoesNotExist:
            pass
        else:
            x.wchodzi_do_raportow = False
            x.save()

        db_disconnect(cur)
