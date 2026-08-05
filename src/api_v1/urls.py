from django.urls import include, path
from django.urls import re_path as url
from rest_framework import routers

from api_v1.permissions import z_bramka_api_v1
from api_v1.views import CustomAPIRootView
from api_v1.viewsets.autor import (
    Autor_JednostkaViewSet,
    AutorViewSet,
    Funkcja_AutoraViewSet,
    TytulViewSet,
)
from api_v1.viewsets.nagroda import NagrodaViewSet
from api_v1.viewsets.openaccess import Czas_Udostepnienia_OpenAccess_ViewSet
from api_v1.viewsets.patent import Patent_AutorViewSet, PatentViewSet
from api_v1.viewsets.praca_doktorska import Praca_DoktorskaViewSet
from api_v1.viewsets.praca_habilitacyjna import Praca_HabilitacyjnaViewSet
from api_v1.viewsets.raport_slotow_uczelnia import (
    RaportSlotowUczelniaViewSet,
    RaportSlotowUczelniaWierszViewSet,
)
from api_v1.viewsets.recent_author_publications import RecentAuthorPublicationsViewSet
from api_v1.viewsets.recent_unit_publications import RecentUnitPublicationsViewSet
from api_v1.viewsets.struktura import JednostkaViewSet, UczelniaViewSet
from api_v1.viewsets.system import (
    Charakter_FormalnyViewSet,
    Dyscyplina_NaukowaViewSet,
    JezykViewSet,
    KonferencjaViewSet,
    Seria_WydawniczaViewSet,
    Typ_KBNViewSet,
)
from api_v1.viewsets.szukaj import SzukajViewSet
from api_v1.viewsets.wydawca import Poziom_WydawcyViewSet, WydawcaViewSet
from api_v1.viewsets.wydawnictwo_ciagle import (
    Wydawnictwo_Ciagle_AutorViewSet,
    Wydawnictwo_Ciagle_StreszczenieViewSet,
    Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychViewSet,
    Wydawnictwo_CiagleViewSet,
)
from api_v1.viewsets.wydawnictwo_zwarte import (
    Wydawnictwo_Zwarte_AutorViewSet,
    Wydawnictwo_Zwarte_StreszczenieViewSet,
    Wydawnictwo_ZwarteViewSet,
)
from api_v1.viewsets.zapytanie import (
    ZapytanieAutorViewSet,
    ZapytanieAutorzyViewSet,
    ZapytanieRekordViewSet,
)
from api_v1.viewsets.zrodlo import Rodzaj_ZrodlaViewSet, ZrodloViewSet
from bpp.models.uczelnia import GrupaApiV1
from oauth_mcp.views_whoami import WhoAmIView


class CustomRouter(routers.DefaultRouter):
    """Router ``/api/v1/`` z bramką przełączników ``Uczelnia``.

    Każdy rejestrowany viewset trafia do routera jako podklasa objęta
    :class:`~api_v1.permissions.BramkaApiV1`, dzięki czemu przełączniki
    obejmują CAŁE API — łącznie z viewsetami, które mają własne
    ``permission_classes`` (``/zapytanie/*``, raport slotów,
    ``recent_*_publications``).

    Dlaczego nie ``DEFAULT_PERMISSION_CLASSES``: to ustawienie *projektu*,
    nie aplikacji (DRF nie ma per-app settings) — złapałoby też widoki DRF
    spoza ``/api/v1/``, a i tak ominęłyby je viewsety nadpisujące
    ``permission_classes``. Dlaczego nie mixin dopisany ręcznie: viewsety nie
    mają jednej wspólnej klasy bazowej, więc znaczyłoby to edycję ~25 plików
    i pozostawienie furtki przy każdym nowym viewsecie.

    ``grupa`` jest keyword-only i BEZ wartości domyślnej: rejestracja bez
    niej kończy się ``TypeError`` przy imporcie tego modułu, czyli przy
    starcie aplikacji. Wartość domyślna po cichu odtworzyłaby dokładnie tę
    furtkę, przed którą broni ten router.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #: prefiks → grupa; czyta z tego filtr listingu w ``CustomAPIRootView``
        self.grupy_endpointow = {}

    def register(self, prefix, viewset, basename=None, *, grupa):
        if basename is None:
            basename = self.get_default_basename(viewset)
        self.grupy_endpointow[prefix] = grupa
        super().register(prefix, z_bramka_api_v1(viewset, grupa), basename)

    def get_api_root_view(self, api_urls=None):
        """Root z bramką (``grupa=None``) i mapą grup do filtrowania listingu.

        Nadpisujemy metodę zamiast ustawiać atrybut ``APIRootView``, bo widok
        potrzebuje dodatkowego ``initkwargs`` — a te przechodzą wyłącznie
        przez ``as_view()``.
        """
        api_root_dict = {}
        list_name = self.routes[0].name
        for prefix, _viewset, basename in self.registry:
            api_root_dict[prefix] = list_name.format(basename=basename)

        return z_bramka_api_v1(CustomAPIRootView, grupa=None).as_view(
            api_root_dict=api_root_dict,
            grupy_endpointow=dict(self.grupy_endpointow),
        )


router = CustomRouter()

DANE = GrupaApiV1.DANE_BIBLIOGRAFICZNE
NARZEDZIA = GrupaApiV1.NARZEDZIA_REDAKTORSKIE

#
# Dane bibliograficzne — słowniki, struktura, autorzy, rekordy
#

router.register(r"konferencja", KonferencjaViewSet, grupa=DANE)
router.register(r"seria_wydawnicza", Seria_WydawniczaViewSet, grupa=DANE)

router.register(
    r"czas_udostepnienia_openaccess",
    Czas_Udostepnienia_OpenAccess_ViewSet,
    grupa=DANE,
)

router.register(r"nagroda", NagrodaViewSet, grupa=DANE)
router.register(r"charakter_formalny", Charakter_FormalnyViewSet, grupa=DANE)
router.register(r"typ_kbn", Typ_KBNViewSet, grupa=DANE)
router.register(r"jezyk", JezykViewSet, grupa=DANE)
router.register(r"dyscyplina_naukowa", Dyscyplina_NaukowaViewSet, grupa=DANE)

router.register(r"poziom_wydawcy", Poziom_WydawcyViewSet, grupa=DANE)
router.register(r"wydawca", WydawcaViewSet, grupa=DANE)

router.register(r"wydawnictwo_zwarte", Wydawnictwo_ZwarteViewSet, grupa=DANE)
router.register(
    r"wydawnictwo_zwarte_autor", Wydawnictwo_Zwarte_AutorViewSet, grupa=DANE
)
router.register(
    r"wydawnictwo_zwarte_streszczenie",
    Wydawnictwo_Zwarte_StreszczenieViewSet,
    grupa=DANE,
)

router.register(r"patent", PatentViewSet, grupa=DANE)
router.register(r"patent_autor", Patent_AutorViewSet, grupa=DANE)

router.register(r"wydawnictwo_ciagle", Wydawnictwo_CiagleViewSet, grupa=DANE)
router.register(
    r"wydawnictwo_ciagle_autor", Wydawnictwo_Ciagle_AutorViewSet, grupa=DANE
)
router.register(
    r"wydawnictwo_ciagle_zewnetrzna_baza_danych",
    Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychViewSet,
    grupa=DANE,
)
router.register(
    r"wydawnictwo_ciagle_streszczenie",
    Wydawnictwo_Ciagle_StreszczenieViewSet,
    grupa=DANE,
)

router.register(r"praca_doktorska", Praca_DoktorskaViewSet, grupa=DANE)

router.register(r"praca_habilitacyjna", Praca_HabilitacyjnaViewSet, grupa=DANE)

router.register(r"rodzaj_zrodla", Rodzaj_ZrodlaViewSet, grupa=DANE)
router.register(r"zrodlo", ZrodloViewSet, grupa=DANE)

router.register(r"jednostka", JednostkaViewSet, grupa=DANE)
router.register(r"uczelnia", UczelniaViewSet, grupa=DANE)

router.register(r"autor", AutorViewSet, grupa=DANE)
router.register(r"funkcja_autora", Funkcja_AutoraViewSet, grupa=DANE)
router.register(r"tytul", TytulViewSet, grupa=DANE)
router.register(r"autor_jednostka", Autor_JednostkaViewSet, grupa=DANE)

#
# Wyszukiwanie — kosztowne, objęte osobnym limitem zapytań
#

router.register(
    r"szukaj",
    SzukajViewSet,
    basename="szukaj",
    grupa=GrupaApiV1.WYSZUKIWANIE,
)

#
# Kafelki do osadzania — JEDYNA grupa niezależna od głównego wyłącznika
# i od ograniczenia do zalogowanych. Widget wisi na publicznych stronach
# WWW jednostek, których administrator BPP nie kontroluje.
#

router.register(
    r"recent_author_publications",
    RecentAuthorPublicationsViewSet,
    basename="recent_author_publications",
    grupa=GrupaApiV1.KAFELKI,
)
router.register(
    r"recent_unit_publications",
    RecentUnitPublicationsViewSet,
    basename="recent_unit_publications",
    grupa=GrupaApiV1.KAFELKI,
)

#
# Narzędzia redaktorskie — wymagają konta także przy włączonej grupie;
# przełącznik decyduje wyłącznie o tym, czy endpointy w ogóle istnieją.
#

router.register(
    r"zapytanie/rekord",
    ZapytanieRekordViewSet,
    basename="zapytanie_rekord",
    grupa=NARZEDZIA,
)
router.register(
    r"zapytanie/autor",
    ZapytanieAutorViewSet,
    basename="zapytanie_autor",
    grupa=NARZEDZIA,
)
router.register(
    r"zapytanie/autorzy",
    ZapytanieAutorzyViewSet,
    basename="zapytanie_autorzy",
    grupa=NARZEDZIA,
)

router.register(
    r"raport_slotow_uczelnia",
    RaportSlotowUczelniaViewSet,
    basename="raport_slotow_uczelnia",
    grupa=NARZEDZIA,
)
router.register(
    r"raport_slotow_uczelnia_wiersz",
    RaportSlotowUczelniaWierszViewSet,
    basename="raport_slotow_uczelnia_wiersz",
    grupa=NARZEDZIA,
)

#
#
#

urlpatterns = [
    # ``whoami`` nie idzie przez router, więc bramkę dostaje osobno — inaczej
    # wyłączone API nadal potwierdzałoby tożsamość zalogowanego klienta.
    # ``grupa=None``: podlega głównemu wyłącznikowi i ograniczeniu do
    # zalogowanych, ale nie należy do żadnej z czterech grup.
    path(
        "whoami/",
        z_bramka_api_v1(WhoAmIView, grupa=None).as_view(),
        name="whoami",
    ),
    url(r"^", include(router.urls)),
]
