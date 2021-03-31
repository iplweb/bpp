# -*- encoding: utf-8 -*-

import copy

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from django.db import transaction
from django.http.response import Http404
from django.views.generic import RedirectView

from bpp.models.patent import Patent, Patent_Autor
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor


class TozView(RedirectView):
    @transaction.atomic
    def get_redirect_url(self, pk):
        try:
            w = self.klass.objects.get(pk=pk)
        except self.klass.DoesNotExist:
            raise Http404

        w_copy = copy.copy(w)
        w_copy.id = None
        w_copy.tytul_oryginalny = "[ ** KOPIA ** ]" + w_copy.tytul_oryginalny
        w_copy.slug = None
        w_copy.save()

        for wca in self.klass_autor.objects.filter(rekord=w):
            wca_copy = copy.copy(wca)
            wca_copy.id = None
            wca_copy.rekord = w_copy
            wca_copy.save()

        return reverse("admin:bpp_%s_change" % self.klass_name, args=(w_copy.pk,))


class WydawnictwoCiagleTozView(TozView):
    klass = Wydawnictwo_Ciagle
    klass_autor = Wydawnictwo_Ciagle_Autor
    klass_name = "wydawnictwo_ciagle"


class WydawnictwoZwarteTozView(TozView):
    klass = Wydawnictwo_Zwarte
    klass_autor = Wydawnictwo_Zwarte_Autor
    klass_name = "wydawnictwo_zwarte"


class PatentTozView(TozView):
    klass = Patent
    klass_autor = Patent_Autor
    klass_name = "patent"
