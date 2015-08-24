from braces.views import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic.base import TemplateView
from django.views.generic.list import ListView
from bpp.models.struktura import Wydzial

class Generuj(LoginRequiredMixin, TemplateView):
    template_name = "generuj.html"

    def get(self, request, *args, **kwargs):
        return

class WyborWydzialu(LoginRequiredMixin, ListView):
    model = Wydzial
    template_name = "wydzial_list.html"
    
    def get_context_data(self, **kwargs):
        return super(WyborWydzialu, self).get_context_data(**{'lata': [2013, 2014, 2015]})
