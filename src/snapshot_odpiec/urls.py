from django.urls import path

from .views import AplikujSnapshot, ListaSnapshotow, NowySnapshot

app_name = "snapshot_odpiec"


urlpatterns = [
    path("", ListaSnapshotow.as_view(), name="index"),
    path("nowy/", NowySnapshot.as_view(), name="nowy"),
    path("aplikuj/<int:pk>/", AplikujSnapshot.as_view(), name="aplikuj"),
]
