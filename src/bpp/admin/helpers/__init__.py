import random
from urllib.parse import parse_qs
from urllib.parse import quote as urlquote

from django.db.models import Q
from django.forms import BaseInlineFormSet
from django.urls import reverse

from django.contrib import messages
from django.contrib.admin.utils import quote
from django.contrib.contenttypes.models import ContentType

from django.utils.html import format_html
from django.utils.safestring import mark_safe

from bpp import const


def js_openwin(url, handle, options):
    options = ",".join([f"{a}={b}" for a, b in list(options.items())])
    d = dict(url=url, handle=handle, options=options)
    return "window.open('%(url)s','\\%(handle)s','%(options)s')" % d


class LimitingFormset(BaseInlineFormSet):
    def get_queryset(self):
        if not hasattr(self, "_queryset_limited"):
            qs = super().get_queryset()
            self._queryset_limited = qs[:100]
        return self._queryset_limited


def link_do_obiektu(obj, friendly_name=None):
    opts = obj._meta
    obj_url = reverse(
        f"admin:{opts.app_label}_{opts.model_name}_change",
        args=(quote(obj.pk),),
        # current_app=self.admin_site.name,
    )
    # Add a link to the object's change form if the user can edit the obj.
    if friendly_name is None:
        friendly_name = mark_safe(obj)
    return format_html('<a href="{}">{}</a>', urlquote(obj_url), friendly_name)


def get_rekord_id_from_GET_qs(request):
    flt = request.GET.get("_changelist_filters", "?")
    data = parse_qs(flt)  # noqa
    if "rekord__id__exact" in data:
        try:
            return int(data.get("rekord__id__exact")[0])
        except (ValueError, TypeError):
            pass


def poszukaj_duplikatu_pola_www_i_ewentualnie_zmien(request, obj):
    """Sprawdza, czy w bazie są inne rekordy z takim polem public_www bądź www.
    Jeżeli są, to dokleja do tych pól hash i randomowy ciąg znaków w taki sposób, aby
    to pole NIE było zdublowane. Potrzebne to jest w sytuacji, gdy dodajemy do PBNu
    rozdziały np z PDFu który nie ma DOI ale za to jest pod jednym adresem WWW, stąd
    żeby wszystkich rozdziałów nie zakodować na jednym PBN UID -- strona WWW będzie wymuszana
    unikalna.

    Wymuszenie unikalnosci -- dokleja hash, 8 cyferek losowych, informuje o tym
    użytkownika."""
    from bpp.models.cache import Rekord

    for field, drugie in (("www", "public_www"), ("public_www", "www")):
        cur_value = getattr(obj, field)
        if cur_value is None:
            continue

        rekord_pk = None
        if obj.pk:
            rekord_pk = (ContentType.objects.get_for_model(obj).pk, obj.pk)

        qry = Rekord.objects.filter(
            Q(**{field + "__iexact": cur_value}) | Q(**{drugie + "__iexact": cur_value})
        )
        if rekord_pk is not None:
            qry = qry.exclude(pk=rekord_pk)

        new_value = None
        while qry.exists():
            new_value = (
                cur_value + "#bpp-auto-url-" + "".join(random.sample("0123456789", 7))
            )
            setattr(obj, field, new_value)

            qry = Rekord.objects.filter(
                Q(**{field + "__iexact": new_value})
                | Q(**{drugie + "__iexact": new_value})
            )
            if rekord_pk is not None:
                qry = qry.exclude(pk=rekord_pk)

        if new_value:
            messages.info(
                request,
                const.ZMIENIONO_AUTOMATYCZNIE_WARTOSC_POLA.format(
                    field=field, value=new_value
                ),
            )


def sprawdz_duplikaty_www_doi(request, obj):
    from bpp.models.cache import Rekord

    IEXACT = "__iexact"
    for field, operator, label in [
        ("www", IEXACT, const.WWW_FIELD_LABEL),
        ("public_www", IEXACT, const.PUBLIC_WWW_FIELD_LABEL),
        ("doi", IEXACT, const.DOI_FIELD_LABEL),
        ("pbn_uid_id", "", const.PBN_UID_FIELD_LABEL),
    ]:
        if not hasattr(obj, field):
            continue

        v = getattr(obj, field)
        if v in [None, ""]:
            continue

        rekord_pk = (ContentType.objects.get_for_model(obj).pk, obj.pk)

        query = Q(**{field + operator: v})

        if field == "www":
            query |= Q(public_www__iexact=v)
        elif field == "public_www":
            query |= Q(www__iexact=v)

        if Rekord.objects.filter(query).exclude(pk=rekord_pk).exists():
            messages.warning(
                request, const.ZDUBLOWANE_POLE_KOMUNIKAT.format(label=label)
            )
