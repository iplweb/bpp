import uuid
from functools import update_wrapper

from django.conf import settings
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render
from sentry_sdk import capture_exception
from templated_email import send_templated_mail

from zglos_publikacje.models import Zgloszenie_Publikacji, Zgloszenie_Publikacji_Autor
from .filters import WydzialJednostkiPierwszegoAutora
from .forms import ZwrocEmailForm

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters

from bpp.admin.helpers import MODEL_Z_OPLATA_ZA_PUBLIKACJE


class Zgloszenie_Publikacji_AutorInline(admin.StackedInline):
    model = Zgloszenie_Publikacji_Autor
    # form = Zgloszenie_Publikacji_AutorInlineForm
    # readonly_fields = ["autor", "jednostka", "dyscyplina_naukowa"]
    fields = ["autor", "jednostka", "dyscyplina_naukowa"]
    extra = 0


@admin.register(Zgloszenie_Publikacji)
class Zgloszenie_PublikacjiAdmin(admin.ModelAdmin):
    list_display = [
        "tytul_oryginalny",
        "utworzono",
        "ostatnio_zmieniony",
        "wydzial_pierwszego_autora",
        "email",
        "status",
    ]
    list_filter = [
        "status",
        "email",
        WydzialJednostkiPierwszegoAutora,
        "rodzaj_zglaszanej_publikacji",
        "rok",
    ]

    fields = (
        (
            "tytul_oryginalny",
            "rok",
            "rodzaj_zglaszanej_publikacji",
        )
        + MODEL_Z_OPLATA_ZA_PUBLIKACJE
        + (
            "email",
            "strona_www",
            "plik",
            "status",
            "przyczyna_zwrotu",
            "kod_do_edycji",
        )
    )

    inlines = [
        Zgloszenie_Publikacji_AutorInline,
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
            url(r"^(.+)/zwroc/$", wrap(self.zwroc_view), name="%s_%s_zwroc" % info),
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
                    except Exception as e:
                        capture_exception(e)

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
            "title": "Zwróć zgłoszenie %s" % obj,
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
