import sys
import uuid
from functools import update_wrapper

import rollbar
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.db import transaction
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.utils.html import format_html
from django_sendfile import sendfile
from djangoql.admin import DjangoQLSearchMixin
from templated_email import send_templated_mail

from bpp.admin.core import DynamicAdminFilterMixin
from bpp.admin.helpers.fieldsets import MODEL_Z_OPLATA_ZA_PUBLIKACJE
from zglos_publikacje.models import (
    Zgloszenie_Publikacji,
    Zgloszenie_Publikacji_Autor,
    Zgloszenie_Publikacji_Zalacznik,
)

from .filters import (
    DzienTygodniaFilter,
    MaPlikFilter,
    MaPrzyczyneZwrotuFilter,
    WydzialJednostkiPierwszegoAutora,
)
from .forms import ZwrocEmailForm


class Zgloszenie_Publikacji_AutorInline(admin.StackedInline):
    model = Zgloszenie_Publikacji_Autor
    fields = ["autor", "jednostka", "dyscyplina_naukowa"]
    extra = 0


class Zgloszenie_Publikacji_ZalacznikInline(admin.TabularInline):
    model = Zgloszenie_Publikacji_Zalacznik
    fields = [
        "plik",
        "oryginalna_nazwa_pliku",
        "kolejnosc",
    ]
    readonly_fields = ["plik", "oryginalna_nazwa_pliku"]
    extra = 0


@admin.register(Zgloszenie_Publikacji)
class Zgloszenie_PublikacjiAdmin(
    DjangoQLSearchMixin, DynamicAdminFilterMixin, admin.ModelAdmin
):
    djangoql_completion_enabled_by_default = False
    djangoql_completion = True

    search_fields = ["email", "tytul_oryginalny", "przyczyna_zwrotu"]
    date_hierarchy = "utworzono"

    list_display = [
        "tytul_oryginalny",
        "utworzono",
        "ostatnio_zmieniony",
        "wydzial_pierwszego_autora",
        "email",
        "status",
        "zgoda_na_publikacje_pelnego_tekstu",
    ]
    list_filter = [
        "status",
        WydzialJednostkiPierwszegoAutora,
        DzienTygodniaFilter,
        "rodzaj_zglaszanej_publikacji",
        "rok",
        "zgoda_na_publikacje_pelnego_tekstu",
        MaPlikFilter,
        MaPrzyczyneZwrotuFilter,
        "utworzono",
        "ostatnio_zmieniony",
    ]

    fields = (
        (
            "tytul_oryginalny",
            "rok",
            "rodzaj_zglaszanej_publikacji",
            "forma_dostepu",
        )
        + MODEL_Z_OPLATA_ZA_PUBLIKACJE
        + (
            "email",
            "strona_www",
            "plik_do_pobrania",
            "wydawca_zgloszenia",
            "wydawca_bpp",
            "wydawca_pbn",
            "wydawnictwo_nadrzedne_tekst",
            "wydawnictwo_nadrzedne_bpp",
            "wydawnictwo_nadrzedne_pbn",
            "status",
            "przyczyna_zwrotu",
            "kod_do_edycji",
            "zgoda_na_publikacje_pelnego_tekstu",
        )
    )

    readonly_fields = ["pliki_do_pobrania"]

    inlines = [
        Zgloszenie_Publikacji_AutorInline,
        Zgloszenie_Publikacji_ZalacznikInline,
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_urls(self):
        from django.urls import re_path as url

        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)

            return update_wrapper(wrapper, view)

        info = self.model._meta.app_label, self.model._meta.model_name

        urls = [
            url(
                r"^(.+)/zwroc/$",
                wrap(self.zwroc_view),
                name=f"{info[0]}_{info[1]}_zwroc",
            ),
            url(
                r"^(.+)/pobierz_plik/$",
                wrap(self.pobierz_plik_view),
                name=f"{info[0]}_{info[1]}_pobierz_plik",
            ),
            url(
                r"^(.+)/pobierz_zalacznik/(\d+)/$",
                wrap(self.pobierz_zalacznik_view),
                name=f"{info[0]}_{info[1]}_pobierz_zalacznik",
            ),
        ]

        super_urls = super().get_urls()

        return urls + super_urls

    zwroc_view_template = (
        "admin/zglos_publikacje/zgloszenie_publikacji/zwroc_zgloszenie.html"
    )

    @transaction.atomic
    def zwroc_view(self, request, id, form_url="", extra_context=None):
        opts = Zgloszenie_Publikacji._meta
        obj = Zgloszenie_Publikacji.objects.get(pk=id)
        form_class = ZwrocEmailForm

        add = False

        if request.method == "POST":
            form = form_class(request.POST, request.FILES, instance=obj)
            form_validated = form.is_valid()
            if form_validated:
                new_object = self.save_form(request, form, change=True)
                new_object.status = Zgloszenie_Publikacji.Statusy.WYMAGA_ZMIAN
                new_object.kod_do_edycji = uuid.uuid4()
                self.save_model(request, new_object, form, not add)
                change_message = f"Rekord został zwrócony, przyczyna {form.cleaned_data['przyczyna_zwrotu']}"
                self.log_change(request, new_object, change_message)

                def _():
                    sent_okay = None
                    try:
                        send_templated_mail(
                            template_name="zwroc_zgloszenie",
                            from_email=getattr(
                                settings, "DEFAULT_FROM_EMAIL", "webmaster@localhost"
                            ),
                            headers={"reply-to": request.user.email},
                            recipient_list=[obj.email],
                            context={
                                "object": obj,
                                "site_url": request.get_host(),
                            },
                        )
                        sent_okay = True
                    except Exception:
                        rollbar.report_exc_info(sys.exc_info())

                        messages.add_message(
                            request,
                            messages.WARNING,
                            f"Z uwagi na błąd wysyłania komunikatu z powiadomieniem, użytkownik {obj.email} "
                            "nie został powiadomiony o dodaniu zgłoszenia. Prosimy wysłać e-mail ręcznie. ",
                        )

                    if sent_okay:
                        messages.add_message(
                            request,
                            messages.INFO,
                            f"Użytkownik {obj.email} został powiadomiony o zwróceniu zgłoszenia przez e-mail.",
                        )

                transaction.on_commit(_)
                return HttpResponseRedirect("../..")

        preserved_filters = self.get_preserved_filters(request)
        form_url = add_preserved_filters(
            {"preserved_filters": preserved_filters, "opts": opts}, form_url
        )

        fieldsets = [(None, {"fields": ["przyczyna_zwrotu"]})]

        adminForm = helpers.AdminForm(form_class(), fieldsets, {}, model_admin=self)

        context = {
            "title": f"Zwróć zgłoszenie {obj}",
            "has_change_permission": True,
            "has_view_permission": True,
            "has_editable_inline_admin_formsets": False,
            "has_delete_permission": False,
            "has_add_permission": False,
            "form_url": form_url,
            "adminform": adminForm,
            "opts": opts,
            "app_label": opts.app_label,
            "original": obj,
            "add": add,
            "change": True,
            "is_popup": False,
            "save_as": False,
            "show_save": False,
            "show_save_and_add_another": False,
            "show_save_and_continue": True,
        }
        context.update(extra_context or {})

        return render(request, self.zwroc_view_template, context)

    def pobierz_plik_view(self, request, id):
        """Pobierz plik załącznika przez X-Accel-Redirect (legacy)."""
        obj = self.get_object(request, id)
        if obj is None:
            raise Http404("Zgłoszenie nie istnieje")

        if not obj.plik:
            raise Http404("Brak pliku")

        # Użyj oryginalnej nazwy pliku jeśli dostępna, w przeciwnym razie UUID
        filename = obj.oryginalna_nazwa_pliku or obj.plik.name.split("/")[-1]
        return sendfile(
            request,
            obj.plik.path,
            attachment=True,
            attachment_filename=filename,
        )

    def pobierz_zalacznik_view(self, request, id, zalacznik_id):
        """Pobierz konkretny załącznik przez X-Accel-Redirect."""
        obj = self.get_object(request, id)
        if obj is None:
            raise Http404("Zgłoszenie nie istnieje")

        try:
            zalacznik = obj.zalaczniki.get(pk=zalacznik_id)
        except Zgloszenie_Publikacji_Zalacznik.DoesNotExist:
            raise Http404("Załącznik nie istnieje") from None

        return sendfile(
            request,
            zalacznik.plik.path,
            attachment=True,
            attachment_filename=zalacznik.oryginalna_nazwa_pliku,
        )

    @admin.display(description="Plik załącznika")
    def plik_do_pobrania(self, obj):
        """Legacy - pokazuje tylko stare pole plik."""
        if not obj.plik:
            return "-"
        from django.urls import reverse

        url = reverse(
            "admin:zglos_publikacje_zgloszenie_publikacji_pobierz_plik",
            args=[obj.pk],
        )
        # Wyświetl oryginalną nazwę pliku jeśli dostępna
        display_name = obj.oryginalna_nazwa_pliku or obj.plik.name.split("/")[-1]
        return format_html(
            '<a href="{}">{}</a>',
            url,
            display_name,
        )

    @admin.display(description="Pliki")
    def pliki_do_pobrania(self, obj):
        """Wyświetla wszystkie pliki - stare pole plik + nowe załączniki."""
        from django.urls import reverse

        parts = []

        # Stare pole plik (legacy)
        if obj.plik:
            url = reverse(
                "admin:zglos_publikacje_zgloszenie_publikacji_pobierz_plik",
                args=[obj.pk],
            )
            display_name = obj.oryginalna_nazwa_pliku or obj.plik.name.split("/")[-1]
            parts.append(
                format_html(
                    '<a href="{}">📄 {} (legacy)</a>',
                    url,
                    display_name,
                )
            )

        # Nowe załączniki
        for zalacznik in obj.zalaczniki.all():
            url = reverse(
                "admin:zglos_publikacje_zgloszenie_publikacji_pobierz_zalacznik",
                args=[obj.pk, zalacznik.pk],
            )
            parts.append(
                format_html(
                    '<a href="{}">📎 {}</a>',
                    url,
                    zalacznik.oryginalna_nazwa_pliku,
                )
            )

        if not parts:
            return "-"

        return format_html("<br/>".join(parts))

    def wydzial_pierwszego_autora(self, obj: Zgloszenie_Publikacji):
        try:
            return (
                obj.zgloszenie_publikacji_autor_set.filter(
                    jednostka__skupia_pracownikow=True
                )
                .first()
                .jednostka.wydzial.nazwa
            )
        except BaseException:
            pass

    wydzial_pierwszego_autora.short_description = "Wydział pierwszego autora"
