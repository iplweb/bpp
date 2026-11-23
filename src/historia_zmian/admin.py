"""Lista wszystkich rewizji ze źródłem zmiany (FD#587) — tylko do odczytu.

Odpowiada na pytania „co zmienił agent X / import / użytkownik Y”. Z każdej
pozycji prowadzą linki do stron „Historia” zmienionych rekordów, gdzie można
porównać i przywrócić wersje.
"""

from django.contrib import admin
from django.contrib.admin.utils import quote
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html, format_html_join
from django_sendfile import sendfile

from .models import ArchiwalnyPlik, ZrodloZmiany

#: Ile rekordów rewizji pokazać w kolumnie (rewizje akcji masowych sprzed
#: FD#587 mogą obejmować setki obiektów).
MAKS_OBIEKTOW = 5


@admin.register(ZrodloZmiany)
class ZrodloZmianyAdmin(admin.ModelAdmin):
    list_display = [
        "data",
        "uzytkownik",
        "zrodlo",
        "aplikacja_nazwa",
        "komentarz",
        "obiekty",
    ]
    list_filter = ["zrodlo", "aplikacja_nazwa"]
    search_fields = [
        "rewizja__comment",
        "rewizja__user__username",
        "rewizja__version__object_repr",
        "aplikacja_nazwa",
        "aplikacja_client_id",
    ]
    date_hierarchy = "rewizja__date_created"
    list_select_related = ["rewizja__user"]
    ordering = ["-rewizja__date_created"]
    show_full_result_count = False
    # Wiersz nie prowadzi do strony wpisu: wszystko jest na liście, a linki
    # w kolumnie „zmienione rekordy” prowadzą do ich stron „Historia”.
    list_display_links = None

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("rewizja__version_set")

    @admin.display(description="data", ordering="rewizja__date_created")
    def data(self, obj):
        return obj.rewizja.date_created

    @admin.display(description="użytkownik", ordering="rewizja__user__username")
    def uzytkownik(self, obj):
        return obj.rewizja.user or "—"

    @admin.display(description="komentarz")
    def komentarz(self, obj):
        return obj.rewizja.comment

    @admin.display(description="zmienione rekordy")
    def obiekty(self, obj):
        wersje = list(obj.rewizja.version_set.all())
        linki = []
        for wersja in wersje[:MAKS_OBIEKTOW]:
            opts = wersja.content_type.model_class()
            if opts is None:
                continue
            opts = opts._meta
            try:
                url = reverse(
                    f"admin:{opts.app_label}_{opts.model_name}_history",
                    args=(quote(wersja.object_id),),
                )
            except NoReverseMatch:
                url = None
            linki.append((url, f"{opts.verbose_name}: {wersja.object_repr}"))
        html = format_html_join(
            format_html("<br>"),
            "{}",
            (
                (format_html('<a href="{}">{}</a>', url, tekst) if url else tekst,)
                for url, tekst in linki
            ),
        )
        if len(wersje) > MAKS_OBIEKTOW:
            html = format_html("{}<br>… i {} więcej", html, len(wersje) - MAKS_OBIEKTOW)
        return html

    def history_view(self, request, object_id, extra_context=None):
        # Wpis historii zmian sam nie ma historii.
        raise Http404

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


def _moze_ogladac_model(user, etykieta):
    """Czy ``user`` może oglądać model ``app_label.Model`` (``view`` albo
    ``change``, jak ``has_view_permission`` w adminie)."""
    app_label, nazwa = etykieta.lower().split(".")
    return user.has_perm(f"{app_label}.view_{nazwa}") or user.has_perm(
        f"{app_label}.change_{nazwa}"
    )


@admin.register(ArchiwalnyPlik)
class ArchiwalnyPlikAdmin(admin.ModelAdmin):
    """„Archiwum plików” — pliki, które straciły odwołanie w bazie
    (``historia_zmian.archiwum_plikow``). Tylko do odczytu, z pobieraniem.
    Z archiwum nic się nie kasuje: plik zostaje na dysku na zawsze."""

    list_display = [
        "kiedy",
        "pobierz",
        "powod",
        "rodzaj",
        "opis",
        "kto",
    ]
    list_filter = ["powod", "rodzaj"]
    search_fields = ["oryginalna_nazwa_pliku", "plik", "opis", "kto__username"]
    date_hierarchy = "kiedy"
    list_select_related = ["kto"]
    list_display_links = None
    show_full_result_count = False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        # Archiwum nie może być furtką do plików, których użytkownik nie
        # zobaczyłby u źródła (np. załączniki zgłoszeń bez uprawnień do
        # zgłoszeń): widać tylko pliki modeli, które może oglądać.
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        from .archiwum_plikow import CHRONIONE_PLIKI

        dozwolone = [
            etykieta.lower()
            for etykieta in CHRONIONE_PLIKI
            if _moze_ogladac_model(request.user, etykieta)
        ]
        return qs.filter(model_zrodlowy__in=dozwolone)

    def get_urls(self):
        from django.urls import path

        return [
            path(
                "<int:pk>/pobierz/",
                self.admin_site.admin_view(self.pobierz_view),
                name="historia_zmian_archiwalnyplik_pobierz",
            ),
            *super().get_urls(),
        ]

    @admin.display(description="plik", ordering="oryginalna_nazwa_pliku")
    def pobierz(self, obj):
        return format_html(
            '<a href="{}">⬇️ {}</a>',
            reverse("admin:historia_zmian_archiwalnyplik_pobierz", args=(obj.pk,)),
            obj,
        )

    def pobierz_view(self, request, pk):
        if not self.has_view_permission(request):
            raise PermissionDenied
        obj = self.get_queryset(request).filter(pk=pk).first()
        if obj is None or not obj.plik.storage.exists(obj.plik.name):
            raise Http404("Brak pliku w archiwum.")
        return sendfile(
            request,
            obj.plik.path,
            attachment=True,
            attachment_filename=str(obj),
        )
