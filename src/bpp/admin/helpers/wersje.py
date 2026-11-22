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

from contextlib import nullcontext
from contextvars import ContextVar

from django.contrib.admin.models import LogEntry
from django.contrib.admin.utils import unquote
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db.models.signals import pre_save
from django.http import Http404
from reversion.models import Version
from reversion_compare.admin import CompareVersionAdmin

from bpp.wersjonowanie import (
    FOLLOW_REVERSION,
    POLA_KOSZA,
    POLA_POZA_WERSJA,
    zapewnij_wersje_poczatkowa,
)

from .wersje_modele import POLA_WRAZLIWE

#: Ustawiane na czas przywracania wersji w adminie — receiver
#: ``zachowaj_pola_wrazliwe`` przepisuje wtedy pola spoza wersji (hasła,
#: sekrety) z bazy, zamiast zostawić wartości domyślne.
_przywracanie_wersji = ContextVar("przywracanie_wersji", default=False)


def zachowaj_pola_wrazliwe(sender, instance, raw=False, **kwargs):
    """Przy przywracaniu wersji (zapis surowy) pola z ``POLA_WRAZLIWE``
    dostają bieżące wartości z bazy: inaczej przywrócenie danych
    użytkownika wyzerowałoby mu hasło."""
    if not raw or not _przywracanie_wersji.get() or instance.pk is None:
        return
    pola = POLA_WRAZLIWE.get(sender._meta.label_lower)
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
        wykluczone = set(POLA_POZA_POROWNANIEM) | set(
            POLA_POZA_WERSJA.get(self.model, POLA_KOSZA)
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
        # reversion-compare nie sprawdza uprawnień ani zakresu uczelni —
        # sam ``admin_view`` wpuszcza każdego członka personelu.
        obj = self.get_object(request, unquote(object_id))
        if obj is None:
            raise Http404("Brak takiego rekordu w zakresie Twojej uczelni.")
        if not self.has_view_or_change_permission(request, obj):
            raise PermissionDenied
        return super().compare_view(
            request,
            object_id,
            {**self._kontekst_porownania(request), **(extra_context or {})},
        )

    @staticmethod
    def _kontekst_porownania(request):
        """Opis obu wersji do nagłówka porównania (A — starsza, B — nowsza;
        reversion-compare zawsze układa je według numeru wersji)."""
        try:
            pks = sorted(int(request.GET[k]) for k in ("version_id1", "version_id2"))
        except (KeyError, ValueError):
            return {}  # reversion-compare sam odrzuci zły formularz (404)
        wersje = {
            v.pk: v
            for v in Version.objects.filter(pk__in=pks).select_related("revision__user")
        }
        if len(wersje) != 2:
            return {}
        return {
            "wersje_porownania": [
                (wersje[pks[0]], "A", "starsza", "bpp-wersja-a"),
                (wersje[pks[1]], "B", "nowsza", "bpp-wersja-b"),
            ]
        }

    def compare(self, obj, version1, version2):
        """Czytelne porównanie (``porownanie_wersji``) zamiast diffu
        reversion-compare. Zwraca (wiersze, „czy są pola nieśledzone”)."""
        from .porownanie_wersji import porownaj_wersje

        return (
            porownaj_wersje(self.model, obj, version1, version2, self.compare_exclude),
            False,
        )

    def po_przywroceniu_wersji(self, request, obj):
        """Hook po udanym przywróceniu wersji ``obj`` (już zapisanej
        formularzem). Domyślnie nic nie robi."""

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
            raise PermissionDenied(
                "Rekord jest w koszu — najpierw przywróć go z kosza, "
                "potem przywracaj wcześniejsze wersje."
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
        if request.method == "GET":
            extra_context = {
                "zmiany_powiazanych": self._zmiany_powiazanych(obj, version_id),
                **(extra_context or {}),
            }
        token = _przywracanie_wersji.set(True)
        try:
            response = super().revision_view(
                request, object_id, version_id, extra_context
            )
        finally:
            _przywracanie_wersji.reset(token)
        # Jak reversion: POST zakończony przekierowaniem = wersja przywrócona.
        # Błąd przywracania też kończy się przekierowaniem (na listę), więc
        # hook musi być bezpieczny do wywołania bez zmiany.
        if request.method == "POST" and response.status_code == 302:
            self.po_przywroceniu_wersji(
                request, self.model._default_manager.get(pk=obj.pk)
            )
        return response

    def _zmiany_powiazanych(self, obj, version_id):
        """Co przywrócenie wersji zrobi ze śledzonymi listami rekordu
        (autorzy, granty, pliki…): które pozycje zostaną usunięte (dopisane
        po tej wersji), a które przywrócone (usunięte po niej). Pokazywane
        w formularzu przywracania, ZANIM użytkownik zapisze."""
        wersja = Version.objects.select_related("revision").get(pk=version_id)
        w_rewizji = list(
            wersja.revision.version_set.exclude(pk=wersja.pk).select_related(
                "content_type"
            )
        )
        wynik = []
        for akcesor in FOLLOW_REVERSION.get(self.model, ()):
            menedzer = getattr(obj, akcesor)
            model = menedzer.model
            biezace = {str(o.pk): str(o) for o in menedzer.all()}
            w_wersji = {
                v.object_id: v.object_repr
                for v in w_rewizji
                if v.content_type.model_class() is model
                and _nalezy_do(v, obj, menedzer)
            }
            usuniete = [biezace[k] for k in biezace.keys() - w_wersji.keys()]
            przywrocone = [w_wersji[k] for k in w_wersji.keys() - biezace.keys()]
            if usuniete or przywrocone:
                wynik.append(
                    {
                        "nazwa": model._meta.verbose_name_plural,
                        "usuniete": sorted(usuniete),
                        "przywrocone": sorted(przywrocone),
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
            )
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
