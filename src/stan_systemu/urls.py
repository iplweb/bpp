from django.urls import path

from stan_systemu.views import IloscObiektowWDenormQueue

app_name = "stan_systemu"

urlpatterns = [
    path(
        "ilosc_obiektow_denorm_queue/",
        IloscObiektowWDenormQueue.as_view(),
        name="ilosc_obiektow_w_denorm_queue",
    )
]
