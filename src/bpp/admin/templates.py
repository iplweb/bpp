import sys
import traceback
from datetime import datetime, timedelta

from dbtemplates.admin import TemplateAdmin, TemplateAdminForm
from dbtemplates.models import Template
from dbtemplates.utils.cache import remove_cached_template
from dbtemplates.utils.template import check_template_syntax
from django.core.exceptions import ValidationError
from django.template import Context, TemplateSyntaxError
from django.template.engine import Engine
from django.template.loaders.cached import Loader as CachedLoader
from django.template.response import TemplateResponse
from django.urls import re_path as url

from django.contrib import admin, messages

from bpp.util import rebuild_instances_of_models

admin.site.unregister(Template)

ILE_OSTATNICH_PRAC = 25


class BppTemplateAdminForm(TemplateAdminForm):
    def clean_content(self):
        content = self.cleaned_data.get("content", "")

        class FakeTemplate:
            content = None

        FakeTemplate.content = content

        if not content:
            raise ValidationError(
                "Szablon nie może być pusty. Użyj np kodu {#...#} zamiast. "
            )

        valid, error = check_template_syntax(FakeTemplate)
        if not valid:
            raise ValidationError(
                f"Błąd przy próbie analizy szablonu: Proszę o korektę przed zapisaniem. Przyczyna błędu: {error}"
            )

        return content


@admin.register(Template)
class BppTemplateAdmin(TemplateAdmin):
    form = BppTemplateAdminForm

    def template_updated(self, request, obj):
        """Zresetuj cache zarówno dbtemplates, jak i CachedLoader'a"""

        remove_cached_template(obj)

        loaders = Engine.get_default().template_loaders
        for loader in loaders:
            if isinstance(loader, CachedLoader):
                key_name = loader.cache_key(obj.name)
                if key_name in loader.get_template_cache:
                    del loader.get_template_cache[key_name]
                # Jeszcze jest opcja uruchomic cl.reset(), ale na tym etapie
                # chyba nei ma takiej potrzeby.

        # Zlokalizuj wszystkie modele, korzystające z tej templatki:
        from bpp.models.szablondlaopisubibliograficznego import (
            SzablonDlaOpisuBibliograficznego,
        )

        modele = SzablonDlaOpisuBibliograficznego.objects.get_models_for_template(obj)

        if not modele:
            messages.info(
                request,
                "Żaden z modeli rekordów publikacji nie korzysta z tego szablonu, "
                "więc żaden nie będzie przebudowany",
            )
            return

        ILE_DNI = 7
        dni_temu = datetime.now() - timedelta(days=ILE_DNI)

        messages.info(
            request,
            f"Włączono przebudowę modeli - w sumie dla {len(modele)} rodzajów. Przebudowa obejmie rekordy "
            f"ostatnio zmodyfikowane w ciągu ostatnich {ILE_DNI} dni. Zmiany powinny być zauważalne "
            "po dłuższej chwili. Pozostałe rekordy zostaną przebudowane w godzinach nocnych. ",
        )
        rebuild_instances_of_models(modele, ostatnio_zmieniony__gte=dni_temu)

    def save_model(self, request, obj, form, change):
        pk = obj.pk

        super(TemplateAdmin, self).save_model(request, obj, form, change)

        if pk is not None:
            # Nie aktualizuj cache przy dodawaniu nowych rekordów.
            self.template_updated(request, obj)

    def delete_model(self, request, obj):
        super(TemplateAdmin, self).delete_model(request, obj)
        self.invalidate_cache(request, Template.objects.filter(pk=obj.pk))
        self.template_updated(request, obj)

    def get_urls(self):
        urls = super().get_urls()

        preview_urls = [
            url(
                r"^preview/$",
                self.admin_site.admin_view(self.opis_bibliograficzny_preview),
            )
            # Add here more urls if you want following same logic
        ]

        return preview_urls + urls

    # Your view definition fn
    def opis_bibliograficzny_preview(self, request):
        template = request.GET.get("template")

        from django.template import Template as DjangoTemplate

        template_okay = True
        exception = None
        lista_prac = []
        tb = None

        try:
            django_template = DjangoTemplate(template)
        except TemplateSyntaxError as e:
            template_okay = False
            exception = e
            type, value, tb = sys.exc_info()

        if template_okay:
            from bpp.models.cache import Rekord

            ostatnie_prace = Rekord.objects.all().order_by("-ostatnio_zmieniony")[
                :ILE_OSTATNICH_PRAC
            ]

            for elem in ostatnie_prace:
                context = Context({"praca": elem.original})
                lista_prac.append(django_template.render(context))

            #
        context = dict(
            self.admin_site.each_context(request),
            template=template,
            lista_prac=lista_prac,
            template_okay=template_okay,
            exception=exception,
            ile_ostatnich_prac=ILE_OSTATNICH_PRAC,
            is_popup=True,
            traceback="\n".join(traceback.format_tb(tb)),
            tytul="Szybki podgląd szablonu",
        )

        return TemplateResponse(
            request, "admin/opis_bibliograficzny_preview.html", context
        )
