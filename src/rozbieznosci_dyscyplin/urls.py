from django.urls import path

from . import views

app_name = 'rozbieznosci_dyscyplin'

urlpatterns = [
    path('', views.MainView.as_view(), name='main-view'),

    path('api/rozbieznosci-dyscyplin/',
         views.API_RozbieznosciDyscyplin.as_view(),
         name='api-rozbieznosci-dyscyplin'),

    path('api/redirect-to-admin/<int:content_type_id>/<int:object_id>/',
         views.RedirectToAdmin.as_view(),
         name='redirect-to-admin')

]
