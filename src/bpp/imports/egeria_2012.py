# -*- encoding: utf-8 -*-
import os

import xlrd
from bpp.models import Funkcja_Autora, Jednostka, Autor, Autor_Jednostka, Wydzial, Opi_2012_Afiliacja_Do_Wydzialu

ignored_seen, wiecej_niz_jeden, brak_takiego, unseen_jed = set(), set(), set(), set()

def znajdz_lub_zrob_stanowisko(nf):
    try:
        return Funkcja_Autora.objects.get(nazwa=nf)
    except Funkcja_Autora.DoesNotExist:
        try:
            return Funkcja_Autora.objects.create(nazwa=nf, skrot=nf)
        except Exception as e:
            print(e, nf)


def dopasuj_jednostke(nazwa_jednostki, text_mangle):

    nazwa_jednostki = nazwa_jednostki.strip().replace("  ", " ")

    if nazwa_jednostki in text_mangle.zamiany_nazw_jednostek:
        nazwa_jednostki = text_mangle.zamiany_nazw_jednostek[nazwa_jednostki]

    if nazwa_jednostki.endswith('.'):
        nazwa_jednostki = nazwa_jednostki[:-1]

    kw = {'nazwa__icontains': nazwa_jednostki}

    if nazwa_jednostki in text_mangle.single_fitters:
        kw = {'nazwa': nazwa_jednostki}

    if nazwa_jednostki in text_mangle.ignorowane_jednostki:
        if nazwa_jednostki not in ignored_seen:
            ignored_seen.add(nazwa_jednostki)
            # print "... TA JEDNOSTKA ZOSTAJE IGNOROWANA W CALOSCI: ", nazwa_jednostki.encode('utf-8')
        return None

    try:
        return Jednostka.objects.get(**kw)
    except Jednostka.DoesNotExist:
        if nazwa_jednostki not in unseen_jed:
            print("=== BRAK JEDNOSTKI: ", nazwa_jednostki.encode('utf-8'))
            unseen_jed.add(nazwa_jednostki)


def dopasuj_autora(imiona, nazwisko, jednostka, stanowisko):
    a = Autor.objects.filter(imiona__icontains=imiona, nazwisko__icontains=nazwisko)
    cnt = a.count()

    if cnt == 0:
        if (imiona, nazwisko) not in brak_takiego:
            print("--- BRAK TAKIEGO AUTORA W BPP: ", imiona.encode('utf-8'), nazwisko.encode('utf-8'), "Stanowisko:", stanowisko)
            brak_takiego.add((imiona, nazwisko))
        return

    elif cnt > 1:
        # jeżeli jest więcej, niż jeden autor pod takimi danymi, spróbujemy dopasować
        # do niego również jego JEDNOSTKĘ, być może w ten sposób uda nam się wyróżnić
        # unikalnego autora?

        aj = list(Autor_Jednostka.objects.filter(
            autor__imiona__icontains=imiona,
            autor__nazwisko__icontains=nazwisko,
            jednostka__nazwa=jednostka).values('autor').distinct())

        if len(aj) == 1:
            return Autor.objects.get(pk=aj[0]['autor'])

        if (imiona, nazwisko) not in wiecej_niz_jeden:
            print("*** WIĘCEJ NIŻ JEDEN AUTOR W BPP: ", imiona.encode('utf-8'), nazwisko.encode('utf-8'), " MIMO DOPASOWANIA Z JENOSTKĄ!")
            wiecej_niz_jeden.add((imiona, nazwisko))
        return

    else:
        return list(a)[0]



def importuj_wiersz(imiona, nazwisko, nazwa_jednostki, stanowisko, rok, text_mangle):
    # Stanowisko
    funkcja = znajdz_lub_zrob_stanowisko(stanowisko)

    # Poszukujemy jednostki
    jednostka = dopasuj_jednostke(nazwa_jednostki, text_mangle)
    if jednostka is None:
        return

    # Poszukajmy autora:
    autor = dopasuj_autora(imiona, nazwisko, jednostka, funkcja.nazwa)
    if autor is None:
        return

    autor.dodaj_jednostke(jednostka, rok, funkcja)


def importuj_sheet_roczny(sheet, rok, text_mangle):

    labels = [x.value for x in sheet.row(0)]

    for a in range(len(labels)):
        if labels[a] == '':
            labels[a] = str(a)

    for nrow in range(1, sheet.nrows):
        row = sheet.row(nrow)
        dct = dict(list(zip(labels, row)))

        importuj_wiersz(
            dct['PRC IMIE'].value, dct['PRC NAZWISKO'].value,
            dct['OB_NAZWA'].value, dct['Stanowisko'].value,
            rok, text_mangle)


def mangle_labels(labels):
    """Pierwsze 'stanowisko' zostawiamy, następne
    przemianowujemy na stanowisko_2009, potem stanowisko_2010 i tak dalej,
    stopień i wydział również. """
    juz = False
    new_labels = []
    appender = 2008

    fun = lambda element: element
    new_fun = lambda element: element.strip() + "_" + str(appender)

    for element in labels:
        if element.lower() == 'stanowisko':
            if juz:
                fun = new_fun
                appender += 1
            juz = True

        new_labels.append(fun(element))
    return new_labels


def importuj_sheet_osoby_nie_ujete(sheet, text_mangle):
    labels = mangle_labels([x.value for x in sheet.row(2)])

    for nrow in range(3, sheet.nrows):
        row = sheet.row(nrow)
        dct = dict(list(zip(labels, row)))

        # Stanowisko
        funkcja = znajdz_lub_zrob_stanowisko(dct['Stanowisko'].value)

        # Poszukujemy jednostki
        jednostka = dopasuj_jednostke(dct['OB_NAZWA'].value, text_mangle)
        if jednostka is None:
            continue

        # Poszukajmy autora:
        autor = dopasuj_autora(dct['PRC IMIE'].value, dct['PRC NAZWISKO'].value, jednostka, funkcja.nazwa)
        if autor is None:
            continue

        for rok in range(2009, 2013):
            stanowisko = 'stanowisko_%s' % rok
            wydzial = 'Wydział_%s' % rok
            # jest jeszcze stopień

            if dct[stanowisko].value == '#N/D!':
                continue

            wn = dct[wydzial].value
            try:
                wydzial_rok = Wydzial.objects.get(nazwa=wn)
            except Wydzial.DoesNotExist:
                print("BRAK TAKIEGO WYDZIALU:", [
                    str(x).encode('utf-8') for x in (wn, autor, jednostka, rok)])
                continue

            Opi_2012_Afiliacja_Do_Wydzialu.objects.get_or_create(
                autor=autor, wydzial=wydzial_rok, rok=rok)

        autor.dodaj_jednostke(jednostka, rok, funkcja)



def importuj_afiliacje(plik_xls, text_mangle):
    """
    Importuje afiliacje z pliku XLS.

    :param plik_xls: nazwa pliku XLS (pełna ścieżka)
    :param text_mangle: klasa z atrybutami: ignorowane_jednostki,
    single_filters, zamiany_nazw_jednostek
    """
    book = xlrd.open_workbook(plik_xls)

    arkusze_ignorowane = ['razem', '2008']

    for name in book.sheet_names():

        sheet = book.sheet_by_name(name)

        if name in ['2009', '2010', '2011', '2012']:
            importuj_sheet_roczny(sheet, int(name), text_mangle)

        elif name.startswith("osoby"):
            importuj_sheet_osoby_nie_ujete(sheet, text_mangle)

        elif name in arkusze_ignorowane:
            pass

        else:
            raise Exception("Nieznany tytuł arkusza: %r" % name)


def importuj_imiona_sheet(sheet, wydzial):
    labels = ['_id', 'tytul', 'imiona', 'nazwisko', 'afiliacja']

    def zmien_imiona(a, dct):
        i = dct['imiona'].value
        if len(a.imiona) < len(i):
            a.imiona = i
            a.save()

    def poinformuj(ile, dct):
        print("*** DLA AUTORA %s %s JEST %s DOPASOWAN!!!" % tuple([
            str(x).encode('utf-8') for x in [dct['imiona'].value, dct['nazwisko'].value, ile]]))

    for nrow in range(0, sheet.nrows):
        row = sheet.row(nrow)
        dct = dict(list(zip(labels, row)))

        i = dct['imiona'].value.split(" ", 1)[0]

        autor = Autor.objects.filter(imiona__istartswith=i, nazwisko=dct['nazwisko'].value)
        cnt = autor.count()

        if cnt == 1:
            a = autor[0]
            zmien_imiona(a, dct)
            continue

        elif cnt == 0:
            poinformuj(0, dct)

        else:
            # 2 lub więcej -- sprawdź, ilu pasuje pod wydział podany jako parametr
            results = []
            for a in autor:
                if a.afiliacja_na_rok(2012, wydzial, rozszerzona=True):
                    results.append(a)

            if len(results)==1:
                zmien_imiona(results[0], dct)
                continue

            poinformuj(len(results), dct)







def importuj_imiona(plik_xls):
    book = xlrd.open_workbook(plik_xls)
    sheet = book.sheet_by_index(0)
    wydzial = Wydzial.objects.get(
        skrot=os.path.basename(plik_xls).split("-")[0])
    importuj_imiona_sheet(sheet, wydzial)