# Przyjazny komunikat przy braku definicji raportu

Data: 2026-05-31
Status: zatwierdzony, do implementacji
Branch/worktree: `feat/nowe-raporty-brak-definicji` / `~/Programowanie/bpp-raport-brak-definicji`

## Problem

Raporty w `nowe_raporty` to definicje `flexible_reports.Report` identyfikowane
przez `slug` (`raport-autorow`, `raport-jednostek`, `raport-uczelni`,
`raport-wydzialow`). Gdy definicja raportu nie istnieje w bazie (świeża
instalacja, nieskonfigurowany moduł redagowania), strona formularza raportu
zwraca **twardy błąd 404**:

```python
# src/nowe_raporty/views.py – BaseFormView.get_context_data
kwargs["report"] = get_object_or_404(Report, slug=self.report_slug)
```

Użytkownik (a zwłaszcza redaktor) nie dostaje żadnej informacji, **gdzie** ten
raport skonfigurować.

Stan obecny jest też niespójny między trzema ścieżkami:

| Ścieżka | Plik | Zachowanie przy braku `Report` |
|---|---|---|
| Strona formularza | `BaseFormView` | **404** (`get_object_or_404`) |
| Strona wyniku | `GenerujRaportBase` | grzeczny tekst „skontaktuj się z administratorem" (`report=None`) |
| Eksport docx/xlsx | `GenerujRaportBase.render_to_response` | **500** (`as_docx_response(None, …)`) |

## Zakres

**Wyłącznie strona formularza** (punkt wejścia użytkownika). Strona wyniku już
ma komunikat; eksport 500 jest świadomie poza zakresem (patrz „Znane, poza
zakresem").

## Rozwiązanie

### 1. `src/nowe_raporty/views.py` — `BaseFormView.get_context_data`

Zamiana `get_object_or_404` na łagodne pobranie (taki sam wzorzec jak
`GenerujRaportBase`):

```python
def get_context_data(self, **kwargs):
    kwargs["title"] = self.title
    try:
        kwargs["report"] = Report.objects.get(slug=self.report_slug)
    except Report.DoesNotExist:
        kwargs["report"] = None
    kwargs["report_slug"] = self.report_slug
    kwargs["report_title"] = self.title
    return super().get_context_data(**kwargs)
```

`report_slug` i `report_title` trafiają do kontekstu, żeby szablon mógł zbudować
link do admina z prefillowanym tytułem i slugiem.

### 2. `src/nowe_raporty/templates/nowe_raporty/formularz.html`

- Osłonić istniejący blok „otwórz do edycji" przez `{% if report %}` — bez tego
  `{% url ... report.pk %}` wybuchłoby na `report == None` i fix wprowadziłby
  nowy błąd.
- Gdy `not report` → zamiast `{% crispy form %}` wyrenderować nowy partial
  `nowe_raporty/_brak_definicji_raportu.html`.

### 3. `src/nowe_raporty/templates/nowe_raporty/_brak_definicji_raportu.html` (nowy)

Callout (Foundation, monochromatyczne `fi-*` ikony — to frontend publiczny):

- **Redaktor** (`request.user.is_superuser` lub grupa `raporty` — ten sam
  warunek co reszta szablonu): komunikat „Raport «{{ report_title }}» nie jest
  jeszcze skonfigurowany w systemie." + przycisk **„Skonfiguruj w module
  redagowania"** linkujący do:
  ```
  {% url 'admin:flexible_reports_report_add' %}?title={{ report_title|urlencode }}&slug={{ report_slug|urlencode }}
  ```
  Admin `ReportAdmin` ma `prepopulated_fields = {"slug": ("title",)}`, więc
  prefill tytułu + sluga daje redaktorowi gotowy formularz dodawania.
- **Pozostali**: ten sam komunikat + „Skontaktuj się z administratorem lub
  redaktorem systemu." (bez linku do panelu admina — nie zdradzamy ścieżki
  panelu osobom bez uprawnień).

## Obsługa błędów

Brak definicji raportu przestaje być błędem HTTP — staje się normalnym stanem
strony 200 z komunikatem. Żadna inna ścieżka błędów się nie zmienia.

## Testy

W `src/nowe_raporty/tests/test_nowe_raporty.py`, dla każdej z 4 form-view
(autor / jednostka / wydział / uczelnia):

1. **Brak `Report` → 200, nie 404.** Wejście zalogowanego usera z odpowiednią
   grupą na URL formularza bez utworzonego `Report` zwraca 200 i zawiera tekst
   komunikatu.
2. **Redaktor widzi link.** Superuser dostaje w treści URL
   `admin/.../flexible_reports/report/add` z prefillowanym slugiem.
3. **Zwykły user nie widzi linku.** Użytkownik z grupą `raporty` ale bez
   `is_staff`/uprawnień do admina dostaje tekst „skontaktuj się", bez linku do
   `report_add`.

Konwencje: pytest, `@pytest.mark.django_db`, `model_bakery.baker`, brak klas
testowych. Wykorzystać istniejące fixtures z `src/nowe_raporty/tests/conftest.py`
(uwaga: domyślnie tworzą `Report` — testy braku definicji muszą działać bez tego
fixture albo go usuwać).

## Reuse

Nowy partial `_brak_definicji_raportu.html` jest samowystarczalny. Gdyby zakres
się rozszerzył, da się go wpiąć też w `generuj.html` (zastępując obecny generyczny
tekst), ale to poza zakresem tej zmiany.

## Znane, poza zakresem (świadoma decyzja użytkownika)

- **Bug 500 w eksporcie** docx/xlsx: `GenerujRaportBase.render_to_response` przy
  `?_export=docx|xlsx` woła `as_*_response(context["report"], …)` gdy
  `report is None`. Latentny, do rozważenia przy temacie 2 (konfigurowalne
  raporty) lub osobno.
- **Strona wyniku** (`generuj.html`) — już ma komunikat, nie ruszamy.
