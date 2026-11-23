"""Mixin historii wersji (django-reversion) dla adminów BPP.

Stawiać w MRO tuż PRZED ``CompareVersionAdmin`` (``reversion-compare``;
porównanie dwóch wersji na stronie „Historia") albo ``VersionAdmin``.
Dokłada do widoków reversion:

* zapis stanu sprzed pierwszej zmiany (rekordy sprzed włączenia
  wersjonowania nie mają wersji, więc inaczej pierwszej edycji nie dałoby
  się cofnąć),
* kontrolę typu wersji i zakresu uczelni w podglądzie/przywracaniu
  wersji — reversion odwraca rewizję ZANIM ``changeform_view`` sprawdzi
  ``get_queryset``, a dla POST przekierowanie „brak obiektu" (302)
  uznałby za udany zapis, więc bez tej kontroli personel uczelni A
  mógłby cofnąć rekord uczelni B,
* odzyskiwanie usuniętych rekordów tylko dla superużytkownika (usuniętego
  rekordu nie da się przypisać do uczelni przez queryset),
* wpisy ``LogEntry`` sprzed włączenia wersjonowania na stronie „Historia"
  (reversion pokazuje wyłącznie wersje — starsza historia by zniknęła),
* akcje masowe wykonują się BEZ wspólnej rewizji otwieranej przez
  ``changelist_view`` (przywrócenie jednego rekordu cofnęłoby wszystkie);
  oznaczone ``zapisuje_historie`` same zapisują wersję „przed” i „po”
  w osobnych rewizjach (w jednej stan „po” nadpisałby „przed”),
* zapamiętanie relacji śledzonych przez modele rejestrowane automatycznie
  (``FOLLOW_REVERSION``, do prefetchu przy hurtowym zapisie wersji),
* porównanie wersji z tą samą kontrolą zakresu uczelni co podgląd wersji
  i bez pól wyliczanych / relacji nieśledzonych (szum w diffie),
* ``po_przywroceniu_wersji`` — hook po udanym przywróceniu wersji (np.
  przebudowa drzewa jednostek).
"""

import logging
from contextlib import nullcontext
from contextvars import ContextVar

from django.contrib.admin.models import LogEntry
from django.contrib.admin.utils import unquote
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.db.models.signals import pre_save
from django.http import Http404
from reversion.models import Version
from reversion_compare.admin import CompareVersionAdmin

from bpp.wersjonowanie import (
    FOLLOW_REVERSION,
    POLA_KOSZA,
    POLA_POZA_WERSJA,
    POLA_UKRYTE_W_POROWNANIU,
    zapewnij_wersje_poczatkowa,
)

from .wersje_modele import POLA_WRAZLIWE

logger = logging.getLogger(__name__)

#: Ustawiane na czas przywracania wersji w adminie — receiver
#: ``zachowaj_pola_wrazliwe`` przepisuje wtedy pola spoza wersji (hasła,
#: sekrety) z bazy, zamiast zostawić wartości domyślne.
_przywracanie_wersji = ContextVar("przywracanie_wersji", default=False)

#: Ustawiane na czas podglądu wersji (GET ``revision_view``): formularz
#: rekordu jest wtedy tylko do odczytu — bez zapisu, bez „Usuń”, także
#: w listach powiązanych (inline'y). Przywrócenie to osobna akcja (POST).
_podglad_wersji = ContextVar("podglad_wersji", default=False)


class PrzeszkodaPrzywrocenia(Exception):
    """Przywrócenie przerwane w transakcji — ``przeszkody`` to pełne zdania
    dla użytkownika (patrz ``przeszkody_przywrocenia``)."""

    def __init__(self, przeszkody):
        super().__init__(" ".join(przeszkody))
        self.przeszkody = przeszkody


def zachowaj_pola_wrazliwe(sender, instance, raw=False, **kwargs):
    """Przy przywracaniu wersji (zapis surowy) pola z ``POLA_WRAZLIWE``
    dostają bieżące wartości z bazy: inaczej przywrócenie danych
    użytkownika wyzerowałoby mu hasło.

    To samo dotyczy pól kosza (``POLA_KOSZA``): są poza wersją, więc zapis
    surowy wpisałby ``deleted_at = NULL`` i po cichu wyjął wiersz z kosza
    z pominięciem ``restore()``. ``_przywroc_wersje`` i tak pomija pozycje
    z kosza — to druga linia obrony."""
    if not raw or not _przywracanie_wersji.get() or instance.pk is None:
        return
    pola = POLA_WRAZLIWE.get(sender._meta.label_lower, ())
    if hasattr(sender, "deleted_objects"):
        pola = (*pola, *POLA_KOSZA)
    if not pola:
        return
    biezace = sender._base_manager.filter(pk=instance.pk).values(*pola).first()
    for nazwa, wartosc in (biezace or {}).items():
        setattr(instance, nazwa, wartosc)


pre_save.connect(zachowaj_pola_wrazliwe, dispatch_uid="bpp.zachowaj_pola_wrazliwe")


def _nalezy_do(wersja, obj, menedzer):
    """Czy obiekt z ``wersja`` (śledzona relacja) należy do ``obj`` — stare
    rewizje akcji masowych obejmują wiersze wielu rekordów naraz."""
    stan = wersja.field_dict
    pole_fk = getattr(menedzer, "field", None)  # relacja odwrotna FK
    if pole_fk is not None:
        return str(stan.get(pole_fk.attname, stan.get(pole_fk.name))) == str(obj.pk)
    # GenericRelation: menedżer zna nazwy pól object_id / content_type.
    return str(stan.get(menedzer.object_id_field_name)) == str(obj.pk) and str(
        stan.get(menedzer.content_type_field_name + "_id", "")
        or stan.get(menedzer.content_type_field_name)
    ) == str(menedzer.content_type.pk)


def _obiekt_nalezy_do(biezacy, obj, menedzer):
    """Czy BIEŻĄCY obiekt z bazy (pozycja listy) należy do ``obj``."""
    pole_fk = getattr(menedzer, "field", None)  # relacja odwrotna FK
    if pole_fk is not None:
        return getattr(biezacy, pole_fk.attname) == obj.pk
    return str(getattr(biezacy, menedzer.object_id_field_name)) == str(
        obj.pk
    ) and getattr(biezacy, menedzer.content_type_field_name + "_id") == (
        menedzer.content_type.pk
    )


def podepnij_historie_wersji(site):
    """Modelom z ``MODELE_Z_HISTORIA`` zarejestrowanym w ``site`` bez historii
    wersji podmień klasę admina na ``z_historia_wersji(klasa)``.

    Wołane raz, po autodiscover (``BppAdminConfig.ready``) — dzięki temu
    słowniki i konfiguracja (także z pakietów zewnętrznych) nie wymagają
    zmian w swoich klasach admina."""
    from .wersje_modele import MODELE_Z_HISTORIA

    for model, model_admin in list(site._registry.items()):
        etykieta = getattr(getattr(model, "_meta", None), "label_lower", None)
        if etykieta not in MODELE_Z_HISTORIA:
            continue
        if isinstance(model_admin, HistoriaWersjiMixin):
            continue
        if etykieta == "dbtemplates.template":
            continue  # własny VersionAdmin dbtemplates z porównaniem
        klasa = z_historia_wersji(type(model_admin))
        site._registry[model] = klasa(model, site)


def z_historia_wersji(klasa_admina):
    """Klasa admina z historią wersji: ``klasa_admina`` + ``HistoriaWersjiMixin``
    + ``CompareVersionAdmin`` (gdy już ją ma — bez zmian)."""
    if issubclass(klasa_admina, HistoriaWersjiMixin):
        return klasa_admina
    return type(
        klasa_admina.__name__,
        (klasa_admina, HistoriaWersjiMixin, CompareVersionAdmin),
        {"__module__": klasa_admina.__module__},
    )


#: Pola pomijane w porównaniu wersji w każdym modelu — zmieniają się przy
#: każdym zapisie albo są techniczne, więc tylko zaśmiecałyby diff.
POLA_POZA_POROWNANIEM = (
    "ostatnio_zmieniony",
    "utworzono",
    "slug",
    "legacy_data",
    "lft",
    "rght",
    "tree_id",
    "level",
)


class HistoriaWersjiMixin:
    # Własny szablon historii BPP (``reversion/object_history.html``), także
    # pod ``CompareVersionAdmin``, który domyślnie podstawia swój.
    object_history_template = "reversion/object_history.html"
    # Zwykła lista rekordów — bez przycisku „Odzyskaj usunięte" z reversion:
    # modele BPP mają kosz (odzyskiwanie z wersji ominęłoby ``restore()``),
    # a sam widok i tak jest tylko dla superużytkownika.
    change_list_template = None

    @property
    def compare_exclude(self):
        """Pola pomijane w porównaniu wersji: wyliczane, spoza wersji,
        relacje nieśledzone (reversion-compare przeglądałby np. wszystkie
        publikacje źródła) i m2m przez własne tabele (autorzy są w
        ``autorzy_set``)."""
        opts = self.model._meta
        sledzone = set(FOLLOW_REVERSION.get(self.model, ()))
        wykluczone = (
            set(POLA_POZA_POROWNANIEM)
            | set(POLA_POZA_WERSJA.get(self.model, POLA_KOSZA))
            # Stare wersje (sprzed wyłączenia) mogą jeszcze nieść sekrety,
            # a sekrety integracji uczelni są w wersjach celowo (zaszyfrowane).
            | set(POLA_WRAZLIWE.get(self.model._meta.label_lower, ()))
            | set(POLA_UKRYTE_W_POROWNANIU.get(self.model._meta.label_lower, ()))
        )
        for relacja in opts.related_objects:
            if relacja.get_accessor_name() not in sledzone:
                wykluczone.add(relacja.name)
        for pole in opts.many_to_many:
            through = getattr(pole.remote_field, "through", None)
            if through is None or not through._meta.auto_created:
                wykluczone.add(pole.name)
        return tuple(wykluczone)

    def compare_view(self, request, object_id, extra_context=None):
        """Porównanie dwóch wersji rekordu.

        Własna implementacja zamiast ``BaseCompareVersionAdmin.compare_view``:
        reversion-compare szuka rekordu zwykłym menedżerem modelu (bez
        rekordów z kosza → 404) i nie sprawdza uprawnień ani zakresu uczelni
        (``admin_view`` wpuszcza każdego członka personelu). Tu rekord bierze
        ``get_object`` (dla modeli z koszem — także z kosza), więc wersje
        rekordu z kosza da się przeglądać i porównywać (przywracać — nie)."""
        from django.contrib.admin.utils import quote
        from django.shortcuts import get_object_or_404, render
        from django.urls import reverse
        from reversion_compare.forms import SelectDiffForm

        obj = self.get_object(request, unquote(object_id))
        if obj is None:
            raise Http404("Brak takiego rekordu w zakresie Twojej uczelni.")
        if not self.has_view_or_change_permission(request, obj):
            raise PermissionDenied
        form = SelectDiffForm(request.GET)
        if not form.is_valid():
            raise Http404("Niepoprawne numery wersji do porównania.")
        id1, id2 = sorted(
            (form.cleaned_data["version_id1"], form.cleaned_data["version_id2"])
        )
        wersje = Version.objects.get_for_object(obj).select_related("revision__user")
        wersja1 = get_object_or_404(wersje, pk=id1)
        wersja2 = get_object_or_404(wersje, pk=id2)
        nastepna = wersje.filter(pk__gt=id2).order_by("pk").first()
        poprzednia = wersje.filter(pk__lt=id1).order_by("-pk").first()

        opts = self.model._meta
        nazwa = f"admin:{opts.app_label}_{opts.model_name}"
        context = {
            **self.admin_site.each_context(request),
            "opts": opts,
            "app_label": opts.app_label,
            "title": f"Porównanie wersji: {obj}",
            "original": obj,
            "compare_data": [
                *self._wiersz_kosza(obj, wersja1, wersja2),
                *self._porownanie_jak_w_formularzu(request, obj, wersja1, wersja2),
            ],
            "version1": wersja1,
            "version2": wersja2,
            "wersje_porownania": [
                (wersja1, "Wersja starsza", "bpp-wersja-a"),
                (wersja2, "Wersja nowsza", "bpp-wersja-b"),
            ],
            "aktualna_wersja_pk": self._aktualna_wersja_pk(str(obj.pk)),
            "najstarsza_wersja_pk": wersje.order_by("pk")
            .values_list("pk", flat=True)
            .first(),
            "przywroc_nowsza_url": reverse(
                f"{nazwa}_revision", args=(quote(wersja2.object_id), wersja2.pk)
            ),
            "changelist_url": reverse(f"{nazwa}_changelist"),
            "history_url": reverse(f"{nazwa}_history", args=(quote(obj.pk),)),
            "save_url": reverse(
                f"{nazwa}_revision", args=(quote(wersja1.object_id), wersja1.pk)
            ),
            **self._stan_kosza(request, obj),
        }
        if nastepna is not None:
            context["next_url"] = f"?version_id1={wersja2.pk}&version_id2={nastepna.pk}"
        if poprzednia is not None:
            context["prev_url"] = (
                f"?version_id1={poprzednia.pk}&version_id2={wersja1.pk}"
            )
        context.update(extra_context or {})
        # Własna nazwa szablonu: nadpisanie „reversion-compare/compare.html”
        # psuło porównanie adminów, które używają widoku biblioteki (np.
        # szablony dbtemplates — inny kształt danych).
        return render(request, "reversion/porownanie_wersji.html", context)

    def _aktualna_wersja_pk(self, object_id):
        """Numer najnowszej zapisanej wersji rekordu — to jego stan obecny
        (każdy zapis tworzy wersję). ``None``, gdy rekord nie ma wersji."""
        return (
            Version.objects.get_for_object_reference(self.model, object_id)
            .order_by("-pk")
            .values_list("pk", flat=True)
            .first()
        )

    def _tresc_jak_aktualna(self, obj, wersja, aktualna_pk):
        """Czy ``wersja`` ma tę samą treść co wersja aktualna (np. stan, do
        którego rekord właśnie przywrócono — przywrócenie tworzy NOWĄ wersję
        o identycznej treści). Wtedy formularz nie może udawać „wcześniejszej
        wersji”, bo zapis niczego nie zmieni."""
        if aktualna_pk is None:
            return False
        from .porownanie_wersji import porownaj_wersje

        aktualna = Version.objects.select_related("revision").get(pk=aktualna_pk)
        return not porownaj_wersje(
            self.model, obj, wersja, aktualna, self.compare_exclude
        )

    def _wiersz_kosza(self, obj, wersja1, wersja2):
        """Wiersz „Kosz” w porównaniu wersji. Stan kosza NIE jest częścią
        danych wersji (pola kosza są celowo wyłączone), więc bez tego
        porównanie wersji sprzed i po przeniesieniu do kosza pokazywałoby
        „brak różnic”. Stan i zdarzenia odczytujemy z rewizji kosza
        (komentarze z ``receivers/soft_delete.py``)."""
        if not hasattr(self.model, "deleted_objects"):
            return []
        from django.utils import formats, timezone
        from django.utils.html import format_html, format_html_join

        from bpp.receivers.soft_delete import (
            KOMENTARZ_WERSJI_KOSZ,
            KOMENTARZ_WERSJI_PRZYWROCENIE,
        )

        zdarzenia = [
            v
            for v in Version.objects.get_for_object(obj)
            .select_related("revision__user")
            .order_by("pk")
            if v.revision.comment.startswith(
                (KOMENTARZ_WERSJI_KOSZ, KOMENTARZ_WERSJI_PRZYWROCENIE)
            )
        ]

        def stan(wersja):
            wczesniejsze = [z for z in zdarzenia if z.pk <= wersja.pk]
            w_koszu = bool(wczesniejsze) and wczesniejsze[
                -1
            ].revision.comment.startswith(KOMENTARZ_WERSJI_KOSZ)
            return "🗑️ w koszu" if w_koszu else "poza koszem"

        miedzy = [z for z in zdarzenia if wersja1.pk < z.pk <= wersja2.pk]
        if not miedzy and stan(wersja1) == stan(wersja2):
            return []

        def opis(z):
            kto = z.revision.user or "system"
            kiedy = formats.date_format(
                timezone.localtime(z.revision.date_created), "j E Y, H:i"
            )
            ikona = "🗑️" if z.revision.comment.startswith(KOMENTARZ_WERSJI_KOSZ) else "♻️"
            return (ikona, z.revision.comment, kiedy, kto)

        return [
            {
                "etykieta": "Kosz",
                "stare": stan(wersja1),
                "zmiana": format_html(
                    "<ul>{}</ul>",
                    format_html_join(
                        "",
                        '<li>{} {} <span class="bpp-przygaszony">— {}, {}</span></li>',
                        (opis(z) for z in miedzy),
                    ),
                ),
                "nowe": stan(wersja2),
                "lista": False,
            }
        ]

    def _stan_kosza(self, request, obj):
        """Kontekst dla stron historii rekordu z kosza: czy jest w koszu,
        od kiedy i — gdy użytkownik może przywracać — adres przycisku
        „♻️ Przywróć z kosza” (``BppSoftDeleteAdminMixin``)."""
        if obj is None or getattr(obj, "deleted_at", None) is None:
            return {"rekord_w_koszu": False}
        stan = {"rekord_w_koszu": True, "w_koszu_od": obj.deleted_at}
        moze = getattr(self, "moze_przywracac", None)
        if moze is not None and moze(request):
            from django.urls import reverse

            stan["kosz_przywroc_url"] = reverse(
                f"admin:{self._nazwa_url_przywroc()}", args=[obj.pk]
            )
        return stan

    def _kolejnosc_pol_formularza(self, request, obj):
        """{model: [nazwy pól]} w kolejności z formularza admina — rekordu
        (``fieldsets``) i jego inline'ów (autorzy itp.)."""
        from django.contrib.admin.utils import flatten_fieldsets

        kolejnosc = {}
        try:
            kolejnosc[self.model] = flatten_fieldsets(self.get_fieldsets(request, obj))
            for inline in self.get_inline_instances(request, obj):
                kolejnosc[inline.model] = flatten_fieldsets(
                    inline.get_fieldsets(request, obj)
                )
        except (AttributeError, KeyError, TypeError, ValueError):
            # Nietypowy formularz (np. dynamiczne pola) — porównanie zostaje
            # w kolejności z modelu; nie blokujemy podglądu historii.
            logger.exception("Brak kolejności pól formularza dla %s", self.model)
        return kolejnosc

    def _porownanie_jak_w_formularzu(self, request, obj, version1, version2):
        from .porownanie_wersji import porownaj_wersje

        return porownaj_wersje(
            self.model,
            obj,
            version1,
            version2,
            self.compare_exclude,
            kolejnosc=self._kolejnosc_pol_formularza(request, obj),
        )

    def compare(self, obj, version1, version2):
        """Czytelne porównanie (``porownanie_wersji``) zamiast diffu
        reversion-compare. Zwraca (wiersze, „czy są pola nieśledzone”)."""
        from .porownanie_wersji import porownaj_wersje

        return (
            porownaj_wersje(self.model, obj, version1, version2, self.compare_exclude),
            False,
        )

    def po_przywroceniu_wersji(self, request, obj):
        """Hook po przywróceniu wersji ``obj`` — wołany w tej samej
        transakcji co przywrócenie (błąd cofa całość). Domyślnie nic nie
        robi."""

    def zablokuj_przed_przywroceniem(self):
        """Wołane na początku transakcji przywracania, przed ponownym
        sprawdzeniem ``przeszkody_przywrocenia``. Domyślnie nic; admini,
        których przeszkody zależą od innych wierszy (drzewo jednostek),
        blokują tu te wiersze."""

    def przeszkody_przywrocenia(self, obj, wersja):
        """Powody, dla których ``wersja`` rekordu ``obj`` nie może zostać
        przywrócona (pełne zdania dla użytkownika; pusta lista = można).
        Domyślnie brak — nadpisują admini z regułami spójności (np. drzewo
        jednostek)."""
        return []

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if request.method == "POST":
            zapewnij_wersje_poczatkowa(self.get_object(request, unquote(object_id)))
        return super().change_view(request, object_id, form_url, extra_context)

    def revision_view(self, request, object_id, version_id, extra_context=None):
        obj = self.get_object(request, unquote(object_id))
        if obj is None:
            raise Http404("Brak takiego rekordu w zakresie Twojej uczelni.")
        # Soft-delete: przywrócenie wersji zapisuje CAŁY obiekt z wersji
        # (``DeserializedObject.save()``), więc pola kosza wracają do
        # wartości domyślnych i rekord po cichu wychodzi z kosza — z
        # pominięciem ``restore()`` (guard, SoftDeleteLog, kolejka PBN).
        # Najpierw przywróć z kosza, potem cofaj wersje.
        if getattr(obj, "deleted_at", None) is not None:
            from django.contrib import messages
            from django.contrib.admin.utils import quote
            from django.http import HttpResponseRedirect
            from django.urls import reverse

            self.message_user(
                request,
                "🗑️ Rekord jest w koszu — wcześniejsze wersje można przeglądać "
                "i porównywać, ale przywrócić dopiero po wyjęciu rekordu "
                "z kosza („♻️ Przywróć z kosza”).",
                level=messages.WARNING,
            )
            opts = self.model._meta
            return HttpResponseRedirect(
                reverse(
                    f"admin:{opts.app_label}_{opts.model_name}_history",
                    args=(quote(obj.pk),),
                )
            )
        # reversion szuka wersji po pk i object_id, ale NIE po typie modelu —
        # bez tego przez URL autora dałoby się cofnąć rewizję innego modelu
        # (np. uczelni) o tym samym numerze ID.
        if (
            not Version.objects.get_for_model(self.model)
            .filter(pk=version_id, object_id=unquote(object_id))
            .exists()
        ):
            raise Http404("Brak takiej wersji tego rekordu.")
        wersja = Version.objects.select_related("revision").get(pk=version_id)
        aktualna_pk = self._aktualna_wersja_pk(unquote(object_id))
        bez_zmian = wersja.pk == aktualna_pk or self._tresc_jak_aktualna(
            obj, wersja, aktualna_pk
        )
        if request.method == "POST":
            return self._przywroc_wersje(request, obj, wersja, bez_zmian)
        extra_context = {
            "zmiany_powiazanych": self._zmiany_powiazanych(obj, version_id),
            "wersja_podgladu": wersja,
            "wersja_aktualna": wersja.pk == aktualna_pk,
            "wersja_jak_aktualna": wersja.pk != aktualna_pk and bez_zmian,
            "konflikty_przywrocenia": (
                konflikty := self._konflikty_przywrocenia(obj, wersja)
            ),
            "przeszkody_przywrocenia": (
                przeszkody := self.przeszkody_przywrocenia(obj, wersja)
            ),
            "pokaz_przywroc": not bez_zmian
            and not konflikty
            and not przeszkody
            and self.has_change_permission(request, obj),
            **(extra_context or {}),
        }
        # Podgląd: reversion odtwarza wersję w transakcji wycofywanej po
        # wyrenderowaniu strony i pokazuje formularz rekordu — u nas tylko
        # do odczytu (``_podglad_wersji``).
        przywracanie = _przywracanie_wersji.set(True)
        podglad = _podglad_wersji.set(True)
        try:
            return super().revision_view(request, object_id, version_id, extra_context)
        finally:
            _podglad_wersji.reset(podglad)
            _przywracanie_wersji.reset(przywracanie)

    def _wersje_rekordu_w_rewizji(self, obj, wersja):
        """``wersja`` + wersje śledzonych pozycji (autorzy, granty, pliki…)
        należących do TEGO rekordu. Stare rewizje akcji masowych obejmują
        wiele rekordów naraz — przywracamy tylko ten jeden."""
        wynik = [wersja]
        pozostale = list(
            wersja.revision.version_set.exclude(pk=wersja.pk).select_related(
                "content_type"
            )
        )
        for akcesor in FOLLOW_REVERSION.get(self.model, ()):
            menedzer = getattr(obj, akcesor)
            wynik.extend(
                v
                for v in pozostale
                if v.content_type.model_class() is menedzer.model
                and _nalezy_do(v, obj, menedzer)
            )
        return wynik

    @staticmethod
    def _pozycje_w_koszu(wersje):
        """Wersje pozycji list (np. plików repozytorium), których wiersz jest
        TERAZ w koszu. Przywrócenie wersji ich NIE odtwarza: zapis surowy
        wyjąłby je z kosza z pominięciem ``restore()`` — plik usunięty np.
        po omyłkowym udostępnieniu wróciłby z dawnym trybem dostępu.
        Zwraca ``{(content_type_id, object_id): object_repr}``."""
        wg_modelu = {}
        for v in wersje:
            model = v.content_type.model_class()
            if hasattr(model, "deleted_objects") and v.object_id.isdigit():
                wg_modelu.setdefault(model, []).append(v)
        wynik = {}
        for model, lista in wg_modelu.items():
            w_koszu = set(
                model._base_manager.filter(
                    pk__in=[int(v.object_id) for v in lista],
                    deleted_at__isnull=False,
                ).values_list("pk", flat=True)
            )
            for v in lista:
                if int(v.object_id) in w_koszu:
                    wynik[(v.content_type_id, v.object_id)] = v.object_repr
        return wynik

    def _konflikty_przywrocenia(self, obj, wersja):
        """Pozycje list z ``wersja``, które w bazie należą TERAZ do innego
        rekordu — np. wiersz autora przeniesiony w osobnym adminie autorstw
        z tej publikacji do innej. Przywrócenie zapisałoby ten sam wiersz ze
        starym rekordem nadrzędnym, czyli po cichu zabrało autora tamtej
        publikacji. Zwraca opisy takich pozycji (pusta lista = brak)."""
        konflikty = []
        for akcesor in FOLLOW_REVERSION.get(self.model, ()):
            menedzer = getattr(obj, akcesor)
            model = menedzer.model
            wersje = [
                v
                for v in self._wersje_rekordu_w_rewizji(obj, wersja)[1:]
                if v.content_type.model_class() is model
            ]
            biezace = model._base_manager.in_bulk([v.object_id for v in wersje])
            for v in wersje:
                biezacy = (
                    biezace.get(int(v.object_id)) if v.object_id.isdigit() else None
                )
                if biezacy is not None and not _obiekt_nalezy_do(
                    biezacy, obj, menedzer
                ):
                    konflikty.append(v.object_repr)
        return konflikty

    def _przywroc_wersje(self, request, obj, wersja, bez_zmian):
        """Przywróć ``wersja`` rekordu ``obj`` (przycisk „♻️ Przywróć tę
        wersję”). NIE jest to zapis formularza z podglądu — odtwarzamy
        dokładnie zapisaną wersję: rekord i jego śledzone listy (pozycje
        dodane później są usuwane), potem zwykły ``save()`` (denormy, MPTT,
        data zmiany), przeliczenie punktacji i nowa rewizja w historii."""
        from django.contrib import messages
        from django.contrib.admin.utils import quote
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        from django.utils import formats, timezone
        from django.utils.html import format_html

        if not self.has_change_permission(request, obj):
            raise PermissionDenied
        opts = self.model._meta
        nazwa = f"admin:{opts.app_label}_{opts.model_name}"
        data = formats.date_format(
            timezone.localtime(wersja.revision.date_created), "j E Y, H:i"
        )
        if bez_zmian:
            self.message_user(
                request,
                f"Wersja z {data} ma taką samą treść jak obecny stan rekordu — "
                "nic nie zmieniono.",
                level=messages.INFO,
            )
            return HttpResponseRedirect(
                reverse(f"{nazwa}_history", args=(quote(obj.pk),))
            )

        historia = HttpResponseRedirect(
            reverse(f"{nazwa}_history", args=(quote(obj.pk),))
        )
        zmienione = self._zmienione_przy_przywroceniu(obj, wersja)
        konflikty = self._konflikty_przywrocenia(obj, wersja)
        if konflikty:
            self.message_user(
                request,
                "Nie przywrócono wersji: te pozycje należą teraz do innego "
                f"rekordu: {'; '.join(konflikty)}. Popraw je ręcznie albo "
                "najpierw przenieś je z powrotem.",
                level=messages.ERROR,
            )
            return historia
        przeszkody = self.przeszkody_przywrocenia(obj, wersja)
        if przeszkody:
            self.message_user(
                request,
                f"Nie przywrócono wersji: {' '.join(przeszkody)}",
                level=messages.ERROR,
            )
            return historia

        wersje = self._wersje_rekordu_w_rewizji(obj, wersja)
        w_koszu = self._pozycje_w_koszu(wersje[1:])
        do_przywrocenia = [
            v for v in wersje if (v.content_type_id, v.object_id) not in w_koszu
        ]
        komentarz = f"Przywrócono wersję z {data}."
        if zmienione:
            komentarz += f" Zmieniono: {', '.join(zmienione)}."
        if w_koszu:
            komentarz += (
                " Pominięto pozycje usunięte do kosza (nie zostały "
                f"przywrócone): {', '.join(sorted(w_koszu.values()))}."
            )

        token = _przywracanie_wersji.set(True)
        try:
            swiezy = self._zapisz_przywrocenie(
                request, obj, wersje, do_przywrocenia, komentarz
            )
        except PrzeszkodaPrzywrocenia as e:
            self.message_user(
                request,
                f"Nie przywrócono wersji: {' '.join(e.przeszkody)}",
                level=messages.ERROR,
            )
            return historia
        except IntegrityError:
            # Np. dwóch autorów zamienionych miejscami (te same wiersze,
            # zamienione osoby) — unikalność nie przepuści stanu pośredniego.
            # Transakcja jest cofnięta w całości, rekord bez zmian.
            logger.warning(
                "Przywrócenie wersji %s rekordu %s naruszyło ograniczenie bazy",
                wersja.pk,
                obj.pk,
                exc_info=True,
            )
            self.message_user(
                request,
                "Nie przywrócono wersji: stan z tej wersji koliduje z obecnymi "
                "danymi (np. powtórzony autor albo kolejność na liście autorów). "
                "Rekord pozostał bez zmian — popraw go ręcznie w formularzu.",
                level=messages.ERROR,
            )
            return historia
        finally:
            _przywracanie_wersji.reset(token)
        self.log_change(request, swiezy, komentarz)

        url = reverse(f"{nazwa}_change", args=(quote(swiezy.pk),))
        self.message_user(
            request,
            format_html(
                '♻️ Przywrócono wersję z {} rekordu „<a href="{}">{}</a>”.{}',
                data,
                url,
                swiezy,
                f" Zmieniono: {', '.join(zmienione)}." if zmienione else "",
            ),
            level=messages.SUCCESS,
        )
        if w_koszu:
            self.message_user(
                request,
                "🗑️ Nie przywrócono pozycji usuniętych do kosza: "
                f"{', '.join(sorted(w_koszu.values()))}. Przywracanie wersji "
                "nie wyjmuje niczego z kosza — jeśli plik ma wrócić, przywróć "
                "go w formularzu rekordu (sekcja „pliki repozytorium w koszu”).",
                level=messages.WARNING,
            )
        return HttpResponseRedirect(url)

    def _zapisz_przywrocenie(self, request, obj, wersje, do_przywrocenia, komentarz):
        """Zapis przywrócenia: rekord, listy, rewizja, punktacja i hook — w
        JEDNEJ transakcji. Błąd przy przeliczaniu punktacji cofa też samo
        przywrócenie; inaczej rekord miałby już treść wersji przy pustej
        punktacji, a ponowna próba trafiłaby w gałąź „bez zmian” i nic by
        nie przeliczyła. Zwraca świeżo zapisany rekord."""
        import reversion
        from django.db import transaction

        from bpp.models.sloty.core import IPunktacjaCacher

        with transaction.atomic(), self.create_revision(request):
            # Kontrola przeszkód jeszcze raz, już pod blokadą: pierwsza
            # (przed transakcją) mogła się zdezaktualizować przez równoległy
            # zapis — np. dwa przywrócenia jednostek A pod B i B pod A.
            self.zablokuj_przed_przywroceniem()
            przeszkody = self.przeszkody_przywrocenia(obj, wersje[0])
            if przeszkody:
                raise PrzeszkodaPrzywrocenia(przeszkody)
            # Najpierw usuń pozycje list dopisane po tej wersji (pokazane
            # w podglądzie jako „Zostaną usunięte”), DOPIERO potem odtwórz
            # wersję: autor usunięty i dodany ponownie ma nowy wiersz, który
            # zajmuje unikalne (rekord, autor, typ odpowiedzialności) —
            # odtworzenie starego wiersza przed jego usunięciem kończyło się
            # błędem bazy. ``wersje`` obejmuje też pozycje z kosza: nie ma ich
            # w ``menedzer.all()``, więc i tak nie są tu usuwane.
            w_wersji = {(v.content_type_id, v.object_id) for v in wersje}
            for akcesor in FOLLOW_REVERSION.get(self.model, ()):
                menedzer = getattr(obj, akcesor)
                ct = ContentType.objects.get_for_model(menedzer.model)
                for pozycja in menedzer.all():
                    if (ct.pk, str(pozycja.pk)) not in w_wersji:
                        pozycja.delete()
            for v in do_przywrocenia:
                v.revert()
            swiezy = self.model._default_manager.get(pk=obj.pk)
            swiezy.save()
            reversion.add_to_revision(swiezy)
            reversion.set_comment(komentarz)

            cacher = IPunktacjaCacher(swiezy)
            if cacher.canAdapt():
                cacher.removeEntries()
                cacher.rebuildEntries()
            self.po_przywroceniu_wersji(request, swiezy)
        return swiezy

    def _zmienione_przy_przywroceniu(self, obj, wersja):
        """Etykiety pól i list, które przywrócenie ``wersja`` zmieni względem
        wersji aktualnej — to samo porównanie co na stronie „Porównanie
        wersji”, żeby wpis w historii mówił, CO wróciło, a nie tylko skąd."""
        from .porownanie_wersji import porownaj_wersje

        aktualna_pk = self._aktualna_wersja_pk(str(obj.pk))
        if aktualna_pk is None:
            return []
        aktualna = Version.objects.select_related("revision").get(pk=aktualna_pk)
        return [
            wiersz["etykieta"]
            for wiersz in porownaj_wersje(
                self.model, obj, aktualna, wersja, self.compare_exclude
            )
        ]

    # --- podgląd wersji tylko do odczytu --------------------------------

    def has_change_permission(self, request, obj=None):
        if _podglad_wersji.get():
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if _podglad_wersji.get():
            return False
        return super().has_delete_permission(request, obj)

    def get_inline_instances(self, request, obj=None):
        instancje = super().get_inline_instances(request, obj)
        if _podglad_wersji.get():
            for inline in instancje:
                inline.has_add_permission = lambda *args, **kwargs: False
                inline.has_change_permission = lambda *args, **kwargs: False
                inline.has_delete_permission = lambda *args, **kwargs: False
        return instancje

    def _zmiany_powiazanych(self, obj, version_id):
        """Co przywrócenie wersji zrobi ze śledzonymi listami rekordu
        (autorzy, granty, pliki…): które pozycje zostaną usunięte (dopisane
        po tej wersji), a które przywrócone (usunięte po niej). Pozycje,
        które są teraz w koszu, NIE wracają — pokazujemy je osobno.
        Pokazywane w formularzu przywracania, ZANIM użytkownik zapisze."""
        wersja = Version.objects.select_related("revision").get(pk=version_id)
        wersje = self._wersje_rekordu_w_rewizji(obj, wersja)[1:]
        w_koszu = self._pozycje_w_koszu(wersje)
        wynik = []
        for akcesor in FOLLOW_REVERSION.get(self.model, ()):
            menedzer = getattr(obj, akcesor)
            model = menedzer.model
            biezace = {str(o.pk): str(o) for o in menedzer.all()}
            w_wersji = {}
            pominiete = []
            for v in wersje:
                if v.content_type.model_class() is not model:
                    continue
                if (v.content_type_id, v.object_id) in w_koszu:
                    pominiete.append(v.object_repr)
                else:
                    w_wersji[v.object_id] = v.object_repr
            usuniete = [biezace[k] for k in biezace.keys() - w_wersji.keys()]
            przywrocone = [w_wersji[k] for k in w_wersji.keys() - biezace.keys()]
            if usuniete or przywrocone or pominiete:
                wynik.append(
                    {
                        "nazwa": model._meta.verbose_name_plural,
                        "usuniete": sorted(usuniete),
                        "przywrocone": sorted(przywrocone),
                        "w_koszu": sorted(pominiete),
                    }
                )
        return wynik

    def recoverlist_view(self, request, extra_context=None):
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().recoverlist_view(request, extra_context)

    def recover_view(self, request, version_id, extra_context=None):
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().recover_view(request, version_id, extra_context)

    def history_view(self, request, object_id, extra_context=None):
        context = {
            "historia_sprzed_wersjonowania": self._historia_sprzed_wersjonowania(
                unquote(object_id)
            ),
            **self._stan_kosza(request, self.get_object(request, unquote(object_id))),
            "aktualna_wersja_pk": self._aktualna_wersja_pk(unquote(object_id)),
            "najstarsza_wersja_pk": Version.objects.get_for_object_reference(
                self.model, unquote(object_id)
            )
            .order_by("pk")
            .values_list("pk", flat=True)
            .first(),
        }
        context.update(extra_context or {})
        return super().history_view(request, object_id, context)

    def _historia_sprzed_wersjonowania(self, object_id):
        """``LogEntry`` starsze niż najstarsza wersja (albo wszystkie, gdy
        rekord nie ma jeszcze wersji). Nowsze zmiany są już w wersjach —
        pokazanie ich drugi raz dublowałoby wpisy."""
        wpisy = LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(self.model),
            object_id=str(object_id),
        ).select_related("user")
        najstarsza = (
            Version.objects.get_for_object_reference(self.model, object_id)
            .order_by("revision__date_created")
            .values_list("revision__date_created", flat=True)
            .first()
        )
        if najstarsza is not None:
            wpisy = wpisy.filter(action_time__lt=najstarsza)
        return list(wpisy.order_by("-action_time"))

    def reversion_register(self, model, **kwargs):
        FOLLOW_REVERSION.setdefault(model, tuple(kwargs.get("follow", ())))
        if hasattr(model, "deleted_objects"):
            # Pola kosza nie wchodzą do wersji (patrz ``POLA_KOSZA``).
            kwargs["exclude"] = (*kwargs.get("exclude", ()), *POLA_KOSZA)
        wrazliwe = POLA_WRAZLIWE.get(model._meta.label_lower, ())
        if wrazliwe:
            kwargs["exclude"] = (*kwargs.get("exclude", ()), *wrazliwe)
        POLA_POZA_WERSJA.setdefault(model, tuple(kwargs.get("exclude", ())))
        super().reversion_register(model, **kwargs)

    def create_revision(self, request):
        # Akcje masowe NIE dostają wspólnej rewizji z ``changelist_view``:
        # przywrócenie wersji odwraca całą rewizję, więc cofnięcie jednego
        # rekordu cofnęłoby po cichu wszystkie zmienione tą samą akcją (także
        # spoza uczelni użytkownika — kontrola zakresu dotyczy tylko rekordu
        # z adresu). Akcje oznaczone ``zapisuje_historie`` zapisują wersje
        # same, osobno dla każdego rekordu.
        if self._post_akcji_masowej(request) is not None:
            return nullcontext()
        return super().create_revision(request)

    def _post_akcji_masowej(self, request):
        """Akcja (krotka z ``get_actions``) uruchamiana POST-em listy
        rekordów albo ``None``, gdy ``request`` nie uruchamia akcji."""
        if request.method != "POST" or "action" not in request.POST:
            return None
        dopasowanie = getattr(request, "resolver_match", None)
        opts = self.model._meta
        lista = f"{opts.app_label}_{opts.model_name}_changelist"
        if dopasowanie is None or dopasowanie.url_name != lista:
            return None
        # Jak ``ModelAdmin.response_action``: przy kilku formularzach akcji
        # na stronie ``index`` wskazuje, który wysłano.
        try:
            nazwa = request.POST.getlist("action")[int(request.POST.get("index", 0))]
        except (ValueError, IndexError):
            return None  # niepoprawny POST — ``response_action`` go odrzuci
        return self.get_actions(request).get(nazwa)
