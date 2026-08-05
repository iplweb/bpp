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
from oauth_mcp.views_whoami import WhoAmIView


class CustomRouter(routers.DefaultRouter):
    """Router ``/api/v1/`` z bramką ``Uczelnia.api_v1_wlaczone``.

    Każdy rejestrowany viewset trafia do routera jako podklasa objęta
    :class:`~api_v1.permissions.ApiV1Wlaczone`, dzięki czemu przełącznik
    obejmuje CAŁE API — łącznie z viewsetami, które mają własne
    ``permission_classes`` (``/zapytanie/*``, raport slotów,
    ``recent_*_publications``).

    Dlaczego nie ``DEFAULT_PERMISSION_CLASSES``: to ustawienie *projektu*,
    nie aplikacji (DRF nie ma per-app settings) — złapałoby też widoki DRF
    spoza ``/api/v1/``, a i tak ominęłyby je viewsety nadpisujące
    ``permission_classes``. Dlaczego nie mixin dopisany ręcznie: viewsety nie
    mają jednej wspólnej klasy bazowej, więc znaczyłoby to edycję ~25 plików
    i pozostawienie furtki przy każdym nowym viewsecie.
    """

    APIRootView = z_bramka_api_v1(CustomAPIRootView)

    def register(self, prefix, viewset, basename=None):
        if basename is None:
            basename = self.get_default_basename(viewset)
        super().register(prefix, z_bramka_api_v1(viewset), basename)


router = CustomRouter()

#
# Read-only JSON API
#

router.register(r"konferencja", KonferencjaViewSet)
router.register(r"seria_wydawnicza", Seria_WydawniczaViewSet)

router.register(r"czas_udostepnienia_openaccess", Czas_Udostepnienia_OpenAccess_ViewSet)

router.register(r"nagroda", NagrodaViewSet)
router.register(r"charakter_formalny", Charakter_FormalnyViewSet)
router.register(r"typ_kbn", Typ_KBNViewSet)
router.register(r"jezyk", JezykViewSet)
router.register(r"dyscyplina_naukowa", Dyscyplina_NaukowaViewSet)

router.register(r"poziom_wydawcy", Poziom_WydawcyViewSet)
router.register(r"wydawca", WydawcaViewSet)

router.register(r"wydawnictwo_zwarte", Wydawnictwo_ZwarteViewSet)
router.register(r"wydawnictwo_zwarte_autor", Wydawnictwo_Zwarte_AutorViewSet)
router.register(
    r"wydawnictwo_zwarte_streszczenie",
    Wydawnictwo_Zwarte_StreszczenieViewSet,
)

router.register(r"patent", PatentViewSet)
router.register(r"patent_autor", Patent_AutorViewSet)

router.register(r"wydawnictwo_ciagle", Wydawnictwo_CiagleViewSet)
router.register(r"wydawnictwo_ciagle_autor", Wydawnictwo_Ciagle_AutorViewSet)
router.register(
    r"wydawnictwo_ciagle_zewnetrzna_baza_danych",
    Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychViewSet,
)
router.register(
    r"wydawnictwo_ciagle_streszczenie",
    Wydawnictwo_Ciagle_StreszczenieViewSet,
)

router.register(r"praca_doktorska", Praca_DoktorskaViewSet)

router.register(r"praca_habilitacyjna", Praca_HabilitacyjnaViewSet)

router.register(r"rodzaj_zrodla", Rodzaj_ZrodlaViewSet)
router.register(r"zrodlo", ZrodloViewSet)

router.register(r"jednostka", JednostkaViewSet)
router.register(r"uczelnia", UczelniaViewSet)

router.register(r"szukaj", SzukajViewSet, basename="szukaj")

router.register(
    r"zapytanie/rekord", ZapytanieRekordViewSet, basename="zapytanie_rekord"
)
router.register(r"zapytanie/autor", ZapytanieAutorViewSet, basename="zapytanie_autor")
router.register(
    r"zapytanie/autorzy", ZapytanieAutorzyViewSet, basename="zapytanie_autorzy"
)

router.register(r"autor", AutorViewSet)
router.register(r"funkcja_autora", Funkcja_AutoraViewSet)
router.register(r"tytul", TytulViewSet)
router.register(r"autor_jednostka", Autor_JednostkaViewSet)
router.register(
    r"recent_author_publications",
    RecentAuthorPublicationsViewSet,
    basename="recent_author_publications",
)
router.register(
    r"recent_unit_publications",
    RecentUnitPublicationsViewSet,
    basename="recent_unit_publications",
)

#
# Raport slotow uczelnia
#

router.register(
    r"raport_slotow_uczelnia",
    RaportSlotowUczelniaViewSet,
    basename="raport_slotow_uczelnia",
)
router.register(
    r"raport_slotow_uczelnia_wiersz",
    RaportSlotowUczelniaWierszViewSet,
    basename="raport_slotow_uczelnia_wiersz",
)

#
#
#

urlpatterns = [
    # ``whoami`` nie idzie przez router, więc bramkę dostaje osobno — inaczej
    # wyłączone API nadal potwierdzałoby tożsamość zalogowanego klienta.
    path("whoami/", z_bramka_api_v1(WhoAmIView).as_view(), name="whoami"),
    url(r"^", include(router.urls)),
]
