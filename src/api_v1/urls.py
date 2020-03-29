from django.conf.urls import url, include
from rest_framework import routers

from api_v1.viewsets.autor import (
    AutorViewSet,
    Funkcja_AutoraViewSet,
    TytulViewSet,
    Autor_JednostkaViewSet,
)
from api_v1.viewsets.struktura import JednostkaViewSet, WydzialViewSet, UczelniaViewSet
from api_v1.viewsets.zrodlo import Rodzaj_ZrodlaViewSet, ZrodloViewSet

router = routers.DefaultRouter()

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
