import os

import progressbar
from dbfread import DBF

from bpp import models as bpp
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

        tytul = tytul.replace(".", ". ").replace("  ", " ").replace("  ", " ").strip()
        try:
            bpp.Tytul.objects.get(skrot=tytul)
        except bpp.Tytul.DoesNotExist:
            bpp.Tytul.objects.create(nazwa=tytul, skrot=tytul)

def integruj_funkcje_autorow():
    for funkcja, in dbf.Aut.objects.all().order_by().values_list("stanowisko").distinct("stanowisko"):
        funkcja = funkcja.strip()
        if not funkcja:
            continue

        funkcja = funkcja.replace(".", ". ").replace("  ", " ").replace("  ", " ").strip()
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
                     progressbar.ETA()]):
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
