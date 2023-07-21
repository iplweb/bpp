from django.urls import include
from django.urls import re_path as url
from rest_framework import routers

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
from api_v1.viewsets.struktura import JednostkaViewSet, UczelniaViewSet, WydzialViewSet
from api_v1.viewsets.system import (
    Charakter_FormalnyViewSet,
    Dyscyplina_NaukowaViewSet,
    JezykViewSet,
    KonferencjaViewSet,
    Seria_WydawniczaViewSet,
    Typ_KBNViewSet,
)
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
from api_v1.viewsets.zrodlo import Rodzaj_ZrodlaViewSet, ZrodloViewSet

router = routers.DefaultRouter()

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
router.register(r"wydzial", WydzialViewSet)
router.register(r"uczelnia", UczelniaViewSet)

router.register(r"autor", AutorViewSet)
router.register(r"funkcja_autora", Funkcja_AutoraViewSet)
router.register(r"tytul", TytulViewSet)
router.register(r"autor_jednostka", Autor_JednostkaViewSet)

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
    url(r"^", include(router.urls)),
]
