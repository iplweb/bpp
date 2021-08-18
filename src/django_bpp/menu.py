# -*- encoding: utf-8 -*-

"""
This file was generated with the custommenu management command, it contains
the classes for the admin menu, you can customize this class as you want.

To activate your custom menu add the following to your settings.py::
    ADMIN_TOOLS_MENU = 'django_bpp.menu.CustomMenu'
"""
from admin_tools.menu import Menu, items
from django.apps import apps
from django.db import connection
from django.urls import reverse

from django.contrib import admin

from django.utils.translation import ugettext_lazy as _

from bpp.models.const import GR_WPROWADZANIE_DANYCH

PBN_MENU = [
    ("Instytucje", "/admin/pbn_api/institution"),
    ("Konferencje", "/admin/pbn_api/conference"),
    ("Zrodla", "/admin/pbn_api/journal"),
    ("Wydawcy", "/admin/pbn_api/publisher"),
    ("Naukowcy", "/admin/pbn_api/scientist"),
    ("Publikacje", "/admin/pbn_api/publication"),
    ("Publikacje instytucji", "/admin/pbn_api/publikacjainstytucji"),
    ("Oświadczenia instytucji", "/admin/pbn_api/oswiadczenieinstytucji"),
    ("Przesłane dane", "/admin/pbn_api/sentdata"),
]

IMPORT_DBF_MENU_1 = [
    (
        "Zaimportowana bibliografia",
        "/admin/import_dbf/bib/",
    ),
    (
        "Zaimportowane dane Open Access",
        "/admin/import_dbf/b_u/",
    ),
    (
        "Zaimportowane opisy rekordów",
        "/admin/import_dbf/poz/",
    ),
    (
        "Zaimportowane i zanalizowane opisy rekordów",
        "/admin/import_dbf/bib_desc/",
    ),
    (
        "Zaimportowane źródła",
        "/admin/import_dbf/usi/",
    ),
    (
        "Zaimportowane jednostki",
        "/admin/import_dbf/jed/",
    ),
    (
        "Zaimportowani autorzy",
        "/admin/import_dbf/aut/",
    ),
    (
        "Zaimportowane powiązania autor-rekord",
        "/admin/import_dbf/b_a/",
    ),
    # Tabela sesji - zbędna
    # ('Zaimportowane Ses', '/admin/import_dbf/ses/',),
    (
        "Zaimportowane identyfikatory PBN",
        "/admin/import_dbf/ixn/",
    ),
    (
        "Zaimportowane dyscypliny pracowników",
        "/admin/import_dbf/dys/",
    ),
    (
        "Zaimportowane hasła naukowe",
        "/admin/import_dbf/ixe/",
    ),
    (
        "Zaimportowane charaktery publikacji",
        "/admin/import_dbf/pub/",
    ),
    (
        "Zaimportowana wersja systemu",
        "/admin/import_dbf/sys/",
    ),
    (
        "Zaimportowane wydziały",
        "/admin/import_dbf/wyd/",
    ),
    (
        "Zaimportowane dziedziny",
        "/admin/import_dbf/ldy/",
    ),
    (
        "Zaimportowane języki",
        "/admin/import_dbf/jez/",
    ),
    (
        "Zaimportowane typy KBN",
        "/admin/import_dbf/kbn/",
    ),
    (
        "Zaimportowane bazy",
        "/admin/import_dbf/ixb/",
    ),
    (
        "Zaimportowane listy wydawców",
        "/admin/import_dbf/lis/",
    ),
    (
        "Zaimportowane historia jednostek",
        "/admin/import_dbf/j_h/",
    ),
    (
        "Zaimportowane rekordy KBR",
        "/admin/import_dbf/kbr/",
    ),
    (
        "Zaimportowane Jer",
        "/admin/import_dbf/jer/",
    ),
    (
        "Zaimportowane B_B",
        "/admin/import_dbf/b_b/",
    ),
    (
        "Zaimportowane B_N",
        "/admin/import_dbf/b_n/",
    ),
]

IMPORT_DBF_MENU_2 = [
    (
        "Zaimportowane Wx2",
        "/admin/import_dbf/wx2/",
    ),
    (
        "Zaimportowane Kad",
        "/admin/import_dbf/kad/",
    ),
    (
        "Zaimportowane Loc",
        "/admin/import_dbf/loc/",
    ),
    (
        "Zaimportowane Pbc",
        "/admin/import_dbf/pbc/",
    ),
    (
        "Zaimportowane Sci",
        "/admin/import_dbf/sci/",
    ),
    (
        "Zaimportowane Wsx",
        "/admin/import_dbf/wsx/",
    ),
    (
        "Zaimportowane B_E",
        "/admin/import_dbf/b_e/",
    ),
    (
        "Zaimportowane B_P",
        "/admin/import_dbf/b_p/",
    ),
    (
        "Zaimportowane Ixp",
        "/admin/import_dbf/ixp/",
    ),
    (
        "Zaimportowane Pba",
        "/admin/import_dbf/pba/",
    ),
    (
        "Zaimportowane Pbd",
        "/admin/import_dbf/pbd/",
    ),
    (
        "Zaimportowane Rtf",
        "/admin/import_dbf/rtf/",
    ),
    (
        "Zaimportowane S_B",
        "/admin/import_dbf/s_b/",
    ),
    (
        "Zaimportowane Wsy",
        "/admin/import_dbf/wsy/",
    ),
    (
        "Zaimportowane B_L",
        "/admin/import_dbf/b_l/",
    ),
    (
        "Zaimportowane Ext",
        "/admin/import_dbf/ext/",
    ),
    (
        "Zaimportowane Pbb",
        "/admin/import_dbf/pbb/",
    ),
]

SYSTEM_MENU = [
    ("Charaktery formalne", "/admin/bpp/charakter_formalny/"),
    ("Charakter PBN", "/admin/bpp/charakter_pbn/"),
    ("Dyscypliny naukowe", "/admin/bpp/dyscyplina_naukowa/"),
    ("Formularze - wartości domyślne", "/admin/formdefaults/formrepresentation/"),
    ("Funkcje w jednostce", "/admin/bpp/funkcja_autora/"),
    ("Granty", "/admin/bpp/grant/"),
    ("Grupy pracownicze", "/admin/bpp/grupa_pracownicza/"),
    ("Języki", "/admin/bpp/jezyk/"),
    ("OpenAccess: wydawnictwa ciągłe", "/admin/bpp/tryb_openaccess_wydawnictwo_ciagle"),
    ("OpenAccess: wydawnictwa zwarte", "/admin/bpp/tryb_openaccess_wydawnictwo_zwarte"),
    ("OpenAccess: czas udostępnienia", "/admin/bpp/czas_udostepnienia_openaccess"),
    ("OpenAccess: licencja", "/admin/bpp/licencja_openaccess"),
    ("OpenAccess: wersja tekstu", "/admin/bpp/wersja_tekstu_openaccess"),
    ("Organy przyznające nagrody", "/admin/bpp/organprzyznajacynagrody/"),
    ("Rodzaje źródeł", "/admin/bpp/rodzaj_zrodla/"),
    ("Rodzaje praw patentowych", "/admin/bpp/rodzaj_prawa_patentowego/"),
    ("Statusy korekt", "/admin/bpp/status_korekty/"),
    ("Typy KBN", "/admin/bpp/typ_kbn/"),
    ("Typy odpowiedzialności", "/admin/bpp/typ_odpowiedzialnosci/"),
    ("Tytuły", "/admin/bpp/tytul/"),
    ("Wydawcy", "/admin/bpp/wydawca/"),
    ("Wymiary etatów", "/admin/bpp/wymiar_etatu/"),
    ("Widoczność opcji wyszukiwarki", "/admin/bpp/bppmultiseekvisibility/"),
    ("Zewnętrzne bazy danych", "/admin/bpp/zewnetrzna_baza_danych/"),
    ("Źródło informacji", "/admin/bpp/zrodlo_informacji/"),
]

RAPORTY_MENU = [
    ("Raporty", "/admin/flexible_reports/report/"),
    ("Źródła danych", "/admin/flexible_reports/datasource/"),
    ("Tabele", "/admin/flexible_reports/table/"),
]

WEB_MENU = [
    ("robots.txt - URLe", "/admin/robots/url/"),
    ("robots.txt - reguły", "/admin/robots/rule/"),
    ("Serwisy", "/admin/sites/site/"),
    ("Miniblog", "/admin/miniblog/article/"),
    ("Favicon", "/admin/favicon/"),
]

STRUKTURA_MENU = [
    ("Uczelnie", "/admin/bpp/uczelnia/"),
    ("Wydziały", "/admin/bpp/wydzial/"),
    ("Jednostki", "/admin/bpp/jednostka/"),
]

REDAKTOR_MENU = [
    ("Autorzy", "/admin/bpp/autor/"),
    ("Źródła", "/admin/bpp/zrodlo/"),
    ("Serie wydawnicze", "/admin/bpp/seria_wydawnicza/"),
    ("Konferencje", "/admin/bpp/konferencja/"),
    ("Wydawcy", "/admin/bpp/wydawca/"),
    ("Wydawnictwa ciągłe", "/admin/bpp/wydawnictwo_ciagle/"),
    ("Wydawnictwa zwarte", "/admin/bpp/wydawnictwo_zwarte/"),
    ("Prace doktorskie", "/admin/bpp/praca_doktorska/"),
    ("Prace habilitacyjne", "/admin/bpp/praca_habilitacyjna/"),
    ("Patenty", "/admin/bpp/patent/"),
    ("Powiązania autorów z dyscyplinami", "/admin/bpp/autor_dyscyplina/"),
]

ADMIN_MENU = [
    ("Grupy", "/admin/auth/group/"),
    ("Użytkownicy", "/admin/bpp/bppuser/"),
    ("Formularze wyszukiwania", "/admin/multiseek/searchform/"),
]


def submenu(label, tuples):
    return items.MenuItem(
        label, children=[items.MenuItem(label, link) for label, link in tuples]
    )


class CustomMenu(Menu):
    def __init__(self, **kwargs):
        Menu.__init__(self, **kwargs)

        self.children += [
            items.MenuItem(_("Dashboard"), reverse("admin:index")),
            items.Bookmarks(),
        ]

    def init_with_context(self, context):
        user = context["request"].user
        if not hasattr(user, "__admin_menu_groups"):
            user.__admin_menu_groups = [x.name for x in user.cached_groups]
        groups = user.__admin_menu_groups

        def flt(n1, n2, v):
            if user.is_superuser or n1 in groups:
                self.children += [
                    submenu(n2, v),
                ]

        flt("web", "WWW", WEB_MENU)

        flt("dane systemowe", "PBN API", PBN_MENU)

        if "import_dbf_aut" in connection.introspection.table_names():
            flt("import DBF", "import DBF", IMPORT_DBF_MENU_1)
            # flt("import DBF", "import DBF #2", IMPORT_DBF_MENU_2)
        else:
            # De-register all models from other apps
            for model in apps.get_app_config("import_dbf").models.values():
                if admin.site.is_registered(model):
                    admin.site.unregister(model)

        flt("dane systemowe", "Dane systemowe", SYSTEM_MENU)
        flt("struktura", "Struktura", STRUKTURA_MENU)
        flt(GR_WPROWADZANIE_DANYCH, "Wprowadzanie danych", REDAKTOR_MENU)
        flt("raporty", "Raporty", RAPORTY_MENU)
        flt("administracja", "Administracja", ADMIN_MENU)

        return super(CustomMenu, self).init_with_context(context)
