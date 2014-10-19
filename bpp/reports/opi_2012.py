# -*- encoding: utf-8 -*-

"""Procedury generujace raporty

UWAGA: pierwsza linia __doc__ każdej funkcji używany jest później na front-endzie do opisania danej tabelki
"""
from _csv import QUOTE_MINIMAL
import csv
from datetime import date, datetime
import os
import shutil
import tempfile
from django.core.files.base import File

from django.db.models import Q

from bpp.models import Wydawnictwo_Ciagle, Charakter_Formalny, \
    Wydawnictwo_Zwarte, Jezyk, Typ_KBN, Typ_Odpowiedzialnosci, Wydzial
from bpp.reports import wytnij_numery_stron, \
    wytnij_zbedne_informacje_ze_zrodla, wytnij_tom, slugify, addToRegistry
from celeryui.registry import ReportAdapter
from bpp.util import zrob_cache


def _query(model, atrybut, wartosc):
    return model.objects.get(**{atrybut:wartosc})


def charakter(skrot):
    # Pobieramy charaktery w ten sposób, za pomocą funkcji GET, a nie za
    # pomocą zapytań typu charakter_formalny__skrot__in [...] ponieważ
    # pobierając pojedynczo charakter dla każdego skrótu dostaniemy błąd
    # jeżeli dany skrót nie odzwierciedla charakteru w bazie danych
    return _query(Charakter_Formalny, 'skrot', skrot)


def jezyk(skrot):
    return _query(Jezyk, 'skrot', skrot)


def zrob_daty(rok_min, rok_maks):
    rozpoczal = date(rok_min, 1, 1)
    zakonczyl = date(rok_maks, 12, 31)
    return rozpoczal, zakonczyl


def chce_jeden_wydzial(funkcja, wydzial, rok_min, rok_maks=None):
    if rok_maks is None:
        rok_maks = rok_min

    rozpoczal, zakonczyl = zrob_daty(rok_min, rok_maks)

    args = tuple([Q(
        autorzy__autor_jednostka__zakonczyl_prace__gte=zakonczyl, autorzy__autor_jednostka__rozpoczal_prace__lte=rozpoczal
    ) | Q(
        autorzy__autor_jednostka__rozpoczal_prace__lte=rozpoczal, autorzy__autor_jednostka__zakonczyl_prace=None
    )])

    kw = dict(autorzy__autor_jednostka__jednostka__wydzial=wydzial,
              rok__gte=rok_min,
              rok__lte=rok_maks)

    qs = funkcja().filter(*args, **kw).distinct()
    return qs

def publikacje_z_impactem_wykaz_A():
    """Publikacje w czasopismach naukowych posiadających impact factor i wymienione w części A wykazu MNiSW
    """
    pw = charakter('PW')

    return Wydawnictwo_Ciagle.objects.filter(
        impact_factor__gt=0, punkty_kbn__gt=0,
        ).exclude(charakter_formalny=pw)

def publikacje_erih():
    """Publikacje w czasopismach znajdujących się w bazie EIRH i wymienionych w części C wykazu MNiSW
    """
    charaktery = map(charakter, ['AP', 'API', 'AZ'])
    return Wydawnictwo_Ciagle.objects.filter(
        punkty_kbn__in=[10, 12, 14],
        charakter_formalny__in=charaktery,
        uwagi__icontains='erih'
    )


def publikacje_wykaz_B():
    """Publikacje w czasopismach naukowych wymienionych w części B wykazu MNiSW
    """
    charaktery = map(charakter, ['AP', 'API', 'AZ'])
    return Wydawnictwo_Ciagle.objects.filter(
        punkty_kbn__gt=0, impact_factor=0,
        charakter_formalny__in=charaktery
    ).exclude(jezyk__skrot='b/d')


def publikacje_wos():
    """Publikacje w recenzowanych materiałach z konferencji międzynarodowych uwzględnionych w Web of Science
    """
    charaktery = map(charakter, ['ZRZ', 'PRI', 'PRZ'])
    return Wydawnictwo_Zwarte.objects.filter(
        charakter_formalny__in=charaktery,
        uwagi__icontains='wos'
    )


def tylko_autorzy(qs):
    # To ostatnie jest konieczne, bo na ten moment Django próbuje
    # dołożyć do tego nowy INNER JOIN dla tabeli bpp_wydawnictwo_zwarte_autor
    # i wychodzi z tego zapytania kiszka, więc zapytamy przez EXTRA:
    to = Typ_Odpowiedzialnosci.objects.get(skrot='aut.')

    return qs.extra(
        where=[
            'bpp_wydawnictwo_zwarte_autor.typ_odpowiedzialnosci_id=%s' % to.pk,
            'bpp_wydawnictwo_zwarte_autor.rekord_id=bpp_wydawnictwo_zwarte.id'],
        tables=['bpp_wydawnictwo_zwarte_autor'])

def monografie_w_jezykach():
    """Monografie naukowe w językach: angielskim, niemieckim, francuskim, hiszpańskim, rosyjskim lub włoskim
    """
    jez = map(jezyk, ['ang.', 'niem.', 'fr.', 'hiszp.', 'ros.', 'wł.'])

    return tylko_autorzy(Wydawnictwo_Zwarte.objects.filter(
        liczba_znakow_wydawniczych__gt=0, jezyk__in=jez,
        charakter_formalny=charakter('KSZ'),
    ).exclude(typ_kbn=Typ_KBN.objects.get(skrot='PAK')))


def monografie_po_polsku():
    """Monografie w języku polskim
    """
    return tylko_autorzy(Wydawnictwo_Zwarte.objects.filter(
        liczba_znakow_wydawniczych__gt=0,
        charakter_formalny=charakter('KSP')
    ).exclude(typ_kbn=Typ_KBN.objects.get(skrot='PAK')))


def monografie_w_innym_jezyku():
    """Monografie w innym języku
    """
    jez = map(jezyk, ['ang.', 'niem.', 'fr.', 'hiszp.', 'ros.', 'wł.', 'pol.', 'b/d'])

    return tylko_autorzy(Wydawnictwo_Zwarte.objects.filter(
        liczba_znakow_wydawniczych__gt=0,
        charakter_formalny=charakter('KSZ')
    ).exclude(jezyk__in=jez).exclude(typ_kbn=Typ_KBN.objects.get(skrot='PAK')))


def monografie_wieloautorskie():
    """Monografie wieloautorskie, w których zamieszczono rozdziały podane w punktach 3.2 d)-f)
    """
    return Wydawnictwo_Zwarte.objects.filter(
        charakter_formalny=charakter('ROZ'),
        liczba_znakow_wydawniczych__gt=0
    )


def rozdzialy_w_monografiach_w_jezykach():
    """Rozdziały w monografiach naukowych w językach: angielskim, niemieckim, francuskim, hiszpańskim, rosyjskim lub włoskim
    """
    jez = map(jezyk, ['ang.', 'niem.', 'fr.', 'hiszp.', 'ros.', 'wł.'])
    return Wydawnictwo_Zwarte.objects.filter(
        charakter_formalny=charakter('ROZ'),
        liczba_znakow_wydawniczych__gt=0,
        jezyk__in=jez
    )


def rozdzialy_w_monografiach_po_polsku():
    """Rozdziały w monografiach naukowych w języku polskim
    """
    return Wydawnictwo_Zwarte.objects.filter(
        charakter_formalny=charakter('ROZ'),
        liczba_znakow_wydawniczych__gt=0,
        jezyk=jezyk('pol.')
    )


def rozdzialy_w_monografiach_w_innym_jezyku():
    """Rozdziały w monografiach naukowych w języku innym, niż: angielski, niemiecki, francuski, hiszpański, rosyjski, włoski lub polski
    """
    jez = map(jezyk, ['ang.', 'niem.', 'fr.', 'hiszp.', 'ros.', 'wł.', 'pol.', 'b/d'])
    return Wydawnictwo_Zwarte.objects.filter(
        charakter_formalny=charakter('ROZ'),
        liczba_znakow_wydawniczych__gt=0,
    ).exclude(jezyk__in=jez)


def autorzy_z_wydzialu(pub, rok, wydzial):
    from bpp.models.opi_2012 import Opi_2012_Afiliacja_Do_Wydzialu
    z_wydzialu = []
    spoza_wydzialu = []
    for autor in pub.autorzy.all():

        afiliacja_na_rok = False
        try:
            Opi_2012_Afiliacja_Do_Wydzialu.objects.get(
                autor=autor, rok=rok, wydzial=wydzial)
            afiliacja_na_rok = True
        except Opi_2012_Afiliacja_Do_Wydzialu.DoesNotExist:
            afiliacja_na_rok = autor.afiliacja_na_rok(rok, wydzial)

        if afiliacja_na_rok is True:
            z_wydzialu.append(autor)
        else:
            spoza_wydzialu.append(autor)
    return z_wydzialu, spoza_wydzialu

DR = 'dr'
DR_HAB = 'dr hab.'
PROF_DR_HAB = 'prof. dr hab.'
MGR = 'mgr'
LEK = 'lek.'

TRANSLACJE_TYTULOW = {
    'testTytul': 'Dr',
    'mgr. inż.': MGR,
    'dr n. fiz.': DR,
    'dr n. hum.': DR,
    'dr n. wet.': DR,
    'lek. wet.': LEK,
    'prof. dr hab. przyr.': PROF_DR_HAB,
    'dr n. przyr.': DR,
    'lek. med.': LEK,
    'lek. dent.': LEK,
    'lek.': LEK,
    'mgr położ.': MGR,
    'mgr piel.': MGR,
    'mgr': MGR,
    'prof. dr hab. n. farm.': PROF_DR_HAB,
    'dr hab. n. farm.': DR_HAB,
    'dr n. farm.': DR,
    'prof. dr hab. med.': PROF_DR_HAB,
    'prof.': PROF_DR_HAB,
    'dr hab. med.': DR_HAB,
    'dr hab.': DR_HAB,
    'dr n. med.': DR,
    'dr': DR,}


def formatuj_autorow(aut, afiliacja):

    def autor(aut):
        ret = u""
        if aut.tytul is not None:
            ret = TRANSLACJE_TYTULOW.get(aut.tytul.skrot, aut.tytul.skrot)

        i1 = aut.imiona
        i2 = ''

        if i1.find(" ") > 0:
            i1, i2 = i1.split(" ", 1)

        def repl(s):
            return s.replace("$", "_").replace("#", "_")

        return ret + "$%s$%s$%s$%s" % (
            repl(aut.nazwisko), repl(i1), repl(i2), afiliacja)

    return u"#".join([autor(x) for x in aut])


def dopisz_autorow(pub, rok, row, wydzial, rowniez_spoza_wydzialu=True):
    z_wydzialu, spoza_wydzialu = autorzy_z_wydzialu(pub, rok, wydzial)
    row.append(formatuj_autorow(z_wydzialu, 'tak'))
    if rowniez_spoza_wydzialu:
        row.append(len(spoza_wydzialu))
        row.append(formatuj_autorow(spoza_wydzialu, 'nie'))


def znaki_wydawnicze(liczba_znakow_wydawniczych):
    """Zwraca objętość pracy w arkuszach wydawniczych (czyli ilość znaków wydawniczych / 40000),
        oraz używa jako separatora PRZECINKA, a nie kropki.
        """

    i = u'0,00'
    if liczba_znakow_wydawniczych is not None:
        i = u"%.2f" % (liczba_znakow_wydawniczych / 40000.0)
        i = i.replace(".", ",")
    return i


def wiersze_publikacji(funkcja, wydzial, rok_min, rok_maks=None):
    """
    Produkuje wiersze z danymi (do tabelki)

    :param wydzial: wydział, dla którego generujemy wiersze
    :param rok:
    :param funkcja: wybierz jedną z powyższych funkcji do wygnerowania prac
    """

    for pub in chce_jeden_wydzial(funkcja, wydzial, rok_min, rok_maks):
        row = []
        #row.append(pub.issn or (pub.zrodlo.issn or u''))

        row.append(pub.zrodlo.nazwa)
        row.append(pub.tytul_oryginalny)

        dopisz_autorow(pub, pub.rok, row, wydzial)

        row.append(pub.rok)
        row.append(wytnij_tom(pub.informacje) or u'')
        row.append(wytnij_numery_stron(pub.szczegoly) or u'')
        row.append(unicode(pub.jezyk))

        yield row


def wiersze_monografii(funkcja, wydzial, rok_min, rok_maks=None):
    """
    Produkuje wiersze z danymi (do tabelki) dla monografii

    :param wydzial: wydział, dla którego generujemy wiersze
    :param rok:
    :param funkcja: wybierz jedną z powyższych funkcji do wygnerowania prac
    """

    for pub in chce_jeden_wydzial(funkcja, wydzial, rok_min, rok_maks):
        row = [pub.wydawnictwo, pub.tytul_oryginalny]
        dopisz_autorow(pub, pub.rok, row, wydzial)
        row.append(unicode(pub.jezyk))
        row.append(pub.rok)
        row.append(pub.isbn or u'')
        row.append(znaki_wydawnicze(pub.liczba_znakow_wydawniczych))
        yield row


def wiersze_wos(funkcja, wydzial, rok_min, rok_maks=None):
    for pub in chce_jeden_wydzial(funkcja, wydzial, rok_min, rok_maks=None):
        informacje = pub.informacje
        if informacje.startswith("W: "):
            informacje = informacje[3:]

        row = [informacje, pub.tytul_oryginalny]
        dopisz_autorow(pub, pub.rok, row, wydzial)
        row.append(unicode(pub.rok))
        row.append(u'')
        row.append(wytnij_numery_stron(pub.szczegoly) or u'')
        row.append(unicode(pub.jezyk))
        row.append(znaki_wydawnicze(pub.liczba_znakow_wydawniczych))
        yield row


def wiersze_rozdzialu(funkcja, wydzial, rok_min, rok_maks=None):
    for pub in chce_jeden_wydzial(funkcja, wydzial, rok_min, rok_maks):

        tytul_zrodla = wytnij_zbedne_informacje_ze_zrodla(pub.informacje)
        zrodlo = zlokalizuj_publikacje_nadrzedna(pub.informacje, pub.rok)
        if zrodlo is not None:
            tytul_zrodla = zrodlo.tytul_oryginalny

        row = [tytul_zrodla, pub.tytul_oryginalny]
        dopisz_autorow(pub, pub.rok, row, wydzial)
        row.append(unicode(pub.jezyk))
        row.append(znaki_wydawnicze(pub.liczba_znakow_wydawniczych))
        yield row

def zlokalizuj_publikacje_nadrzedna(informacje, rok):
    """Z pola źródło-informacje, gdzie jest zapis w formacie

        W: Praca. Pod. red. Jan Kowalski.

    znajdź 'prawdziwą' publikację w bazie danych.

    Ta procedura używana jest do wygenerowania raportów OPI 2012 z danych
    na 'starej bazie' oraz będzie użyta jednorazowo do zaimportowania rekordów
    do nowej bazy i poustalania im prac nadrzędnych. """

    from bpp.models.opi_2012 import Opi_2012_Tytul_Cache

    informacje = wytnij_zbedne_informacje_ze_zrodla(informacje)

    try:
        return Wydawnictwo_Zwarte.objects.get(tytul_oryginalny=informacje)
    except Wydawnictwo_Zwarte.MultipleObjectsReturned:
        try:
            return Wydawnictwo_Zwarte.objects.get(
                ~Q(charakter_formalny__skrot='ROZ'),
                tytul_oryginalny=informacje, rok=rok)
        except Wydawnictwo_Zwarte.DoesNotExist:
            raise Exception("FUBAR")
        except Wydawnictwo_Zwarte.MultipleObjectsReturned:
            print "WIELE PUBLIKACJI DLA TYTULU %r" % z
            return

    except Wydawnictwo_Zwarte.DoesNotExist:
        try:
            return Wydawnictwo_Zwarte.objects.get(tytul_oryginalny=informacje[:-1])
        except Wydawnictwo_Zwarte.DoesNotExist:
            # Poszukamy po CACHE:
            try:
                tc = Opi_2012_Tytul_Cache.objects.get(
                    tytul_oryginalny_cache__icontains=zrob_cache(informacje))
            except Opi_2012_Tytul_Cache.MultipleObjectsReturned:
                try:
                    tc = Opi_2012_Tytul_Cache.objects.get(
                        tytul_oryginalny_cache=zrob_cache(informacje))
                except Opi_2012_Tytul_Cache.DoesNotExist:
                    print "BRAK Publikacji o tytule %r" % informacje
                    return

            except Opi_2012_Tytul_Cache.DoesNotExist:
                print "BRAK PUBLIKACJ O TYTULE %r" % informacje
                return

            return tc.wydawnictwo_zwarte


def wiersze_wieloautorskie(funkcja, wydzial, rok_min, rok_maks=None):
    widziane = set()

    for pub in chce_jeden_wydzial(funkcja, wydzial, rok_min, rok_maks):
        if pub.informacje in widziane:
            continue
        widziane.add(pub.informacje)

        pub2 = zlokalizuj_publikacje_nadrzedna(pub.informacje, pub.rok)
        if pub2 is None:
            yield [u'', wytnij_zbedne_informacje_ze_zrodla(pub.informacje),
                   u'', u'', u'', u'', u'']
            continue

        row = [pub2.wydawnictwo, pub2.tytul_oryginalny]
        dopisz_autorow(pub2, pub2.rok, row, wydzial, rowniez_spoza_wydzialu=False)
        row.append(pub2.rok)
        row.append(pub2.isbn)
        row.append(znaki_wydawnicze(pub2.liczba_znakow_wydawniczych))
        row.append(unicode(pub2.jezyk))
        yield row

RAPORTY = [publikacje_z_impactem_wykaz_A,
           publikacje_erih,
           publikacje_wykaz_B,
           publikacje_wos,

           monografie_w_jezykach,
           monografie_po_polsku,
           monografie_w_innym_jezyku,
           monografie_wieloautorskie,

           rozdzialy_w_monografiach_w_jezykach,
           rozdzialy_w_monografiach_po_polsku,
           rozdzialy_w_monografiach_w_innym_jezyku]


def wez_funkcje_tabelki(nazwa_raportu):

    if nazwa_raportu == "publikacje_wos":
        return wiersze_wos

    elif nazwa_raportu == "monografie_wieloautorskie":
        return wiersze_wieloautorskie

    elif "publikacje" in nazwa_raportu:
        return wiersze_publikacji

    elif "rozdzia" in nazwa_raportu:
        return wiersze_rozdzialu

    elif "monograf" in nazwa_raportu:
        return wiersze_monografii

    else:
        raise Exception("Nieznana nazwa raportu: %r" % nazwa_raportu)


class opi:
    delimiter = ';'
    quotechar = '"'
    escapechar = None
    doublequote = True
    skipinitialspace = False
    lineterminator = '\n'
    quoting = QUOTE_MINIMAL

csv.register_dialect('opi', opi)


def make_report_zipfile(wydzialy, rok_min=2009, rok_maks=2012):
    katalog = tempfile.mkdtemp("-BPP")
    current_dir = os.getcwd()
    zipname = None
    ret_path = None

    try:

        for wydzial_skrot in wydzialy:

            sciezka = os.path.join(katalog, wydzial_skrot)
            os.mkdir(sciezka)

            wydzial = Wydzial.objects.get(skrot=wydzial_skrot)

            for no, raport in enumerate(RAPORTY):

                nazwa_raportu = raport.__name__

                nazwa_pliku_raportu = "%i_%s" % (no+1, nazwa_raportu)
                nazwa_pliku_raportu = nazwa_pliku_raportu .replace(" ", "_")

                fn1 = os.path.join(sciezka, nazwa_pliku_raportu + ".txt")
                fn2 = os.path.join(sciezka, nazwa_pliku_raportu + ".utf8.txt")

                f1 = open(fn1, 'wb')
                f2 = open(fn2, 'wb')

                o1 = csv.writer(f1, dialect='opi')
                o2 = csv.writer(f2, dialect='opi')

                funkcja_tabelki = wez_funkcje_tabelki(nazwa_raportu)

                for row in funkcja_tabelki(raport, wydzial, rok_min, rok_maks):

                    o1.writerow([
                        unicode(x).encode('cp1250', 'replace').replace("\r\n", " ")
                        .replace("\n", " ").replace("  ", " ").replace("  ", " ").replace(";", ",")
                        for x in row])

                    o2.writerow([
                        unicode(x).encode('utf-8').replace("\r\n", " ")
                        .replace("\n", " ").replace("  ", " ").replace("  ", " ").replace(";", ",")
                        for x in row])

                f1.close()
                f2.close()
                #break

        # Zzipuj wszystko
        os.chdir(katalog)
        zipname = "raporty_OPI_%s.zip" % datetime.now().date()
        os.system("zip -r %s ." % zipname)

        # Utwórz nowy katalog temp na plik zip
        katalog_zip = tempfile.mkdtemp("-BPP-ZIP")
        shutil.move(zipname, katalog_zip)
        ret_path = os.path.abspath(os.path.join(katalog_zip, zipname))

        return ret_path

    finally:
        try:
            shutil.rmtree(katalog)
        except (WindowsError, IOError):
            pass
        os.chdir(current_dir)
        pass


class Raport_OPI_2012(ReportAdapter):
    slug = "raport-opi-2012"

    def _get_title(self):
        args = self.original.arguments
        wydzialy = args['wydzial']
        rok_min = args['od_roku']
        rok_maks = args['do_roku']

        opis_wydzialy = []

        for wydzial in wydzialy:
            try:
                w = unicode(Wydzial.objects.get(pk=wydzial))
            except Wydzial.DoesNotExist:
                w = u'(wydział usunięty)'
            opis_wydzialy.append(w)

        if rok_min == rok_maks:
            rok = "rok %s" % rok_min
        else:
            rok = "lata %s-%s" % (rok_min, rok_maks)

        return u"Raport OPI 2012 dla %s, %s" % (u", ".join(opis_wydzialy), rok)

    title = property(_get_title)

    def perform(self):
        report = self.original
        zipname = make_report_zipfile(
            wydzialy=[Wydzial.objects.get(pk=x).skrot
                      for x in self.original.arguments['wydzial']],
            rok_min=int(self.original.arguments['od_roku']),
            rok_maks=int(self.original.arguments['do_roku'])
        )
        self.original.file.save(
            zipname, File(open(zipname, 'rb'), zipname))

addToRegistry(Raport_OPI_2012)