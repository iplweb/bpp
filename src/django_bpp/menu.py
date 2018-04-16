# -*- encoding: utf-8 -*-

"""
This file was generated with the custommenu management command, it contains
the classes for the admin menu, you can customize this class as you want.

To activate your custom menu add the following to your settings.py::
    ADMIN_TOOLS_MENU = 'django_bpp.menu.CustomMenu'
"""

from admin_tools.menu import items, Menu
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _

from bpp.models.const import GR_WPROWADZANIE_DANYCH

SYSTEM_MENU = [
    ('Charaktery formalne', '/admin/bpp/charakter_formalny/'),
    ('Charakter PBN', '/admin/bpp/charakter_pbn/'),
    ('Dyscypliny naukowe', '/admin/bpp/dyscyplina_naukowa/'),
    ('Funkcje w jednostce', '/admin/bpp/funkcja_autora/'),
    ('Języki', '/admin/bpp/jezyk/'),

    ('OpenAccess: wydawnictwa ciągłe', '/admin/bpp/tryb_openaccess_wydawnictwo_ciagle'),
    ('OpenAccess: wydawnictwa zwarte', '/admin/bpp/tryb_openaccess_wydawnictwo_zwarte'),
    ('OpenAccess: czas udostępnienia', '/admin/bpp/czas_udostepnienia_openaccess'),
    ('OpenAccess: licencja', '/admin/bpp/licencja_openaccess'),
    ('OpenAccess: wersja tekstu', '/admin/bpp/wersja_tekstu_openaccess'),

    ('Organy przyznające nagrody', '/admin/bpp/organprzyznajacynagrody/'),

    ('Rodzaje źródeł', '/admin/bpp/rodzaj_zrodla/'),
    ('Rodzaje praw patentowych', '/admin/bpp/rodzaj_prawa_patentowego/'),
    ('Statusy korekt', '/admin/bpp/status_korekty/'),
    ('Typy KBN', '/admin/bpp/typ_kbn/'),
    ('Typy odpowiedzialności', '/admin/bpp/typ_odpowiedzialnosci/'),
    ('Tytuły', '/admin/bpp/tytul/'),
    ('Zewnętrzne bazy danych', '/admin/bpp/zewnetrzna_baza_danych/'),
    ('Źródło informacji', '/admin/bpp/zrodlo_informacji/'),

]

RAPORTY_MENU = [
    ('Raporty', '/admin/flexible_reports/report/'),
    ('Źródła danych', '/admin/flexible_reports/datasource/'),
    ('Tabele', '/admin/flexible_reports/table/'),
]

WEB_MENU = [
    ("robots.txt - URLe", "/admin/robots/url/"),
    ("robots.txt - reguły", "/admin/robots/rule/"),
    ("Serwisy", "/admin/sites/site/"),
    ("Miniblog", "/admin/miniblog/article/"),
    ("Favicon", "/admin/favicon/"),
]

STRUKTURA_MENU = [
    ('Uczelnie', '/admin/bpp/uczelnia/'),
    ('Wydziały', '/admin/bpp/wydzial/'),
    ('Jednostki', '/admin/bpp/jednostka/'),
]

REDAKTOR_MENU = [
    ('Autorzy', '/admin/bpp/autor/'),
    ('Źródła', '/admin/bpp/zrodlo/'),
    ('Serie wydawnicze', '/admin/bpp/seria_wydawnicza/'),
    ('Konferencje', '/admin/bpp/konferencja/'),
    ('Wydawnictwa ciągłe', '/admin/bpp/wydawnictwo_ciagle/'),
    ('Wydawnictwa zwarte', '/admin/bpp/wydawnictwo_zwarte/'),
    ('Prace doktorskie', '/admin/bpp/praca_doktorska/'),
    ('Prace habilitacyjne', '/admin/bpp/praca_habilitacyjna/'),
    ('Patenty', '/admin/bpp/patent/'),
]

ADMIN_MENU = [
    ('Grupy', '/admin/auth/group/'),
    ('Użytkownicy', '/admin/bpp/bppuser/'),
    ('Formularze wyszukiwania', '/admin/multiseek/searchform/')

]


def submenu(label, tuples):
    return items.MenuItem(label,
                          children=[
                              items.MenuItem(label, link) for label, link in tuples
                          ]
                          )


class CustomMenu(Menu):
    def __init__(self, **kwargs):
        Menu.__init__(self, **kwargs)

        self.children += [
            items.MenuItem(_('Dashboard'), reverse('admin:index')),
            items.Bookmarks(),
        ]

    def init_with_context(self, context):
        user = context['request'].user
        if not hasattr(user, '__admin_menu_groups'):
            user.__admin_menu_groups = [x.name for x in user.groups.all()]
        groups = user.__admin_menu_groups

        def flt(n1, n2, v):
            if user.is_superuser or n1 in groups:
                self.children += [submenu(n2, v), ]

        flt("web", "WWW", WEB_MENU)
        flt("dane systemowe", "Dane systemowe", SYSTEM_MENU)
        flt("struktura", "Struktura", STRUKTURA_MENU)
        flt(GR_WPROWADZANIE_DANYCH, "Wprowadzanie danych", REDAKTOR_MENU)
        flt("raporty", "Raporty", RAPORTY_MENU)
        flt("administracja", "Administracja", ADMIN_MENU)

        return super(CustomMenu, self).init_with_context(context)
