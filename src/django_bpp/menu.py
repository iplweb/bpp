"""
This file was generated with the custommenu management command, it contains
the classes for the admin menu, you can customize this class as you want.

To activate your custom menu add the following to your settings.py::
    ADMIN_TOOLS_MENU = 'django_bpp.menu.CustomMenu'
"""

from admin_tools.menu import Menu, items
from django.template.defaultfilters import capfirst
from django.urls import reverse
from django.utils.functional import lazy as _lazy
from django.utils.translation import gettext_lazy as _
from polish_inflection import MIANOWNIK, MNOGA, odmien_lub_wyraz

from bpp.const import GR_WPROWADZANIE_DANYCH, GR_ZGLOSZENIA_PUBLIKACJI
from bpp.nazwy import lemat


def _tytul(uid, liczba=None):
    lem = lemat(uid)
    if liczba:
        forma = odmien_lub_wyraz(lem, MIANOWNIK, liczba)
    else:
        forma = odmien_lub_wyraz(lem, MIANOWNIK)
    return capfirst(forma)


_tytul_lazy = _lazy(_tytul, str)

PBN_MENU = [
    ("Instytucje", "/admin/pbn_api/institution"),
    ("Konferencje", "/admin/pbn_api/conference"),
    ("Zrodla", "/admin/pbn_api/journal"),
    ("Wydawcy", "/admin/pbn_api/publisher"),
    ("Naukowcy", "/admin/pbn_api/scientist"),
    ("Osoby z instytucji", "/admin/pbn_api/osobazinstytucji"),
    ("Publikacje", "/admin/pbn_api/publication"),
    ("Publikacje instytucji V1", "/admin/pbn_api/publikacjainstytucji"),
    ("Publikacje instytucji V2", "/admin/pbn_api/publikacjainstytucji_v2"),
    ("Słowniki dyscyplin", "/admin/pbn_api/disciplinegroup"),
    ("Dyscypliny", "/admin/pbn_api/discipline"),
    ("Tłumacz dyscyplin", "/admin/pbn_api/tlumaczdyscyplin"),
    # Chowamy publikacjie instytucji z menu - niech sobie zostaną dostępne z innego
    # miejsca, ale nie są one generalnie potrzebne (mpasternak, 1.09.2021)
    # ("Publikacje instytucji", "/admin/pbn_api/publikacjainstytucji"),
    ("Oświadczenia instytucji", "/admin/pbn_api/oswiadczenieinstytucji"),
    ("Przesłane dane", "/admin/pbn_api/sentdata"),
    ("Niepożądane odpowiedzi PBN", "/admin/pbn_api/pbnodpowiedziniepozadane"),
    ("Kolejka eksportu", "/admin/pbn_export_queue/pbn_export_queue"),
    (
        "Deduplikator autorów - nie duplikaty",
        "/admin/deduplikator_autorow/notaduplicate/",
    ),
]


SYSTEM_MENU = [
    ("Charaktery formalne", "/admin/bpp/charakter_formalny/"),
    ("Crossref Mapper", "/admin/bpp/crossref_mapper/"),
    ("Charakter PBN", "/admin/bpp/charakter_pbn/"),
    ("Mapowania DSpace", "/admin/dspace_api/mapowanie_dspace/"),
    ("Wysyłki do DSpace", "/admin/dspace_api/senttodspace/"),
    ("Dyscypliny naukowe", "/admin/bpp/dyscyplina_naukowa/"),
    ("Formularze - wartości domyślne", "/admin/formdefaults/formrepresentation/"),
    ("Funkcje w jednostce", "/admin/bpp/funkcja_autora/"),
    ("Granty", "/admin/bpp/grant/"),
    ("Grupy pracownicze", "/admin/bpp/grupa_pracownicza/"),
    (
        "Import POLON - wymuszenia grup stanowisk",
        "/admin/import_polon/importpolonoverride/",
    ),
    ("Języki", "/admin/bpp/jezyk/"),
    ("OpenAccess: wydawnictwa ciągłe", "/admin/bpp/tryb_openaccess_wydawnictwo_ciagle"),
    ("OpenAccess: wydawnictwa zwarte", "/admin/bpp/tryb_openaccess_wydawnictwo_zwarte"),
    ("OpenAccess: czas udostępnienia", "/admin/bpp/czas_udostepnienia_openaccess"),
    ("OpenAccess: licencja", "/admin/bpp/licencja_openaccess"),
    ("OpenAccess: wersja tekstu", "/admin/bpp/wersja_tekstu_openaccess"),
    ("Organy przyznające nagrody", "/admin/bpp/organprzyznajacynagrody/"),
    ("Rodzaje autorów - ewaluacja", "/admin/ewaluacja_common/rodzaj_autora/"),
]

SYSTEM_MENU_2 = [
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
    ("Serwisy", "/admin/sites/site/"),
    ("Blog", "/admin/siteblog/article/"),
    ("Favicon", "/admin/favicon/"),
    ("Szablony", "/admin/dbtemplates/template/"),
    ("Powiązania szablonów dla opisu", "/admin/bpp/szablondlaopisubibliograficznego/"),
]

STRUKTURA_MENU = [
    (_tytul_lazy("UCZELNIA"), "/admin/bpp/uczelnia/"),
    (_tytul_lazy("WYDZIAL", MNOGA), "/admin/bpp/wydzial/"),
    (_tytul_lazy("JEDNOSTKA", MNOGA), "/admin/bpp/jednostka/"),
    ("Kierunki studiów", "/admin/bpp/kierunek_studiow/"),
]

REDAKTOR_MENU = [
    ("Autorzy", "/admin/bpp/autor/"),
    (
        "Autorzy - udziały",
        "/admin/ewaluacja_liczba_n/iloscudzialowdlaautorazarok/",
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
    ("Importer publikacji", "/importer_publikacji/"),
]

ADMIN_MENU = [
    ("Grupy", "/admin/auth/group/"),
    ("Użytkownicy", "/admin/bpp/bppuser/"),
    ("Ustawienia systemu", "/admin/constance/config/"),
    ("Formularze wyszukiwania", "/admin/multiseek/searchform/"),
    (
        "Obsługa zgłoszeń prac - wydziały",
        "/admin/zglos_publikacje/obslugujacy_zgloszenia_wydzialow/",
    ),
    (
        "Kolumny w module redagowania",
        "/admin/dynamic_admin_columns/modeladmin/",
    ),
]

DOCKER_SERVICES_MENU = [
    ("Grafana", "/grafana/"),
    ("Dozzle (logi)", "/dozzle/"),
    ("Flower (Celery)", "/flower/"),
]


def submenu(label, tuples, icon_class=None):
    menu_item = items.MenuItem(
        label, children=[items.MenuItem(label, link) for label, link in tuples]
    )
    if icon_class:
        menu_item.css_classes = [icon_class]
    return menu_item


def submenu_multicolumn(label, column1_tuples, column2_tuples, icon_class=None):
    """Create a two-column submenu"""
    children = []

    # Add column 1 items first (they will appear in the left column)
    for item_label, link in column1_tuples:
        menu_item = items.MenuItem(item_label, link)
        menu_item.css_classes = ["column-1"]
        children.append(menu_item)

    # Add column 2 items second (they will appear in the right column)
    for item_label, link in column2_tuples:
        menu_item = items.MenuItem(item_label, link)
        menu_item.css_classes = ["column-2"]
        children.append(menu_item)

    # Create parent menu item with children
    parent = items.MenuItem(label, children=children)
    css_classes = ["has-columns"]
    if icon_class:
        css_classes.append(icon_class)
    parent.css_classes = css_classes
    return parent


# First 5 theme options for column 1
THEME_ITEMS_COL1 = [
    ("Domyślny (ciemny)", "default", "theme-selector-default"),
    ("Klasyczny jasny", "classic-light", "theme-selector-classic-light"),
    ("Granatowy akademicki", "navy-academic", "theme-selector-navy-academic"),
    ("Szary profesjonalny", "gray-professional", "theme-selector-gray-professional"),
    ("Kremowo-zielony", "cream-green", "theme-selector-cream-green"),
]

# Remaining theme options for column 2
THEME_ITEMS_COL2 = [
    ("Minimalistyczny jasny", "minimal-light", "theme-selector-minimal-light"),
    ("Złoty", "golden", "theme-selector-golden"),
    ("Srebrny", "srebrny", "theme-selector-srebrny"),
    ("Brat Ludwika", "mario-bros", "theme-selector-mario-bros"),
    ("Brat Mariana", "luigi", "theme-selector-luigi"),
]

# Font options for column 2
FONT_ITEMS = [
    ("Domyślna czcionka", "default", "font-selector-default"),
    ("Inter", "inter-small", "font-selector-inter-small"),
    ("Open Sans", "opensans-small", "font-selector-opensans-small"),
    ("Roboto", "roboto-small", "font-selector-roboto-small"),
    ("Lato", "lato-small", "font-selector-lato-small"),
    ("Source Sans Pro", "sourcesans-small", "font-selector-sourcesans-small"),
    ("Segoe UI", "segoeui-small", "font-selector-segoeui-small"),
    ("Arial", "arial-small", "font-selector-arial-small"),
    ("Verdana", "verdana-small", "font-selector-verdana-small"),
    ("Calibri", "calibri-small", "font-selector-calibri-small"),
]


def _styled_item(label, url, css_classes):
    item = items.MenuItem(label, url=url)
    item.css_classes = css_classes
    return item


def _should_hide_wydzial():
    """Czy ukryć pozycję „wydział" w menu Struktura (na podst. ustawień/uczelni)."""
    from django.conf import settings

    from bpp.models import Uczelnia

    uczelnia = Uczelnia.objects.get_default()
    uzywaj_wydzialow = True
    if uczelnia is not None:
        uzywaj_wydzialow = uczelnia.uzywaj_wydzialow

    return (
        (not getattr(settings, "DJANGO_BPP_UCZELNIA_UZYWA_WYDZIALOW", True))
        or (not uzywaj_wydzialow)
    ) and STRUKTURA_MENU[1][1].find("wydzial") >= 0


def _add_group_submenus(menu, user, groups):
    """Dodaj poddrzewa menu zależne od grup/uprawnień użytkownika."""

    def flt(n1, n2, v, icon_class=None):
        if user.is_superuser or n1 in groups:
            menu.children += [
                submenu(n2, v, icon_class),
            ]

    flt("web", "WWW", WEB_MENU, "menu-icon-web")
    flt("dane systemowe", "PBN API", PBN_MENU, "menu-icon-api")

    # Combine "Dane" and "systemowe" into single 2-column menu
    if user.is_superuser or "dane systemowe" in groups:
        menu.children += [
            submenu_multicolumn(
                "Dane systemowe", SYSTEM_MENU, SYSTEM_MENU_2, "menu-icon-settings"
            ),
        ]

    if _should_hide_wydzial():
        STRUKTURA_MENU.pop(1)

    flt("struktura", "Struktura", STRUKTURA_MENU, "menu-icon-structure")
    flt(GR_WPROWADZANIE_DANYCH, "Wprowadzanie danych", REDAKTOR_MENU, "menu-icon-edit")
    if GR_ZGLOSZENIA_PUBLIKACJI not in groups and not user.is_superuser:
        # Wyrzuć "zgłoszenia publikacji" z REDAKTOR_MENU
        del menu.children[-1].children[-1]

    flt("raporty", "Raporty", RAPORTY_MENU, "menu-icon-reports")
    flt("administracja", "Administracja", ADMIN_MENU, "menu-icon-admin")

    # Add Docker services to Administracja menu (superusers only)
    if user.is_superuser:
        for label, url in DOCKER_SERVICES_MENU:
            menu.children[-1].children.append(items.MenuItem(label, url))


def _build_user_menu(user):
    """Zbuduj menu „Mój profil" (akcje użytkownika + motywy + czcionki)."""
    username = (
        user.first_name or user.username or user.get_short_name() or user.get_username()
    )

    # Column 1: user actions and first themes
    column1_children = [_styled_item(username, "#", ["column-1"])]

    if user.has_usable_password():
        column1_children.append(
            _styled_item(
                str(_("Change password")),
                reverse("admin:password_change"),
                ["column-1"],
            )
        )

    column1_children.append(
        _styled_item(str(_("Log out")), reverse("admin:logout"), ["column-1"])
    )
    column1_children.append(_styled_item("---", "#", ["theme-separator", "column-1"]))
    for theme_name, theme_key, css_class in THEME_ITEMS_COL1:
        column1_children.append(
            _styled_item(
                theme_name,
                f"#theme-{theme_key}",
                ["theme-selector-item", css_class, "column-1"],
            )
        )

    # Column 2: remaining themes, spacers, then fonts
    column2_children = []
    for theme_name, theme_key, css_class in THEME_ITEMS_COL2:
        column2_children.append(
            _styled_item(
                theme_name,
                f"#theme-{theme_key}",
                ["theme-selector-item", css_class, "column-2"],
            )
        )

    # Add 4 empty spacer entries above fonts in column 2
    for _i in range(4):
        column2_children.append(_styled_item("", "#", ["menu-spacer", "column-2"]))

    column2_children.append(_styled_item("---", "#", ["font-separator", "column-2"]))
    for font_name, font_key, css_class in FONT_ITEMS:
        column2_children.append(
            _styled_item(
                font_name,
                f"#font-{font_key}",
                ["font-selector-item", css_class, "column-2"],
            )
        )

    # Combine all children in order (column1 first, then column2)
    user_menu = items.MenuItem(
        "Mój profil", children=column1_children + column2_children
    )
    user_menu.css_classes = ["menu-icon-user", "has-columns"]
    return user_menu


class CustomMenu(Menu):
    def __init__(self, **kwargs):
        Menu.__init__(self, **kwargs)

        # Add BPP logo/home link as first item
        bpp_home = items.MenuItem("BPP", url="/")
        bpp_home.css_classes = ["menu-icon-home"]

        self.children += [
            bpp_home,
            items.MenuItem(str(_("Dashboard")), reverse("admin:index")),
            # items.Bookmarks(),  # Hidden - user requested to hide bookmarks menu
        ]

    def init_with_context(self, context):
        user = context["request"].user
        if not hasattr(user, "__admin_menu_groups"):
            user.__admin_menu_groups = [x.name for x in user.cached_groups]
        groups = user.__admin_menu_groups

        # Dashboard is now second item (index 1), add icon
        if len(self.children) >= 2:
            self.children[1].css_classes = ["menu-icon-dashboard"]  # Dashboard (Panel)

        _add_group_submenus(self, user, groups)
        self.children.append(_build_user_menu(user))

        return super().init_with_context(context)
