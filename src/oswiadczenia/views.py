from django.http import Http404
from django.views.generic import DetailView

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Cache_Punktacja_Autora,
    Dyscyplina_Naukowa,
    Rekord,
)


class OswiadczenieAutoraView(DetailView):
    template_name = "oswiadczenia/oswiadczenie_autora.html"

    def get_object(self, queryset=None):
        try:
            self.object = Rekord.objects.get(
                pk=(self.kwargs["content_type_id"], self.kwargs["object_id"])
            )
        except Rekord.DoesNotExist:
            raise Http404

        try:
            self.autor = self.object.autorzy_set.get(
                autor_id=self.kwargs["autor_id"]
            ).autor
        except Autor.DoesNotExist:
            raise Http404

        try:
            self.dyscyplina_pracy = Dyscyplina_Naukowa.objects.get(
                pk=self.kwargs["dyscyplina_pracy_id"]
            )
        except Dyscyplina_Naukowa.DoesNotExist:
            raise NotImplementedError

        try:
            self.dyscyplina_naukowa = Autor_Dyscyplina.objects.get(
                rok=self.object.rok, autor=self.autor
            ).dyscyplina_naukowa
        except Autor_Dyscyplina.DoesNotExist:
            self.dyscyplina_naukowa = None

        try:
            self.subdyscyplina_naukowa = Autor_Dyscyplina.objects.get(
                rok=self.object.rok, autor=self.autor
            ).subdyscyplina_naukowa
        except Autor_Dyscyplina.DoesNotExist:
            self.subdyscyplina_naukowa = None

        return self.object

    def get_context_data(self, **kwargs):
        return {
            "object": self.object,
            "autor": self.autor,
            "dyscyplina_pracy": self.dyscyplina_pracy,
            "dyscyplina_naukowa": self.dyscyplina_naukowa,
            "subdyscyplina_naukowa": self.subdyscyplina_naukowa,
        }


class OswiadczenieAutoraAlternatywnaDyscyplinaView(OswiadczenieAutoraView):
    def get_context_data(self, **kwargs):
        # Ustaw alternatywną dyscyplinę, czyli nie tą która jest przy pracy
        if self.dyscyplina_pracy == self.dyscyplina_naukowa:
            self.dyscyplina_pracy = self.subdyscyplina_naukowa
        else:
            self.dyscyplina_pracy = self.dyscyplina_naukowa

        return super().get_context_data(**kwargs)


class OswiadczeniaPublikacji(DetailView):
    template_name = "oswiadczenia/wiele_oswiadczen.html"

    def get_object(self, **kwargs):
        try:
            self.object = Rekord.objects.get(
                pk=(self.kwargs["content_type_id"], self.kwargs["object_id"])
            )
        except Rekord.DoesNotExist:
            raise Http404

        return self.object

    def get_context_data(self, **kwargs):
        return {
            "object": self.object,
            "punktacje": Cache_Punktacja_Autora.objects.filter(
                rekord_id=self.object.pk
            ),
        }
