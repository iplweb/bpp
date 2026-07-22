import copy

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from django.db import transaction
from django.http import HttpResponseRedirect
from django.http.response import Http404
from django.views import View

from bpp.models.patent import Patent, Patent_Autor
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor
from bpp.permissions import WprowadzanieDanychRequiredMixin


class TozView(WprowadzanieDanychRequiredMixin, View):
    """Tworzy kopię ("Toż") rekordu wraz z przypisaniami autorów.

    Mutacja wykonywana WYŁĄCZNIE przez POST + CSRF. Wcześniej klonowanie
    działało na GET (``RedirectView``), co łamało kontrakt „GET jest
    bezpieczny": rekord dało się sklonować samą nawigacją/linkiem/prefetchem
    i bez ochrony CSRF. Dostęp ograniczony do redaktorów (grupa „wprowadzanie
    danych" lub superuser) — patrz ``WprowadzanieDanychRequiredMixin``.
    """

    @transaction.atomic
    def get_redirect_url(self, pk):
        try:
            w = self.klass.objects.get(pk=pk)
        except self.klass.DoesNotExist:
            raise Http404 from None

        w_copy = copy.copy(w)
        w_copy.id = None
        w_copy.tytul_oryginalny = "[ ** KOPIA ** ]" + w_copy.tytul_oryginalny
        w_copy.slug = None
        if hasattr(w_copy, "pbn_uid_id"):
            # pbn_uid to OneToOneField (unique=True) — kopia nie moze
            # wspoldzielic identyfikatora PBN z oryginalem, bo save()
            # rzuciłby IntegrityError (FD#328).
            w_copy.pbn_uid_id = None
        w_copy.save()

        for wca in self.klass_autor.objects.filter(rekord=w):
            wca_copy = copy.copy(wca)
            wca_copy.id = None
            wca_copy.rekord = w_copy
            wca_copy.save()

        return reverse(f"admin:bpp_{self.klass_name}_change", args=(w_copy.pk,))

    def post(self, request, pk):
        return HttpResponseRedirect(self.get_redirect_url(pk))


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
