# -*- encoding: utf-8 -*-

import copy
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http.response import Http404
from django.views.generic import RedirectView
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor


class WydawnictwoCiagleTozView(RedirectView):

    @transaction.atomic
    def get_redirect_url(self, pk):
        try:
            w = Wydawnictwo_Ciagle.objects.get(pk=pk)
        except Wydawnictwo_Ciagle.DoesNotExist:
            raise Http404

        w_copy = copy.copy(w)
        w_copy.id = None
        w_copy.tytul_oryginalny = u'[ ** KOPIA ** ]' + w_copy.tytul_oryginalny
        w_copy.save()

        for wca in Wydawnictwo_Ciagle_Autor.objects.filter(rekord=w):
            wca_copy = copy.copy(wca)
            wca_copy.id = None
            wca_copy.rekord = w_copy
            wca_copy.save()

        return reverse("admin:bpp_wydawnictwo_ciagle_change", args=(w_copy.pk,))


