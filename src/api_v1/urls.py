from django.conf.urls import url, include
from rest_framework import routers

from api_v1.viewsets.autor import (
    AutorViewSet,
    Funkcja_AutoraViewSet,
    TytulViewSet,
    Autor_JednostkaViewSet,
)
from api_v1.viewsets.nagroda import NagrodaViewSet
from api_v1.viewsets.openaccess import Czas_Udostepnienia_OpenAccess_ViewSet
from api_v1.viewsets.praca_doktorska import Praca_DoktorskaViewSet
from api_v1.viewsets.struktura import JednostkaViewSet, WydzialViewSet, UczelniaViewSet
from api_v1.viewsets.system import (
    Charakter_FormalnyViewSet,
    Typ_KBNViewSet,
    JezykViewSet,
    Dyscyplina_NaukowaViewSet,
    KonferencjaViewSet,
    Seria_WydawniczaViewSet,
)
from api_v1.viewsets.wydawca import Poziom_WydawcyViewSet, WydawcaViewSet
from api_v1.viewsets.wydawnictwo_ciagle import (
    Wydawnictwo_CiagleViewSet,
    Wydawnictwo_Ciagle_AutorViewSet,
    Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychViewSet,
)
from api_v1.viewsets.wydawnictwo_zwarte import (
    Wydawnictwo_ZwarteViewSet,
    Wydawnictwo_Zwarte_AutorViewSet,
)
from api_v1.viewsets.zrodlo import Rodzaj_ZrodlaViewSet, ZrodloViewSet
from bpp.models import Wydawnictwo_Zwarte

router = routers.DefaultRouter()

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

router.register(r"wydawnictwo_ciagle", Wydawnictwo_CiagleViewSet)
router.register(r"wydawnictwo_ciagle_autor", Wydawnictwo_Ciagle_AutorViewSet)
router.register(
    r"wydawnictwo_ciagle_zewnetrzna_baza_danych",
    Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychViewSet,
)

router.register(r"praca_doktorska", Praca_DoktorskaViewSet)

router.register(r"rodzaj_zrodla", Rodzaj_ZrodlaViewSet)
router.register(r"zrodlo", ZrodloViewSet)

router.register(r"jednostka", JednostkaViewSet)
router.register(r"wydzial", WydzialViewSet)
router.register(r"uczelnia", UczelniaViewSet)

router.register(r"autor", AutorViewSet)
router.register(r"funkcja_autora", Funkcja_AutoraViewSet)
router.register(r"tytul", TytulViewSet)
router.register(r"autor_jednostka", Autor_JednostkaViewSet)

urlpatterns = [
    url(r"^", include(router.urls)),
    url(r"^api-auth/", include("rest_framework.urls", namespace="rest_framework")),
]
