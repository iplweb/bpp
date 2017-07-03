from django.conf.urls import url

from integrator2.views import Main, UploadListaMinisterialna, DetailBase

urlpatterns = (
        url(r'^upload/$', UploadListaMinisterialna.as_view(), name='upload_lista_ministerialna'),
        # url(r'^nowy_lista_min/$', .as_view(template_name="integrator_upload.html"), name='new_list_min'),
        url(r'^$', Main.as_view(), name='main'),
        url(r'^(?P<model_name>[a-z]+)/(?P<pk>[0-9]+)/$', DetailBase.as_view(), name='detail'),

)
