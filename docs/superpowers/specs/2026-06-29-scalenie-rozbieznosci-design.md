# Scalenie „rozbieżności punktacji/kwartyli" — spec

Data: 2026-06-29
Gałąź: `feat-scalenie-rozbieznosci-punktacji`
Worktree: `~/Programowanie/bpp-scalenie-rozbieznosci`

## Problem

W systemie istnieją dwie odrębne, pokrewne funkcje z menu „Operacje"
(`top_bar.html`):

1. **„rozbieżności punktacji IF"** — porównuje `impact_factor` źródła
   (`Punktacja_Zrodla`) z `impact_factor` pracy (`Wydawnictwo_Ciagle`).
2. **„rozbieżności punktacji MNiSW"** — to samo dla pola `punkty_kbn`
   (Punkty MNiSW).

Logika Pythona jest już zrefaktorowana do klas bazowych sparametryzowanych
`field_name` (w `src/rozbieznosci_if/views.py`); `rozbieznosci_pk` to cienkie
podklasy. Realna duplikacja: szablony HTML, osobne modele `Ignoruj*`/`*Log`,
osobne URL-e i dwa wpisy w menu.

Cel: **jedna** opcja menu „rozbieżności punktacji/kwartyli", obejmująca cztery
metryki, z domyślnym ukrywaniem rekordów, w których źródło ma `0` lub brak
wartości (żeby masowe „ustaw ze źródła" nie zerowało punktacji prac).

## Ustalenia (z brainstormingu)

- **Metryki (4):** Impact Factor, Punkty MNiSW, Kwartyl Scopus, Kwartyl WoS.
  Kwartyle to **nowy** zakres — dziś żadna z funkcji ich nie używa.
- **Kierunek porównania:** jak dziś — listujemy PRACE (`Wydawnictwo_Ciagle`),
  w wierszu wartość pracy obok wartości źródła dla tego samego roku. Bez
  nowego widoku „po stronie źródeł" — „dwie strony" = dwie porównywane
  wartości w jednym wierszu.
- **Ustawianie jednostronne:** praca ← źródło (bez kierunku odwrotnego),
  tryby per-rekord i masowy — bez zmian semantyki.
- **Filtr zer/NULL:** jeden przełącznik, **domyślnie ukrywa** rekordy, gdzie
  źródło ma `0` lub brak wartości. Checkbox „Pokaż też rekordy ze źródłem
  0/brak" odsłania je. Dla kwartyli `0` nie występuje → traktujemy jak NULL.
- **UI wyboru metryki:** zakładki u góry jednej strony.
- **Dane historyczne:** start od zera — istniejące ignory i logi z obu starych
  aplikacji przepadają (bez migracji danych).
- **Struktura kodu:** nowa aplikacja `rozbieznosci`; stare `rozbieznosci_if`
  i `rozbieznosci_pk` usunięte.

## Architektura

### Nowa aplikacja `src/rozbieznosci/`

**Rejestr metryk** (`metryki.py`) — jedno źródło prawdy, uporządkowana lista
dataclass (kolejność = kolejność zakładek):

| slug        | `field_name`       | label          | kwartyl? | przelicza dyscypliny? | precyzja |
|-------------|--------------------|----------------|----------|-----------------------|----------|
| `if`        | `impact_factor`    | Impact Factor  | nie      | nie                   | 3        |
| `mnisw`     | `punkty_kbn`       | Punkty MNiSW   | nie      | **tak**               | 2        |
| `kw_scopus` | `kwartyl_w_scopus` | Kwartyl Scopus | **tak**  | nie                   | int 1–4  |
| `kw_wos`    | `kwartyl_w_wos`    | Kwartyl WoS    | **tak**  | nie                   | int 1–4  |

```python
@dataclass(frozen=True)
class Metryka:
    slug: str                     # id w URL/zakładce
    field_name: str               # pole na Wydawnictwo_Ciagle i Punktacja_Zrodla
    label: str                    # etykieta zakładki/nagłówka
    is_quartile: bool             # kwartyl → filtr tylko NULL, brak „0"
    recalculates_disciplines: bool  # True dla punkty_kbn
    decimal_places: int           # formatowanie wyświetlania

METRYKI: list[Metryka]  # ordered; pierwsza = domyślna zakładka
METRYKI_BY_SLUG: dict[str, Metryka]
```

Wszystkie widoki rozwiązują metrykę z URL-a (`<slug:metryka>`) i parametryzują
queryset, filtr, set, log oraz bulk z rejestru. Dodanie kolejnej metryki w
przyszłości = jeden wpis w `METRYKI`.

### Modele (`models.py`)

```python
class IgnorowanaRozbieznosc(models.Model):
    metryka = CharField(max_length=16, choices=…)   # slug
    rekord = FK(Wydawnictwo_Ciagle, on_delete=CASCADE)
    class Meta:
        unique_together = [("metryka", "rekord")]

class RozbieznoscLog(models.Model):
    metryka = CharField(max_length=16, choices=…)
    rekord = FK(Wydawnictwo_Ciagle, on_delete=CASCADE)
    wartosc_przed = DecimalField(max_digits=10, decimal_places=3, null=True)
    wartosc_po    = DecimalField(max_digits=10, decimal_places=3, null=True)
    user = FK(AUTH_USER_MODEL, null=True, on_delete=SET_NULL)
    czas = DateTimeField(auto_now_add=True)
```

`Decimal(10,3)` mieści IF (3 miejsca), MNiSW (2) i kwartyl (`3.000`).
Formatowanie do wyświetlenia/eksportu robi warstwa widoku wg `decimal_places` /
`is_quartile`. Stare modele (`IgnorujRozbieznoscIf/Pk`, `RozbieznosciIfLog/PkLog`)
**usunięte**.

### URL-e (`urls.py`, `app_name = "rozbieznosci"`)

- `rozbieznosci/<slug:metryka>/` → `index`
- `rozbieznosci/<slug:metryka>/export` → `export` (XLSX)
- `rozbieznosci/<slug:metryka>/ustaw-wszystkie` → `ustaw_wszystkie`
- `rozbieznosci/<slug:metryka>/task-status` → `task_status` (HTMX polling)

Nieznany slug metryki → 404. W `django_bpp/urls.py`: jeden
`path("rozbieznosci/", include("rozbieznosci.urls"))` zamiast dwóch starych
include'ów. `INSTALLED_APPS`: dodać `rozbieznosci`, usunąć `rozbieznosci_if`
i `rozbieznosci_pk`.

## Logika porównania + filtr zer/NULL

Bazowy queryset jak obecnie (uogólniony z `get_base_queryset_for_field`):

```python
Wydawnictwo_Ciagle.objects
    .exclude(zrodlo=None)
    .filter(zrodlo__punktacja_zrodla__rok=F("rok"))            # ten sam rok
    .exclude(**{f"zrodlo__punktacja_zrodla__{field}": F(field)})  # różnica
    .exclude(pk__in=IgnorowanaRozbieznosc[metryka])            # pominięcie
    .annotate(**{f"punktacja_zrodla_{field}":
                 F(f"zrodlo__punktacja_zrodla__{field}")})
```

**Filtr zer/NULL (domyślnie aktywny):**

- metryki skalarne (IF, MNiSW):
  `.exclude(Q(<źródło>__isnull=True) | Q(<źródło>=0))`
- kwartyle: `.exclude(<źródło>__isnull=True)` (0 nie występuje)

Gdy GET `pokaz_puste_zrodla=1` (checkbox zaznaczony) → tę wykluczkę pomijamy.
Brak parametru = filtr aktywny (chowa). Skutek: domyślnie użytkownik **nie widzi
ani nie ustawia** pracy ze źródła 0/brak.

Uwaga (zachowanie strukturalne, bez zmian): jeśli źródło nie ma w ogóle wiersza
`Punktacja_Zrodla` za dany rok, praca nie pojawia się niezależnie od filtra
(INNER JOIN — nie ma wartości źródła do porównania ani do ustawienia). Filtr
zer/NULL działa w obrębie istniejących wierszy punktacji.

## „Ustaw ze źródła" — jednostronne (praca ← źródło)

- **Per-rekord** (`?_set=<pk>`): pobierz `wc.punktacja_zrodla()`, ustaw
  `setattr(wc, field, wartość_źródła)`, zapis, log do `RozbieznoscLog`
  (`metryka`, `wartosc_przed`, `wartosc_po`, `user`), usuń z
  `IgnorowanaRozbieznosc`. Dla `mnisw` → `wc.przelicz_punkty_dyscyplin()`.
- **Masowo** (`ustaw-wszystkie`): działa na **aktualnie odfiltrowanym**
  querysecie (ta sama metryka i te same filtry, w tym stan filtra zer) — więc
  domyślnie nigdy nie zeruje prac. GET → ekran potwierdzenia z liczbą rekordów;
  POST → przy `count >= OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE` (20) Celery,
  inaczej synchronicznie. Jedno uogólnione zadanie:
  `task_ustaw_ze_zrodla(pks, metryka_slug, user_id)` (progres co 5 elementów).

## UI / menu

- `top_bar.html`: zamiast dwóch wpisów (obecnie linie 200–203) jeden:
  „rozbieżności punktacji/kwartyli" →
  `{% url "rozbieznosci:index" metryka="if" %}` (domyślna zakładka = pierwsza
  z rejestru). Pozycja w tej samej sekcji „Operacje", pod tym samym warunkiem
  uprawnień (grupa „wprowadzanie danych" lub superuser).
- Szablony `rozbieznosci/templates/rozbieznosci/`:
  - `index.html` — pasek zakładek (pętla po `METRYKI`, aktywna = bieżąca;
    link przełączający przenosi filtry w query stringu), formularz filtrów
    (`rok_od` dom. 2022, `rok_do` dom. bieżący, `tytul`, checkbox
    „Pokaż też rekordy ze źródłem 0/brak"), tabela (Tytuł | Rok | Praca |
    Źródło | „Ustaw wg źródła"), przycisk „Ustaw wszystkie wg źródła", link do
    admina ignorowanych z filtrem po metryce.
  - `ustaw_wszystkie_confirm.html`, `task_status.html`, `_progress.html` —
    generyczne, metryka w kontekście.
  Jeden komplet szablonów zamiast dwóch near-copy.

## Obsługa błędów

- Nieznany slug metryki → 404.
- Brak `Punktacja_Zrodla` przy set → pominięcie rekordu (jak dziś).
- Celery: progres przez `update_state`, raport błędu wg obecnego wzorca
  (rollbar). Bez nowych ścieżek wyjątków; bez `except: pass`.

## Testy

Przeniesione z `rozbieznosci_if/tests.py`, **sparametryzowane po 4 metrykach**
(`pytest.mark.parametrize`), plus nowe:

- Filtr zer/NULL: domyślnie chowa rekordy ze źródłem `0` i `NULL`; toggle
  `pokaz_puste_zrodla=1` je pokazuje; **bulk „ustaw wszystkie" respektuje filtr**
  (przy domyślnym nie zeruje prac).
- Specyfika kwartyli: filtr tylko-NULL (brak „0"), per-rekord set kwartyla,
  brak wywołania `przelicz_punkty_dyscyplin`.
- `przelicz_punkty_dyscyplin` wołane **tylko** dla `mnisw` (per-rekord i task).
- Logi `RozbieznoscLog` z poprawną `metryka`, `wartosc_przed/po`, `user`.
- Render zakładek (4 zakładki, aktywna = bieżąca), 404 dla złego slug-a.
- Bulk: mały batch (sync) vs duży (≥20, Celery), `TaskStatusView` (HTMX).

Konwencje: pytest bez klas, `@pytest.mark.django_db`, `model_bakery.baker.make`;
fixtury grupy/`client_with_group` przeniesione z `rozbieznosci_if/conftest.py`.

## Migracje (jedyny ostrożny obszar)

- `rozbieznosci/migrations/0001_initial.py` — tworzy 2 nowe modele.
- Usunięcie starych modeli przez **nowe** migracje `DeleteModel` (zakaz edycji
  istniejących migracji). **Bez migracji danych** — start od zera.
- `make baseline-update` przy scalaniu (delta nowych migracji); commit
  `baseline.sql` + `baseline.meta.json`.
- Dokładna sekwencja (kolejność DeleteModel vs usunięcie aplikacji z
  `INSTALLED_APPS`/usunięcie katalogów) zostanie rozpisana w planie
  implementacji; przy realizacji **zatrzymać się i potwierdzić** przed
  wykonaniem migracji (reguła z CLAUDE.md).

## Poza zakresem (YAGNI)

- Widok „po stronie źródeł" (listujący źródła) — odrzucony, niepotrzebny.
- Pozostałe pola `ModelPunktowanyBaza` (Index Copernicus, SNIP, punktacja
  wewnętrzna) — celowo pominięte; rejestr metryk ułatwia dodanie później.
- Migracja danych historycznych (ignory/logi) — świadomie pominięta.
- Odwrotny kierunek ustawiania (źródło ← praca) — nie dotyczy.
- Przekierowania starych URL-i `rozbieznosci_if`/`rozbieznosci_pk` — pomijamy
  (narzędzie wewnętrzne, dostęp z menu).
