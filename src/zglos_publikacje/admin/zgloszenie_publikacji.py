import logging
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
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.http import urlencode
from django_sendfile import sendfile
from djangoql.admin import DjangoQLSearchMixin
from templated_email import send_templated_mail

from bpp.admin.core import DynamicAdminFilterMixin
from bpp.admin.helpers.fieldsets import MODEL_Z_OPLATA_ZA_PUBLIKACJE
from bpp.util import zaloguj_polkniety_wyjatek
from import_common.normalization import extract_doi_from_url
from zglos_publikacje.models import (
    Zgloszenie_Publikacji,
    Zgloszenie_Publikacji_Autor,
    Zgloszenie_Publikacji_Zalacznik,
)

from .filters import (
    DzienTygodniaFilter,
    MaPlikFilter,
    MaPrzyczyneZwrotuFilter,
    StanObslugiFilter,
    WydzialJednostkiPierwszegoAutora,
)
from .forms import ZwrocEmailForm

logger = logging.getLogger(__name__)


def _nazwa_pliku_do_pobrania(plik, oryginalna_nazwa_pliku=""):
    if oryginalna_nazwa_pliku:
        return oryginalna_nazwa_pliku
    return plik.name.rsplit("/", 1)[-1]


class Zgloszenie_Publikacji_AutorInline(admin.StackedInline):
    model = Zgloszenie_Publikacji_Autor
    fields = ["autor", "jednostka", "dyscyplina_naukowa"]
    extra = 0


class Zgloszenie_Publikacji_ZalacznikInline(admin.TabularInline):
    model = Zgloszenie_Publikacji_Zalacznik
    fields = [
        "plik_do_pobrania",
        "oryginalna_nazwa_pliku",
        "kolejnosc",
    ]
    readonly_fields = ["plik_do_pobrania", "oryginalna_nazwa_pliku"]
    extra = 0

    @admin.display(description="Plik załącznika")
    def plik_do_pobrania(self, obj):
        if not obj.pk or not obj.plik:
            return "-"

        url = reverse(
            "admin:zglos_publikacje_zgloszenie_publikacji_pobierz_zalacznik",
            args=[obj.zgloszenie_id, obj.pk],
        )
        display_name = _nazwa_pliku_do_pobrania(obj.plik, obj.oryginalna_nazwa_pliku)
        return format_html('<a href="{}">{}</a>', url, display_name)


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
        "zaimportowano",
        "zgoda_na_publikacje_pelnego_tekstu",
    ]
    list_filter = [
        StanObslugiFilter,
        "status",
        # ``RelatedOnlyFieldListFilter``, nie gołe pole: inaczej sidebar
        # dostaje ``<li>`` dla KAŻDEGO użytkownika w bazie (plus HTMX-owy
        # licznik z ``DynamicAdminFilterMixin`` do każdej pozycji).
        ("zaimportowal", admin.RelatedOnlyFieldListFilter),
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
            "pliki_do_pobrania",
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

    # Audyt domknięcia zgłoszenia importerem prac (FD#443) NIE jest polami
    # formularza — całość pokazuje panel „📥 Zaimportowane …" nad formularzem
    # (patrz ``change_view`` + ``change_form.html``). Jedno źródło prawdy:
    # dublowanie tego w ``readonly_fields`` dawało dwa linki do tego samego
    # rekordu i dwa komplety zapytań na każdy render strony.
    readonly_fields = [
        "pliki_do_pobrania",
    ]

    inlines = [
        Zgloszenie_Publikacji_AutorInline,
        Zgloszenie_Publikacji_ZalacznikInline,
    ]

    def get_queryset(self, request):
        # ``zaimportowal`` czyta panel audytu (strona zgłoszenia) — bez
        # ``select_related`` to dodatkowy SELECT na użytkownika przy każdym
        # renderze; na liście oszczędza zapytanie na wiersz przy filtrze.
        return super().get_queryset(request).select_related("zaimportowal")

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

    def change_view(self, request, object_id, form_url="", extra_context=None):
        # Udostępnij szablonowi URL importera, by przycisk „Użyj importera"
        # mógł stanąć w pasku akcji nad tabelą (blok object-tools), a nie w
        # readonly wierszu tabeli (Freshdesk #430).
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        if obj is not None:
            extra_context["importer_url"] = self.importer_url(obj)
            if obj.czy_zaimportowane:
                # Panel „📥 Zaimportowane …" nad formularzem (FD#443, §8).
                url, nazwa = self._rekord_url_i_nazwa(obj)
                extra_context["zaimportowany_rekord_url"] = url
                extra_context["zaimportowany_rekord_nazwa"] = nazwa
                sesja = self._ostatnia_sesja_importu(obj)
                extra_context["sesja_importu_url"] = (
                    self._sesja_importu_url(sesja) if sesja is not None else None
                )
        return super().change_view(request, object_id, form_url, extra_context)

    def _rekord_url_i_nazwa(self, obj):
        """``(url_admina, etykieta)`` rekordu powstałego ze zgłoszenia.

        Zwraca ``(None, None)``, gdy ``odpowiednik_w_bpp`` nie jest ustawiony
        albo wskazuje na rekord, którego nie da się już załadować (skasowany
        model / nieistniejący wiersz — GenericFK nie ma integralności).
        """
        if obj is None or obj.content_type_id is None or not obj.object_id:
            return None, None

        try:
            rekord = obj.odpowiednik_w_bpp
            if rekord is None:
                return None, None

            opts = rekord._meta
            return (
                reverse(
                    f"admin:{opts.app_label}_{opts.model_name}_change",
                    args=[rekord.pk],
                ),
                str(rekord),
            )
        except Exception:
            # Zerwany GenericFK to w adminie brak danych do pokazania, nie
            # awaria — logujemy traceback, bez alarmu Rollbara.
            zaloguj_polkniety_wyjatek(
                f"Budowanie linku do odpowiednika w BPP (zgłoszenie pk={obj.pk})",
                logger=logger,
                do_rollbar=False,
            )
            return None, None

    @staticmethod
    def _sesja_importu_url(sesja) -> str:
        return reverse(
            "admin:importer_publikacji_importsession_change", args=[sesja.pk]
        )

    @staticmethod
    def _ostatnia_sesja_importu(obj):
        """Najnowsza sesja importu związana ze zgłoszeniem albo ``None``.

        ``ImportSession.Meta.ordering`` to ``["-created"]``, więc ``first()``
        zwraca **najnowszą** sesję — i o to chodzi: gdy import był ponawiany,
        operatora interesuje ostatnie podejście, nie pierwsze.

        ``sesje_importu`` to relacja odwrotna z ``importer_publikacji``.
        ``getattr`` z wartością domyślną — relacja jest dokładana osobną
        migracją tej samej gałęzi, a admin zgłoszeń nie może się wywalić,
        gdy jej jeszcze nie ma.
        """
        manager = getattr(obj, "sesje_importu", None)
        if manager is None:
            return None
        return manager.first()

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

        if not self.has_view_permission(request, obj):
            raise Http404("Zgłoszenie nie istnieje")

        if not obj.plik:
            raise Http404("Brak pliku")

        filename = _nazwa_pliku_do_pobrania(obj.plik, obj.oryginalna_nazwa_pliku)
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

        if not self.has_view_permission(request, obj):
            raise Http404("Zgłoszenie nie istnieje")

        try:
            zalacznik = obj.zalaczniki.get(pk=zalacznik_id)
        except Zgloszenie_Publikacji_Zalacznik.DoesNotExist:
            raise Http404("Załącznik nie istnieje") from None

        if not zalacznik.plik:
            raise Http404("Brak pliku")

        filename = _nazwa_pliku_do_pobrania(
            zalacznik.plik, zalacznik.oryginalna_nazwa_pliku
        )
        return sendfile(
            request,
            zalacznik.plik.path,
            attachment=True,
            attachment_filename=filename,
        )

    @admin.display(description="Plik załącznika")
    def plik_do_pobrania(self, obj):
        """Legacy - pokazuje tylko stare pole plik."""
        if not obj.plik:
            return "-"

        url = reverse(
            "admin:zglos_publikacje_zgloszenie_publikacji_pobierz_plik",
            args=[obj.pk],
        )
        display_name = _nazwa_pliku_do_pobrania(obj.plik, obj.oryginalna_nazwa_pliku)
        return format_html(
            '<a href="{}">{}</a>',
            url,
            display_name,
        )

    @admin.display(description="Pliki")
    def pliki_do_pobrania(self, obj):
        """Wyświetla wszystkie pliki - stare pole plik + nowe załączniki."""
        parts = []

        # Stare pole plik (legacy)
        if obj.plik:
            url = reverse(
                "admin:zglos_publikacje_zgloszenie_publikacji_pobierz_plik",
                args=[obj.pk],
            )
            display_name = _nazwa_pliku_do_pobrania(
                obj.plik, obj.oryginalna_nazwa_pliku
            )
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
                    _nazwa_pliku_do_pobrania(
                        zalacznik.plik, zalacznik.oryginalna_nazwa_pliku
                    ),
                )
            )

        if not parts:
            return "-"

        return format_html_join("<br/>", "{}", ((part,) for part in parts))

    def importer_url(self, obj: Zgloszenie_Publikacji) -> str | None:
        """Zbuduj URL importera dla adresu zgłoszenia albo zwróć ``None``.

        Priorytet: jeśli z pola „Dostępna w sieci pod adresem" (lub z pola
        DOI zgłoszenia) da się wyłuskać DOI — importer z providerem CrossRef
        i wypełnionym identyfikatorem. W przeciwnym razie, jeśli adres w
        ogóle jest — importer z providerem „Pozostałe strony WWW" (import z
        ogólnej strony), z adresem w polu identyfikatora. Gdy adresu nie ma
        — ``None`` (przycisku importera nie pokazujemy).

        Zgłoszenie już domknięte importerem także zwraca ``None``: przycisk
        znika, żeby operator nie zaimportował tej samej pracy drugi raz
        (FD#443, §7 specyfikacji).
        """
        if obj.status == Zgloszenie_Publikacji.Statusy.ZAIMPORTOWANY:
            return None

        doi = extract_doi_from_url(obj.strona_www) or extract_doi_from_url(
            getattr(obj, "doi", None)
        )

        if doi:
            params = {"provider": "CrossRef", "identifier": doi}
        elif obj.strona_www:
            # Nazwa providera musi zgadzać się z WWWProvider.name.
            params = {
                "provider": "Pozostałe strony WWW",
                "identifier": obj.strona_www,
            }
        else:
            return None

        # Kontekst zgłoszenia musi przeżyć skok do importera — bez niego
        # sesja importu nie ma jak domknąć zgłoszenia (FD#443, §6 ścieżka A).
        params["zgloszenie"] = obj.pk

        return "{}?{}".format(
            reverse("importer_publikacji:index"),
            urlencode(params),
        )

    def wydzial_pierwszego_autora(self, obj: Zgloszenie_Publikacji):
        try:
            return (
                obj.zgloszenie_publikacji_autor_set.filter(
                    jednostka__skupia_pracownikow=True
                )
                .first()
                .jednostka.wydzial.nazwa
            )
        except Exception:
            # Kolumna admina — brak autora/jednostki/wydziału to często
            # oczekiwany brak danych; logujemy traceback, bez alarmu Rollbara.
            zaloguj_polkniety_wyjatek(
                f"Ustalanie wydziału pierwszego autora zgłoszenia (pk={obj.pk})",
                logger=logger,
                do_rollbar=False,
            )

    wydzial_pierwszego_autora.short_description = "Wydział pierwszego autora"
