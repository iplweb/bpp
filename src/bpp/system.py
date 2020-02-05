# -*- encoding: utf-8 -*-

"""Ustawienia systemowe

groups - lista grup wraz z uprawnieniami do edycji poszczególnych obiektów.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db import transaction
from favicon.models import Favicon, FaviconImg
from flexible_reports import models as flexible_models
from multiseek.models import SearchForm
from robots.models import Rule, Url

from bpp.models import Funkcja_Autora, Zrodlo_Informacji, Jezyk, \
    Rodzaj_Zrodla, Status_Korekty, Tytul, Typ_KBN, Uczelnia, Wydzial, \
    Jednostka, Zrodlo, Autor, Autor_Jednostka, \
    Charakter_Formalny, \
    Typ_Odpowiedzialnosci, \
    Wydawnictwo_Ciagle, Wydawnictwo_Zwarte, Punktacja_Zrodla, \
    Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor, \
    Redakcja_Zrodla, Praca_Doktorska, Praca_Habilitacyjna, Patent, Patent_Autor, \
    Rodzaj_Prawa_Patentowego, Dyscyplina_Naukowa, Zewnetrzna_Baza_Danych, Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych, \
    Autor_Dyscyplina, Wydawnictwo_Zwarte_Zewnetrzna_Baza_Danych
from bpp.models.const import GR_WPROWADZANIE_DANYCH
from bpp.models.konferencja import Konferencja
from bpp.models.nagroda import OrganPrzyznajacyNagrody, Nagroda
from bpp.models.openaccess import Tryb_OpenAccess_Wydawnictwo_Ciagle, Tryb_OpenAccess_Wydawnictwo_Zwarte, \
    Czas_Udostepnienia_OpenAccess, Licencja_OpenAccess, Wersja_Tekstu_OpenAccess
from bpp.models.praca_habilitacyjna import Publikacja_Habilitacyjna
from bpp.models.profile import BppUser
from bpp.models.seria_wydawnicza import Seria_Wydawnicza
from bpp.models.struktura import Jednostka_Wydzial
from bpp.models.system import Charakter_PBN
from bpp.models.wydawca import Wydawca, Poziom_Wydawcy
from import_dbf.models import Bib, B_A, Aut, Jed, Poz, B_U, Usi, Ses, Wx2, Ixn
from miniblog.models import Article

User = get_user_model()

groups = {
    'import DBF': [
        Bib, B_A, Aut, Jed, Poz, B_U, Usi, Ses, Wx2, Ixn
    ],
    'dane systemowe': [
        Charakter_Formalny, Charakter_PBN,
        Funkcja_Autora, Zrodlo_Informacji,
        Jezyk, Typ_Odpowiedzialnosci, Rodzaj_Zrodla, Status_Korekty,
        Tytul, Typ_KBN,
        Tryb_OpenAccess_Wydawnictwo_Ciagle,
        Tryb_OpenAccess_Wydawnictwo_Zwarte,
        Czas_Udostepnienia_OpenAccess,
        Licencja_OpenAccess,
        Wersja_Tekstu_OpenAccess,
        OrganPrzyznajacyNagrody,
        Rodzaj_Prawa_Patentowego,
        Dyscyplina_Naukowa,
        Zewnetrzna_Baza_Danych, 
        Wydawca, Poziom_Wydawcy
    ],
    'struktura': [Uczelnia, Wydzial, Jednostka, Jednostka_Wydzial],
    GR_WPROWADZANIE_DANYCH: [
        Zrodlo, Autor, Autor_Dyscyplina, Wydawnictwo_Ciagle, Wydawnictwo_Zwarte,
        Punktacja_Zrodla, Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte_Autor, Autor_Jednostka, Redakcja_Zrodla,
        Praca_Doktorska, Praca_Habilitacyjna, Patent, Patent_Autor,
        Publikacja_Habilitacyjna, Konferencja, Seria_Wydawnicza,
        Nagroda, Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych,
        Wydawnictwo_Zwarte_Zewnetrzna_Baza_Danych],
    'indeks autorów': [Autor, Autor_Jednostka],
    'administracja': [User, Group, SearchForm],
    'web': [Url, Rule, Site, Favicon, FaviconImg, Article],
    'raporty': [
        flexible_models.Report,
        flexible_models.ReportElement,
        flexible_models.Table,
        flexible_models.Column,
        flexible_models.Datasource,
        flexible_models.ColumnOrder]
}

# -*- charmap -*- -*- charmap -*--*- charmap -*--*- charmap -*--*- charmap -*-

greek = ['391', '3b1', '392', '3b2', '393', '3b3', '394', '3b4', '395', '3b5',
         '396', '3b6', '397', '3b7', '398', '3b8', '399', '3b9', '39a', '3ba',
         '39b', '3bb', '39c', '3bc', '39d', '3bd', '39e', '3be', '39f', '3bf',
         '3a0', '3c0', '3a1', '3c1', '3a3', '3c3', '3a4', '3c4', '3a5', '3c5',
         '3a6', '3c6', '3a7', '3c7', '3a8', '3c8', '3a9', '3c9', '1fb9', '1fb1',
         '1fd9', '1fd1', '1fe9', '1fe1', '386', '3ac', '388', '3ad', '389',
         '3ae', '38a', '3af', '38c', '3cc', '38e', '3cd', '38f', '3ce', '3aa',
         '3ca', '3ab', '3cb', '1f08', '1f00', '1f18', '1f10', '1f28', '1f20',
         '1f38', '1f30', '1f48', '1f40', '1fe4', '1f50', '1f68', '1f60', '1f09',
         '1f01', '1f19', '1f11', '1f29', '1f21', '1f39', '1f31', '1f49', '1f41',
         '1fec', '1fe5', '1f59', '1f51', '1f69', '1f61', '1f0a', '1f02', '1f1a',
         '1f12', '1f2a', '1f22', '1f3a', '1f32', '1f4a', '1f42', '1f52', '1f6a',
         '1f62', '1f0b', '1f03', '1f1b', '1f13', '1f2b', '1f23', '1f3b', '1f33',
         '1f4b', '1f43', '1f5b', '1f53', '1f6b', '1f63', '1f0c', '1f04', '1f1c',
         '1f14', '1f2c', '1f24', '1f3c', '1f34', '1f4c', '1f44', '1f54', '1f6c',
         '1f64', '1f0d', '1f05', '1f1d', '1f15', '1f2d', '1f25', '1f3d', '1f35',
         '1f4d', '1f45', '1f5d', '1f55', '1f6d', '1f65', '1f0e', '1f06', '1f2e',
         '1f26', '1f3e', '1f36', '1f56', '1f6e', '1f66', '1f0f', '1f07', '1f2f',
         '1f27', '1f3f', '1f37', '1f5f', '1f57', '1f6f', '1f67', '1fb8', '1fb0',
         '1fd8', '1fd0', '1fe8', '1fe0', '1fbc', '1fcc', '1ffc', '1fb6', '1fc6',
         '1fd6', '1fe6', '1ff6']

cyrylic = ['410', '430', '411', '431', '412', '432', '413', '433', '403', '453',
           '412', '432', '414', '434', '402', '452', '405', '455', '40f', '45f',
           '415', '435', '404', '454', '416', '436', '417', '437', '418', '438',
           '419', '439', '406', '456', '41a', '43a', '4a0', '4a1', '40c', '45c',
           '480', '481', '41b', '43b', '409', '459', '41c', '43c', '41d', '43d',
           '40a', '45a', '41e', '43e', '4e8', '4e9', '41f', '43f', '420', '440',
           '421', '441', '422', '442', '426', '446', '40b', '45b', '423', '443',
           '40e', '45e', '4ae', '4af', '478', '479', '424', '444', '425', '445',
           '426', '446', '427', '447', '4cb', '4cc', '428', '448', '429', '449',
           '4ba', '4bb', '42a', '44a', '42b', '44b', '42d', '44d', '42e', '44e',
           '42f', '44f', '472', '473', '401', '451', '408', '458', '46a', '46b',
           '466', '467', '460', '461', '47a', '47b', '47e', '47f', '470', '471',
           '4d8', '4d9', '4c3', '4c4', '4c7', '4c8', '4d2', '4d3', '4dc', '4dd',
           '4de', '4df', '4e4', '4e5', '4e6', '4e7', '4ea', '4eb', '4f0', '4f1',
           '4f4', '4f5', '4f8', '4f9', '4ec', '4ed', '4da', '4db', '492', '493',
           '49e', '49f', '4b0', '4b1', '4e2', '4e3', '4ee', '4ef', '400', '450',
           '40d', '45d', '4d0', '4d1', '4d6', '4d7', '4c1', '4c2', '4f2', '4f3',
           '496', '497', '498', '499', '49a', '49b', '4a2', '4a3', '4aa', '4ab',
           '4ac', '4ad', '4b2', '4b3', '4b6', '4b7', '47c', '47d', '48e', '48f',
           '490', '491', '49c', '49d', '4b8', '4b9', '494', '495', '4a6', '4a7',
           '4e8', '4e9']

iso = ['00A0', '0104', '02D8', '0141', '00A4', '013D', '015A', '00A7', '00A8', '0160', '015E', '0164',
       '0179', '00AD', '017D', '017B', '00B0', '0105', '02DB', '0142', '00B4', '013E', '015B', '02C7',
       '00B8', '0161', '015F', '0165', '017A', '02DD', '017E', '017C', '0154', '00C1', '00C2', '0102',
       '00C4', '0139', '0106', '00C7', '010C', '00C9', '00C8', '0118', '00CB', '011A', '00CD', '00CE', '010E',
       '0110', '0143', '0147', '00D3', '00D4', '0150', '00D6', '00D7', '0158', '016E', '00DA', '0170',
       '00DC', '00DD', '0162', '00DF', '0155', '00E1', '00E2', '0103', '00E4', '013A', '0107', '00E7',
       '010D', '00E9', '00E8', '0119', '00EB', '011B', '00ED', '00EE', '010F', '0111', '0144', '0148', '00F3',
       '00F4', '0151', '00F6', '00F7', '0159', '016F', '00FA', '0171', '00FC', '00FD', '0163', '02D9']

# Po migracji, upewnij się że robots.txt są generowane poprawnie

DISALLOW_URLS = [
    "/multiseek/",
    "/bpp/raporty/",
    "/eksport_pbn/",
    "/admin/",
    "/integrator2/",
    "/password_change/",
]


def ustaw_robots_txt(**kwargs):
    urls = set()
    for elem in DISALLOW_URLS:
        url, _ignore = Url.objects.get_or_create(pattern=elem)
        urls.add(url)

    cnt = Site.objects.all().count()
    if cnt != 1:
        raise Exception("Not supported count=%i" % cnt)

    r, _ignore = Rule.objects.get_or_create(robot="*")
    r.sites.add(Site.objects.all()[0])
    for elem in DISALLOW_URLS:
        r.disallowed.add(Url.objects.get(pattern=elem))
    r.save()


@transaction.atomic
def odtworz_grupy(**kwargs):
    grp_dict = {}
    for u in BppUser.objects.all():
        grp_dict[u] = [grp.name for grp in u.groups.all()]

    for name, models in list(groups.items()):
        try:
            Group.objects.get(name=name).delete()
        except Group.DoesNotExist:
            pass

        g = Group.objects.create(name=name)
        for model in models:
            content_type = ContentType.objects.get_for_model(model)
            for permission in Permission.objects.filter(
                    content_type=content_type):
                g.permissions.add(permission)

    for u, grps in list(grp_dict.items()):
        for gname in grps:
            u.groups.add(Group.objects.get(name=gname))
