from django.urls import re_path

from . import views

app_name = "oswiadczenia"

urlpatterns = [
    re_path(
        r"^pojedyncze/(?P<content_type_id>[\d]+)/(?P<object_id>[\d]+)/"
        r"(?P<autor_id>[\d]+)/(?P<dyscyplina_pracy_id>[\d]+)/$",
        views.OswiadczenieAutoraView.as_view(),
        name="jedno-oswiadczenie",
    ),
    re_path(
        r"^pojedyncze-alternatywna/(?P<content_type_id>[\d]+)/(?P<object_id>[\d]+)/"
        r"(?P<autor_id>[\d]+)/(?P<dyscyplina_pracy_id>[\d]+)/$",
        views.OswiadczenieAutoraAlternatywnaDyscyplinaView.as_view(),
        name="jedno-oswiadczenie-druga-dyscyplina",
    ),
    re_path(
        r"^wiele/(?P<content_type_id>[\d]+)/(?P<object_id>[\d]+)/$",
        views.OswiadczeniaPublikacji.as_view(),
        name="wiele-oswiadczen",
    ),
]
