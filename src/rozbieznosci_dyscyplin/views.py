from django.shortcuts import render
from django.views.generic import ListView

from bpp.models import Autor, Autor_Dyscyplina


class ListaAutorow(ListView):
    template_name = 'przypisywanie_dyscyplin/main_view.html'
    context_object_name = 'lista_autorow'

    def get_queryset(self):
        return Autor.objects.filter(
            pk__in=Autor_Dyscyplina.objects.all().values('autor').distinct()
        )


