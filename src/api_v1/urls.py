from django.conf.urls import url, include
from rest_framework import routers

from api_v1.viewsets.jednostka import JednostkaViewSet
from api_v1.viewsets.zrodlo import Rodzaj_ZrodlaViewSet, ZrodloViewSet

router = routers.DefaultRouter()
router.register(r"rodzaj_zrodla", Rodzaj_ZrodlaViewSet)
router.register(r"zrodlo", ZrodloViewSet)
router.register(r"jednostka", JednostkaViewSet)

urlpatterns = [
    url(r"^", include(router.urls)),
    url(r"^api-auth/", include("rest_framework.urls", namespace="rest_framework")),
]
