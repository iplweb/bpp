"""
This file was generated with the custommenu management command, it contains
the classes for the admin menu, you can customize this class as you want.

To activate your custom menu add the following to your settings.py::
    ADMIN_TOOLS_MENU = 'django_bpp.menu.CustomMenu'
"""
from admin_tools.menu import Menu, items
from django.urls import reverse

from django.utils.translation import gettext_lazy as _

from bpp.const import GR_WPROWADZANIE_DANYCH, GR_ZGLOSZENIA_PUBLIKACJI

PBN_MENU = [
    ("Instytucje", "/admin/pbn_api/institution"),
    ("Konferencje", "/admin/pbn_api/conference"),
    ("Zrodla", "/admin/pbn_api/journal"),
    ("Wydawcy", "/admin/pbn_api/publisher"),
    ("Naukowcy", "/admin/pbn_api/scientist"),
    ("Publikacje", "/admin/pbn_api/publication"),
    ("Słowniki dyscyplin", "/admin/pbn_api/disciplinegroup"),
    ("Dyscypliny", "/admin/pbn_api/discipline"),
    ("Tłumacz dyscyplin", "/admin/pbn_api/tlumaczdyscyplin"),
    # Chowamy publikacjie instytucji z menu - niech sobie zostaną dostępne z innego
    # miejsca, ale nie są one generalnie potrzebne (mpasternak, 1.09.2021)
    # ("Publikacje instytucji", "/admin/pbn_api/publikacjainstytucji"),
    ("Oświadczenia instytucji", "/admin/pbn_api/oswiadczenieinstytucji"),
    ("Przesłane dane", "/admin/pbn_api/sentdata"),
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
    ("Szablony", "/admin/dbtemplates/template/"),
    ("Powiązania szablonów dla opisu", "/admin/bpp/szablondlaopisubibliograficznego/"),
]

STRUKTURA_MENU = [
    ("Uczelnie", "/admin/bpp/uczelnia/"),
    ("Wydziały", "/admin/bpp/wydzial/"),
    ("Jednostki", "/admin/bpp/jednostka/"),
    ("Kierunki studiów", "/admin/bpp/kierunek_studiow/"),
]

REDAKTOR_MENU = [
    ("Autorzy", "/admin/bpp/autor/"),
    (
        "Autorzy - udziały (Ewaluacja 2021)",
        "/admin/ewaluacja2021/iloscudzialowdlaautora/",
    ),
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
    (
        "Rozbieżności dyscyplin",
        "/admin/rozbieznosci_dyscyplin/rozbieznosciview/",
    ),
    (
        "Rozbieżności dyscyplin źródeł",
        "/admin/rozbieznosci_dyscyplin/rozbieznoscizrodelview/",
    ),
    ("Zgłoszenia publikacji", "/admin/zglos_publikacje/zgloszenie_publikacji/"),
]

ADMIN_MENU = [
    ("Grupy", "/admin/auth/group/"),
    ("Użytkownicy", "/admin/bpp/bppuser/"),
    ("Formularze wyszukiwania", "/admin/multiseek/searchform/"),
    (
        "Obsługa zgłoszeń prac - wydziały",
        "/admin/zglos_publikacje/obslugujacy_zgloszenia_wydzialow/",
    ),
    (
        "Kolumny w module redagowania",
        "/admin/dynamic_columns/modeladmincolumn/",
    ),
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
        flt("dane systemowe", "Dane systemowe", SYSTEM_MENU)
        flt("struktura", "Struktura", STRUKTURA_MENU)
        flt(GR_WPROWADZANIE_DANYCH, "Wprowadzanie danych", REDAKTOR_MENU)
        if GR_ZGLOSZENIA_PUBLIKACJI not in groups and not user.is_superuser:
            # Wyrzuć "zgłoszenia publikacji" z REDAKTOR_MENU
            del self.children[-1].children[-1]

        flt("raporty", "Raporty", RAPORTY_MENU)
        flt("administracja", "Administracja", ADMIN_MENU)

        return super().init_with_context(context)
