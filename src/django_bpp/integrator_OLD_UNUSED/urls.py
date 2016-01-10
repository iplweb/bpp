from django.conf.urls import patterns, url

from integrator_OLD_UNUSED import FileUploadView, FileListView, AutorIntegrationFileDetail, FileListaMinisterialnaUploadView

urlpatterns = patterns(
    '',

    url(r'^nowy/$', FileUploadView.as_view(template_name="integrator_upload.html"), name='new'),
    url(r'^nowy_lista_min/$', FileListaMinisterialnaUploadView.as_view(template_name="integrator_upload.html"), name='new_list_min'),

    url(r'^(?P<pk>[0-9]+)/$', AutorIntegrationFileDetail.as_view(template_name="integrator_detail.html"), name='detail'),
    url(r'^$', FileListView.as_view(template_name="integrator_list.html"), name='list'),

)
