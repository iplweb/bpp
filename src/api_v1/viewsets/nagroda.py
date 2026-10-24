from functools import cache

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from rest_framework import viewsets

from api_v1.permissions import widzi_dane_osobowe
from api_v1.serializers.nagroda import NagrodaSerializer
from bpp.models import Uczelnia
from bpp.models.abstract.api_export import ModelOpcjonalnieNieEksportowanyDoAPI
from bpp.models.abstract.metadata import ModelZeStatusem
from bpp.models.autor import Autor
from bpp.models.nagroda import Nagroda


@cache
def _modele_rekordow():
    """Zarządzane modele ``bpp`` z flagą ``nie_eksportuj_przez_api`` i/lub
    statusem korekty — możliwe cele ``Nagroda.object``. Widoki
    (``managed=False``, np. ``Rekord``) pomijamy: nagroda wskazuje zawsze
    na konkretną tabelę."""
    return [
        model
        for model in apps.get_app_config("bpp").get_models()
        if model._meta.managed
        and not model._meta.proxy
        and issubclass(model, (ModelOpcjonalnieNieEksportowanyDoAPI, ModelZeStatusem))
    ]


def warunek_ukrytych_nagrod(ukryte_statusy):
    """``Q`` dopasowujące nagrody przypięte do obiektów niewidocznych w API
    (autor z ``pokazuj=False``, rekord z ``nie_eksportuj_przez_api`` albo
    ze statusem korekty z ``ukryte_statusy``).

    Jedno podzapytanie ``object_id IN (SELECT pk …)`` na typ obiektu — bez
    iterowania po wierszach w Pythonie.
    """
    warunek = Q(
        content_type=ContentType.objects.get_for_model(Autor),
        object_id__in=Autor.objects.filter(pokazuj=False).values("pk"),
    )

    for model in _modele_rekordow():
        ukryj = Q()
        if issubclass(model, ModelOpcjonalnieNieEksportowanyDoAPI):
            ukryj |= Q(nie_eksportuj_przez_api=True)
        if ukryte_statusy and issubclass(model, ModelZeStatusem):
            ukryj |= Q(status_korekty_id__in=ukryte_statusy)
        if not ukryj:
            continue
        warunek |= Q(
            content_type=ContentType.objects.get_for_model(model),
            object_id__in=model.objects.filter(ukryj).values("pk"),
        )

    return warunek


class NagrodaViewSet(viewsets.ReadOnlyModelViewSet):
    # ``organ_przyznajacy`` to StringRelatedField (join), a ``object`` to
    # GenericForeignKey, z którego serializer buduje absolute_url. GFK nie da
    # się załatwić przez select_related (relacja polimorficzna) — prefetch
    # grupuje wiersze po content_type i robi jedno zapytanie na TYP zamiast
    # na wiersz.
    queryset = (
        Nagroda.objects.all()
        .select_related("organ_przyznajacy")
        .prefetch_related("object")
    )
    serializer_class = NagrodaSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        # Redakcja i superuser widzą wszystkie nagrody; pozostali tylko
        # te, których obiekt jest widoczny w API.
        if widzi_dane_osobowe(self.request):
            return queryset

        ukryte_statusy = None
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        if uczelnia:
            ukryte_statusy = list(uczelnia.ukryte_statusy("api"))

        return queryset.exclude(warunek_ukrytych_nagrod(ukryte_statusy))
