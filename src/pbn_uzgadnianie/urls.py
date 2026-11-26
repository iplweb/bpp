from django.urls import path

from . import views

app_name = "pbn_uzgadnianie"

urlpatterns = [
    path("", views.StronaGlownaView.as_view(), name="main"),
    path("start/", views.StartView.as_view(), name="start"),
    path("<int:pk>/", views.SzczegolyView.as_view(), name="szczegoly"),
    path("<int:pk>/stan/", views.StanView.as_view(), name="stan"),
    path("<int:pk>/anuluj/", views.AnulujView.as_view(), name="anuluj"),
    path("<int:pk>/wykonaj/", views.WykonajPodgladView.as_view(), name="wykonaj"),
    path("<int:pk>/raport.xlsx", views.RaportXlsxView.as_view(), name="raport_xlsx"),
]
