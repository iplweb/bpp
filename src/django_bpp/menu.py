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

SYSTEM_MENU = [
    (u'Charaktery formalne', '/admin/bpp/charakter_formalny/'),
    (u'Funkcje w jednostce', '/admin/bpp/funkcja_autora/'),
    (u'Języki', '/admin/bpp/jezyk/'),

    (u'OpenAccess: wydawnictwa ciągłe', '/admin/bpp/tryb_openaccess_wydawnictwo_ciagle'),
    (u'OpenAccess: wydawnictwa zwarte', '/admin/bpp/tryb_openaccess_wydawnictwo_ciagle'),
    (u'OpenAccess: czas udostępnienia', '/admin/bpp/czas_udostepnienia_openaccess'),
    (u'OpenAccess: licencja', '/admin/bpp/licencja_openaccess'),
    (u'OpenAccess: wersja tekstu', '/admin/bpp/wersja_tekstu_openaccess'),

    (u'Rodzaje źródeł', '/admin/bpp/rodzaj_zrodla/'),
    (u'Statusy korekt', '/admin/bpp/status_korekty/'),
    (u'Typy KBN', '/admin/bpp/typ_kbn/'),
    (u'Typy odpowiedzialności', '/admin/bpp/typ_odpowiedzialnosci/'),
    (u'Tytuły', '/admin/bpp/tytul/'),
    (u'Źródło informacji', '/admin/bpp/zrodlo_informacji/'),

]

WEB_MENU = [
    (u"robots.txt - URLe", "/admin/robots/url/"),
    (u"robots.txt - reguły", "/admin/robots/rule/"),
    (u"Strony", "/admin/sites/site/"),
]

STRUKTURA_MENU = [
    (u'Uczelnie', '/admin/bpp/uczelnia/'),
    (u'Wydziały', '/admin/bpp/wydzial/'),
    (u'Jednostki', '/admin/bpp/jednostka/'),
]

REDAKTOR_MENU = [
    (u'Autorzy', '/admin/bpp/autor/'),
    (u'Źródła', '/admin/bpp/zrodlo/'),
    (u'Wydawnictwa ciągłe', '/admin/bpp/wydawnictwo_ciagle/'),
    (u'Wydawnictwa zwarte', '/admin/bpp/wydawnictwo_zwarte/'),
    (u'Prace doktorskie', '/admin/bpp/praca_doktorska/'),
    (u'Prace habilitacyjne', '/admin/bpp/praca_habilitacyjna/'),
    (u'Patenty', '/admin/bpp/patent/'),
]

ADMIN_MENU = [
    (u'Grupy', '/admin/auth/group/'),
    (u'Użytkownicy', '/admin/bpp/bppuser/'),
    (u'Formularze wyszukiwania', '/admin/multiseek/searchform/')

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

        flt("web", "Web", WEB_MENU)
        flt("dane systemowe", "Dane systemowe", SYSTEM_MENU)
        flt("struktura", "Struktura", STRUKTURA_MENU)
        flt("wprowadzanie danych", "Wprowadzanie danych", REDAKTOR_MENU)
        flt("administracja", "Administracja", ADMIN_MENU)

        return super(CustomMenu, self).init_with_context(context)
