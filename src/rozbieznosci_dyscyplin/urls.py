from django.urls import path

from . import views

app_name = 'przypisywanie_dyscyplin'

urlpatterns = [
    path('', views.ListaAutorow.as_view(), name='main-view')
]
