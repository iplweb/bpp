import os

import progressbar
from dbfread import DBF
from django.db.models import Q

from bpp import models as bpp
from bpp.models import Status_Korekty, wez_zakres_stron, parse_informacje
from bpp.system import User
from import_dbf import models as dbf
from .codecs import custom_search_function  # noqa

custom_search_function  # noqa


def addslashes(v):
    if not v:
        return v
    if not hasattr(v, 'replace'):
        return v
    return v.replace("'", "''")


def exp_combine(a, b, sep=", "):
    ret = ''
    if a:
        ret = a

    if b:
        if ret:
            ret += sep
        ret += b

    while ret.find("  ") >= 0:
        ret = ret.replace("  ", " ")
    return ret


def import_dbf(filename, appname="import_dbf"):
    tablename = appname + "_" + os.path.basename(filename.split(".")[0]).lower()
    dbf = DBF(filename, encoding="my_cp1250")

    print("BEGIN;")
    print("DROP TABLE IF EXISTS %s;" % tablename)
    print("CREATE TABLE %s(" % tablename)
    for field in dbf.fields:
        print("\t%s text," % field.name.lower())
    print("\t_ignore_me text);")

    for record in dbf:
        print("INSERT INTO %s(%s) VALUES(%s);" % (tablename, ", ".join([f.lower() for f in record]),
                                                  ", ".join(["'%s'" % addslashes(v or '') for v in record.values()])))

    print("COMMIT;")


def exp_parse_str(s):
    """
    :param s: tekst z pola tekstowego bazy danych Expertus, np "#102$ #a$ Tytul #b$ #c$ ...
    :return: słownik zawierający pole 'id' oraz kolejno pola 'a', 'b', 'c' itd
    """
    assert len(s) >= 5
    assert s[0] == '#'
    assert s[4] == '$'

    ret = {}

    ret['id'] = int(s[1:4])

    s = s[5:].strip()

    literki = "abcdefghij"
    cnt = 0

    while True:
        try:
            literka = literki[cnt]
        except IndexError:
            break

        sep = f"#{literka}$"
        pos = s.find(sep)
        if pos < 0:
            # Nie ma takiego separatora w tym ciągu znakw
            continue
        assert pos == 0
        s = s[3:]

        while True:
            try:
                nastepna = literki[cnt + 1]
            except IndexError:
                ret[literka] = s.strip()
                break

            next_pos = s.find(f"#{nastepna}$")
            if next_pos < 0:
                # Nie ma następnego separatora, szukaj kolejnego
                cnt += 1
                continue

            ret[literka] = s[:next_pos].strip()
            break

        s = s[next_pos:]
        cnt += 1

    return ret


def exp_add_spacing(s):
    s = s.replace(".", ". ")
    while s.find("  ") >= 0:
        s = s.replace("  ", " ")
    s = s.replace(". )", ".)")
    s = s.replace(". -", ".-")
    s = s.replace(". ,", ".,")
    return s.strip()


def integruj_uczelnia(nazwa="Domyślna Uczelnia", skrot="DU"):
    """Jeżeli istnieje jakikolwiek obiekt uczelnia w systemie, zwróć go.

    Jeżeli nie ma żadnych obiektw Uczelnia w systemie, utwórz obiekt z
    ustawieniami domyślnymi i zwróć go. """

    if bpp.Uczelnia.objects.exists():
        return bpp.Uczelnia.objects.first()

    uczelnia, created = bpp.Uczelnia.objects.get_or_create(nazwa=nazwa, skrot=skrot)
    if created:
        User.objects.create_superuser(username="admin", password="admin", email=None)
    return uczelnia


def integruj_wydzialy(uczelnia):
    """Utwórz wydziały na podstawie importu DBF"""
    for wydzial in dbf.Wyd.objects.all():
        bpp.Wydzial.objects.get_or_create(uczelnia=uczelnia, nazwa=wydzial.nazwa, skrot=wydzial.skrot)


def integruj_jednostki(uczelnia):
    for jednostka in dbf.Jed.objects.all():
        if bpp.Jednostka.objects.filter(nazwa=jednostka.nazwa, skrot=jednostka.skrot).exists():
            # Jeżeli istnieje jednostka o dokładnie takiej nazwie, to przejdź dalej
            continue

        widoczna = True
        if jednostka.nazwa == "":
            # Jeżeli nazwa jest pusta, nadaj identyfikator ale i ukryj później
            jednostka.nazwa = "Jednostka %s" % jednostka.idt_jed
            widoczna = False

        while bpp.Jednostka.objects.filter(nazwa=jednostka.nazwa).exists():
            jednostka.nazwa += "*"

        while bpp.Jednostka.objects.filter(skrot=jednostka.skrot).exists():
            jednostka.skrot += "*"

        bpp_jednostka, _ign = bpp.Jednostka.objects.get_or_create(
            nazwa=jednostka.nazwa,
            skrot=jednostka.skrot,
            email=jednostka.email,
            www=jednostka.www,
            wydzial=bpp.Wydzial.objects.get(skrot=jednostka.wyd_skrot),
            uczelnia=uczelnia,
            widoczna=widoczna
        )
        jednostka.bpp_jednostka = bpp_jednostka
        jednostka.save()


def data_or_null(s):
    if s == "15011961":
        return
    if not s:
        return None
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"


def get_dict(model, attname):
    return dict([(getattr(i, attname), i) for i in model.objects.all()])


def integruj_tytuly_autorow():
    for tytul, in dbf.Aut.objects.all().order_by().values_list("tytul").distinct("tytul"):
        tytul = tytul.strip()
        if not tytul:
            continue

        tytul = exp_add_spacing(tytul)
        try:
            bpp.Tytul.objects.get(skrot=tytul)
        except bpp.Tytul.DoesNotExist:
            bpp.Tytul.objects.create(nazwa=tytul, skrot=tytul)


def integruj_funkcje_autorow():
    for funkcja, in dbf.Aut.objects.all().order_by().values_list("stanowisko").distinct("stanowisko"):
        funkcja = funkcja.strip()
        if not funkcja:
            continue

        funkcja = exp_add_spacing(funkcja)
        try:
            bpp.Funkcja_Autora.objects.get(nazwa=funkcja)
        except bpp.Funkcja_Autora.DoesNotExist:
            bpp.Funkcja_Autora.objects.create(nazwa=funkcja, skrot=funkcja)


def integruj_autorow(uczelnia):
    integruj_tytuly_autorow()
    integruj_funkcje_autorow()

    tytuly = get_dict(bpp.Tytul, "skrot")
    funkcje = get_dict(bpp.Funkcja_Autora, "skrot")

    for autor in progressbar.progressbar(
            dbf.Aut.objects.all().select_related("idt_jed", "idt_jed__bpp_jednostka"),
            max_value=dbf.Aut.objects.count(),
            widgets=[progressbar.Bar(), " ",
                     progressbar.Timer(), " ",
                     progressbar.AdaptiveETA()]):
        bpp_autor = None

        if not bpp_autor and autor.exp_id:
            try:
                bpp_autor = bpp.Autor.objects.get(expertus_id=autor.exp_id)
            except bpp.Autor.DoesNotExist:
                pass

        if not bpp_autor and autor.orcid_id:
            try:
                bpp_autor = bpp.Autor.objects.get(orcid=autor.orcid_id)
            except bpp.Autor.DoesNotExist:
                pass

        if not bpp_autor and autor.pbn_id:
            try:
                bpp_autor = bpp.Autor.objects.get(pbn_id=autor.pbn_id)
            except bpp.Autor.DoesNotExist:
                pass

        if bpp_autor is not None:
            # Istnieje już autor z takim ORCID lub PBN ID, nie tworzymy
            autor.bpp_autor = bpp_autor
            autor.save()

        if bpp_autor is None:
            # Nie istnieje taki autor; tworzymy
            tytul = None
            if autor.tytul:
                tytul = tytuly.get(autor.tytul)

            bpp_autor = bpp.Autor.objects.create(
                nazwisko=autor.nazwisk_bz,
                imiona=autor.imiona_bz,
                tytul=tytul,
                pbn_id=autor.pbn_id or None,
                orcid=autor.orcid_id or None,
                expertus_id=autor.exp_id or None
            )

        autor.bpp_autor = bpp_autor
        autor.save()

        # Jeżeli nie ma tego przypisania do jednostki, to utworz:
        if not autor.idt_jed_id:
            continue

        jednostka = autor.idt_jed
        try:
            bpp.Autor_Jednostka.objects.get(autor=bpp_autor, jednostka=jednostka.bpp_jednostka)
        except bpp.Autor_Jednostka.DoesNotExist:
            funkcja_autora = None
            if autor.stanowisko:
                funkcja_autora = funkcje.get(autor.stanowisko)

            bpp.Autor_Jednostka.objects.create(
                autor=bpp_autor,
                jednostka=jednostka.bpp_jednostka,
                funkcja=funkcja_autora,
                rozpoczal_prace=data_or_null(autor.prac_od),
                zakonczyl_prace=data_or_null(autor.dat_zwol)
            )


def integruj_charaktery():
    for rec in dbf.Pub.objects.all():
        try:
            charakter = bpp.Charakter_Formalny.objects.get(skrot=rec.skrot)
        except bpp.Charakter_Formalny.DoesNotExist:
            charakter = bpp.Charakter_Formalny.objects.create(
                nazwa=rec.nazwa,
                skrot=rec.skrot,
            )
        rec.bpp_id = charakter
        rec.save()


def integruj_kbn():
    for rec in dbf.Kbn.objects.all():
        try:
            kbn = bpp.Typ_KBN.objects.get(skrot=rec.skrot)
        except bpp.Typ_KBN.DoesNotExist:
            kbn = bpp.Typ_KBN.objects.create(
                nazwa=rec.nazwa,
                skrot=rec.skrot
            )
        rec.bpp_id = kbn
        rec.save()


def integruj_jezyki():
    for rec in dbf.Jez.objects.all():
        try:
            jez = bpp.Jezyk.objects.get(Q(nazwa=rec.nazwa) | Q(skrot=rec.skrot))
        except bpp.Jezyk.DoesNotExist:
            jez = bpp.Jezyk.objects.create(
                nazwa=rec.nazwa,
                skrot=rec.skrot
            )
        rec.bpp_id = jez
        rec.save()


def integruj_zrodla():
    # pole usm_f:
    # - 988 -> numer ISBN,
    # - 985 -> jakiś identyfikator (dwa rekordy),
    # - 969 -> kilka rekordow nazwanych od okreslen openaccess
    # - 154 -> monografia
    # - 107 -> 10 rekordw (ISSN, numerki, nazwa pracy(?))
    # - 100 -> źrdło indeksowane

    rodzaj = bpp.Rodzaj_Zrodla.objects.get(nazwa='periodyk')

    for rec in dbf.Usi.objects.filter(usm_f='100'):
        rec.nazwa = exp_add_spacing(rec.nazwa)

        try:
            zrodlo = bpp.Zrodlo.objects.get(nazwa=rec.nazwa)
        except bpp.Zrodlo.DoesNotExist:
            zrodlo = bpp.Zrodlo.objects.create(
                nazwa=rec.nazwa,
                skrot=rec.skrot or rec.nazwa,
                rodzaj=rodzaj
            )
        rec.bpp_id = zrodlo
        rec.save()

    for rec in dbf.Usi.objects.filter(usm_f='152'):
        rec.nazwa = exp_add_spacing(rec.nazwa)
        try:
            wydawca = bpp.Wydawca.objects.get(nazwa=rec.nazwa)
        except bpp.Wydawca.DoesNotExist:
            wydawca = bpp.Wydawca.objects.create(
                nazwa=rec.nazwa,
            )
        rec.bpp_wydawca_id = wydawca
        rec.save()

    for rec in dbf.Usi.objects.filter(usm_f='154'):
        rec.nazwa = exp_add_spacing(rec.nazwa)
        try:
            seria = bpp.Seria_Wydawnicza.objects.get(nazwa=rec.nazwa)
        except bpp.Seria_Wydawnicza.DoesNotExist:
            seria = bpp.Seria_Wydawnicza.objects.create(
                nazwa=rec.nazwa,
            )
        rec.bpp_seria_wydawnicza_id = seria
        rec.save()


def integruj_publikacje():
    # zagadnienie nr 1 BPP: prace mają rok i rok_punkt inny: select rok, rok_punkt from import_dbf_bib where rok_punkt != rok and rok_punkt != '' order by rok;

    # zagadnienie nr 2: kody w polach tekstowych:
    #
    # postgres=# select distinct substr(tytul_or, 0, 6) from import_dbf_bib;
    #  substr
    # --------
    #  #102$
    #  #150$
    #  #204$

    # bpp=# select distinct substr(title, 1, 4) from import_dbf_bib;
    #  substr
    # --------
    #  #105
    #  #157
    #  #207

    # postgres=# select distinct substr(zrodlo, 0, 6) from import_dbf_bib;
    #  substr
    # --------
    #  #152$ -> (a: miejsce, b: numer id lub brak, c: rok)
    #  #100$ -> (a: numer id -> idt_usi -> Usi, B_U)
    #  #200$ -> (a: tytuł, b: podtytuł, c: pod red)

    statusy_korekt = dict([(a.nazwa, a) for a in Status_Korekty.objects.all()])
    mapping_korekt = {
        '!': 'przed korektą',
        '*': 'w trakcie korekty',
        'ű': 'po korekcie'
    }

    base_query = dbf.Bib.objects.filter(object_id=None)
    for rec in progressbar.progressbar(
            base_query.select_related(),
            max_value=base_query.count(),
            widgets=[progressbar.AnimatedMarker(), " ",
                     progressbar.Counter(), " ",
                     progressbar.Percentage(), " ",
                     progressbar.SimpleProgress(), " ",
                     progressbar.Timer(), " ",
                     progressbar.AdaptiveETA()]):
        kw = {}

        poz_a = dbf.Poz.objects.get_for_model(rec.idt, "A")
        if poz_a:
            rec.tytul_or += poz_a

        tytul = exp_parse_str(rec.tytul_or)

        title = None
        if rec.title:
            title = exp_parse_str(rec.title)
            if title['b']:
                raise NotImplementedError("co mam zrobic %r" % title)

            for literka in 'cdefgh':
                if literka in title.keys():
                    raise NotImplementedError("co mam z tym zrobic %r" % title)
            kw['tytul'] = title['a']

        kw['charakter_formalny'] = dbf.Pub.objects.get(skrot=rec.charakter).bpp_id

        try:
            kw['typ_kbn'] = dbf.Kbn.objects.get(skrot=rec.kbn).bpp_id
        except dbf.Kbn.DoesNotExist:
            kw['typ_kbn'] = bpp.Typ_KBN.objects.get(skrot='000')

        kw['jezyk'] = dbf.Jez.objects.get(skrot=rec.jezyk).bpp_id

        if rec.jezyk2:
            kw['jezyk_alt'] = dbf.Jez.objects.get(skrot=rec.jezyk2).bpp_id

        kw['rok'] = rec.rok
        kw['recenzowana'] = rec.recenzowan.strip() == '1'

        # afiliowana -- nie ma takiego pola
        # kw['afiliowana'] = rec.afiliowana.strip() == '1'

        # kbr -- co to za pole?
        # bpp=# select distinct kbr, count(*) from import_dbf_bib group by kbr;
        #  kbr | count
        # -----+-------
        #      | 86354
        #  000 |    41
        #  OA  |    21
        # (3 rows)

        # lf -- co to za pole?
        # bpp=# select distinct lf, count(*) from import_dbf_bib group by lf;
        #  lf | count
        # ----+-------
        #     |  9605
        #  0  | 66617
        #  1  | 10194
        # (3 rows)

        # study_gr -- co to za pole?
        # bpp=# select distinct study_gr, count(*) from import_dbf_bib group by study_gr;
        #  study_gr | count
        # ----------+-------
        #  0        | 86026
        #  1        |   390
        # (2 rows)

        # idt2 - 5 rekordw

        # pun_max - 1 rekord

        # kwartyl -- co to za pole?
        # bpp=# select distinct kwartyl, count(*) from import_dbf_bib group by kwartyl;
        #  kwartyl | count
        # ---------+-------
        #          | 85236
        #  A       |    37
        #  A1      |   831
        #  B       |    13
        #  B1      |   296
        #  CC      |     3
        # (6 rows)

        # lis_numer -- co to za pole?
        # bpp=# select distinct lis_numer, count(*) from import_dbf_bib group by lis_numer;
        #  lis_numer | count
        # -----------+-------
        #            | 86365
        #  10226     |     1
        #  116       |     8
        #  118       |     1
        #  1436      |     2
        #  157       |     1
        #  162       |     1
        #  165       |     1
        #  167       |     4
        #  182       |     1
        #  205       |     1
        #  22        |     8
        #  2700      |     1
        #  3180      |     1
        #  3903      |     1
        #  4930      |     2
        #  5206      |     1
        #  54        |     3
        #  6728      |     1
        #  75        |     3
        #  756       |     1
        #  7742      |     1
        #  8         |     1
        #  888       |     2
        #  89        |     3
        #  972       |     1
        # (26 rows)

        kw['status_korekty'] = statusy_korekt[mapping_korekt[rec.status]]

        if rec.punkty_kbn:
            kw['punkty_kbn'] = rec.punkty_kbn

        if rec.impact:
            kw['impact_factor'] = rec.impact

        if rec.link:
            kw['www'] = rec.link

        if rec.uwagi2:
            kw['adnotacje'] = rec.uwagi2

        if rec.pun_wl:
            kw['punktacja_wewnetrzna'] = rec.pun_wl

        if rec.issn:
            kw['issn'] = rec.issn

        if rec.eissn:
            kw['e_issn'] = rec.e_issn

        klass = None

        if tytul['id'] == 204:
            klass = bpp.Wydawnictwo_Zwarte
            kw['tytul_oryginalny'] = exp_combine(tytul['a'], tytul.get('b'), sep=": ")

            kw['szczegoly'] = exp_add_spacing(tytul['e'])
            if tytul.get('f'):
                if kw['szczegoly']:
                    kw['szczegoly'] += ", "
                kw['szczegoly'] += tytul['f']

            if tytul.get('c'):
                kw['tytul_oryginalny'] = exp_combine(kw['tytul_oryginalny'], tytul.get('c'))

            if tytul.get('d'):
                kw['tytul_oryginalny'] = exp_combine(kw['tytul_oryginalny'], tytul.get('d'))

            if kw['szczegoly']:
                kw['strony'] = wez_zakres_stron(kw['szczegoly'])

        elif tytul['id'] == 102:
            klass = bpp.Wydawnictwo_Ciagle
            kw['tytul_oryginalny'] = tytul['a']

            if tytul.get("b"):
                kw['tytul_oryginalny'] += ": " + tytul.get("b")

                kw['tekst_po_ostatnim_autorze'] = tytul.get('c')

            for literka in 'def':
                assert not tytul.get(literka), "co mam robic z %r" % tytul

        elif tytul['id'] == 150:
            klass = bpp.Wydawnictwo_Zwarte
            kw['tytul_oryginalny'] = exp_combine(tytul['a'], exp_combine(tytul.get('b'), tytul.get('d')), sep=" ")
            kw['informacje'] = tytul['c']  # "wstep i oprac. Edmund Waszynski"

        else:
            raise NotImplementedError(tytul)

        # Jeżeli pole 'zrodlo' jest dosc dlugie, reszta tego pola moze znalezc
        # sie w tabeli "Poz" z oznaczeniem literowym 'C'
        zrodlo_cd = dbf.Poz.objects.get_for_model(rec.idt, "C")
        if zrodlo_cd:
            rec.zrodlo += zrodlo_cd

        poz_g = dbf.Poz.objects.get_for_model(rec.idt, "G")
        poz_n = dbf.Poz.objects.get_for_model(rec.idt, "N")

        if poz_g:
            for elem in [elem.strip() for elem in poz_g.split('\r\n') if elem.strip()]:
                elem = exp_parse_str(elem)

                if elem['id'] == 202:
                    wydawca_id = None
                    try:
                        wydawca_id = int(elem['b'][1:])
                    except:
                        pass
                    if wydawca_id is not None:
                        kw['wydawca'] = dbf.Usi.objects.get(idt_usi=wydawca_id).bpp_wydawca_id
                    kw['miejsce_i_rok'] = f"{elem['a']} {elem['c']}"

                elif elem['id'] in [203, 154]:
                    # Seria wydawnicza

                    seria_wydawnicza_id = int(elem['a'][1:])
                    kw['seria_wydawnicza'] = dbf.Usi.objects.get(idt_usi=seria_wydawnicza_id).bpp_seria_wydawnicza_id

                    if elem.get('d') and elem.get('c'):
                        raise NotImplementedError(elem, rec, rec.idt)

                    kw['numer_w_serii'] = ''

                    for literka in "bcd":
                        if elem.get(literka):
                            kw['numer_w_serii'] = exp_combine(kw['numer_w_serii'], elem.get(literka))

                    for literka in "ef":
                        assert not elem.get(literka), (elem, rec)

                elif elem['id'] in [201, 206]:
                    # wydanie
                    kw['uwagi'] = exp_combine(kw.get('uwagi', ''), elem.get('a'), sep=" ")  # Wyd 1 pol
                    kw['uwagi'] = exp_combine(kw.get('uwagi', ''), elem.get('b'), sep=" ")  # pod red A. Kowalski

                    for literka in "cde":
                        assert not elem.get(literka), elem

                elif elem['id'] == 205:

                    isbn = elem['a']
                    if isbn.find("e-ISBN") >= 0:
                        kw['e_isbn'] = elem['a'].split("e-ISBN ")[1].strip()
                    elif isbn.find("ISBN") >= 0:
                        kw['isbn'] = elem['a'].split("ISBN ")[1].strip()
                    else:
                        kw['uwagi'] = exp_combine(kw.get('uwagi'), elem.get('a'), sep=", ")

                    for literka in "bcde":
                        assert not elem.get(literka)

                elif elem['id'] == 101:
                    kw['informacje'] = elem.get('a')
                    assert not elem.get('b'), (elem, rec)
                    assert not kw.get('szczegoly')
                    kw['szczegoly'] = elem.get('c')
                    if elem.get('d'):
                        if kw['szczegoly']:
                            kw['szczegoly'] += ", "
                        kw['szczegoly'] += elem.get('d')
                    assert not kw.get('uwagi')
                    if elem.get('e'):
                        if kw['szczegoly']:
                            kw['szczegoly'] += ", "
                        kw['szczegoly'] += elem.get('e')

                elif elem['id'] == 103:
                    # Konferencja
                    try:
                        konferencja = bpp.Konferencja.objects.get(nazwa=elem['a'])
                    except bpp.Konferencja.DoesNotExist:
                        konferencja = bpp.Konferencja.objects.create(nazwa=elem['a'])

                    assert not kw.get('konferencja'), (elem, rec)

                    kw['konferencja'] = konferencja
                    for literka in "bcde":
                        assert not elem.get(literka)

                elif elem['id'] == 153:
                    assert not kw.get('szczegoly')
                    kw['szczegoly'] = elem['a']

                    assert not kw.get('uwagi')
                    kw['uwagi'] = exp_combine(elem.get('b'), elem.get('c'))

                elif elem['id'] == 104:
                    assert not kw.get('uwagi'), (kw['uwagi'], elem, rec, rec.idt)
                    kw['uwagi'] = elem['a']
                    for literka in "bcd":
                        assert not elem.get(literka), (elem, rec, rec.idt)

                elif elem['id'] == 151:
                    # w ksiazkach, wydanie i "pod redakcja'
                    if kw['tytul_oryginalny'].find('=') >= 0:
                        raise NotImplementedError
                    kw['tytul_oryginalny'] = (kw['tytul_oryginalny'] + ". " + elem['a'] + " " + elem['b']).strip()

                    for literka in "cde":
                        assert not elem.get(literka), (elem, rec, rec.idt)

                elif elem['id'] == 155:
                    # "Komunikat tegoż w ...
                    assert not kw.get('adnotacje')
                    kw['adnotacje'] = elem.get('a')

                else:
                    raise NotImplementedError(elem, rec, rec.idt)

        assert not poz_n, "nie gotowy na poz_n %r %r %s" % (poz_a, rec, rec.idt)

        zrodlo = exp_parse_str(rec.zrodlo)
        if zrodlo['id'] == 200:
            # Wydawnictwo zwarte
            assert klass == bpp.Wydawnictwo_Zwarte

            for literka in 'efg':
                assert not zrodlo.get(literka), "co mam z tym zrobic literka %s w %r" % (literka, zrodlo)

            assert not kw.get('informacje'), (kw['informacje'], rec, rec.idt)
            kw['informacje'] = zrodlo['a']
            if zrodlo.get('b'):
                kw['informacje'] += ": " + zrodlo.get('b')

            if zrodlo.get('c'):
                kw['informacje'] += "; " + zrodlo.get("c")

            if zrodlo.get('d'):
                kw['informacje'] += "; " + zrodlo.get('d')

            if kw['informacje']:
                kw['tom'] = parse_informacje(kw['informacje'], "tom")

                # Zwarte NIE ma numeru zeszytu
                # kw['nr_zeszytu'] = parse_informacje(kw['informacje'], "numer")

        elif zrodlo['id'] == 100:
            # Wydawnictwo_Ciagle
            assert klass == bpp.Wydawnictwo_Ciagle
            for literka in 'bcde':
                if literka in zrodlo.keys():
                    raise NotImplementedError("co mam z tym zrobic %r" % zrodlo)

            import pdb;
            pdb.set_trace
            kw['zrodlo'] = dbf.Usi.objects.get(idt_usi=zrodlo['a'][1:]).bpp_id

        elif zrodlo['id'] == 152:
            # Wydawca indeksowany
            assert klass == bpp.Wydawnictwo_Zwarte

            for literka in "ac":
                # w literce "b" może nie byc tekstu
                assert zrodlo.get(literka), "brak tekstu w literce %s zrodlo %r" % (literka, zrodlo)
            for elem in "def":
                assert elem not in zrodlo.keys()

            if zrodlo.get("b"):
                if kw.get("wydawca"):
                    raise NotImplementedError("Juz jest wydawca, prawdopodobnie z tabeli Poz")
                kw['wydawca'] = dbf.Usi.objects.get(idt_usi=zrodlo['b'][1:]).bpp_wydawca_id

            kw['miejsce_i_rok'] = f"{zrodlo['a']} {zrodlo['c']}"
        else:
            raise NotImplementedError(zrodlo)

        if kw['tytul_oryginalny'].find('=') >= 0:

            t1, t2 = [x.strip() for x in kw['tytul_oryginalny'].split("=")]

            if kw.get('tytul'):
                if t2 != kw['tytul']:
                    raise NotImplementedError(
                        "jest tytul_oryginalny %r a jest i tytul %r i sie ROZNIA!" % (
                            kw['tytul_oryginalny'], kw['tytul']))

            kw['tytul_oryginalny'] = t1
            kw['tytul'] = t2

        res = klass.objects.create(**kw)

        rec.object = res
        rec.save()
