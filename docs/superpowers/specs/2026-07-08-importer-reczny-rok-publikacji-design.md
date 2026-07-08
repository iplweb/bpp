# Ręczne wpisanie roku publikacji w importerze publikacji

**Data:** 2026-07-08
**Status:** zaakceptowany

## Problem

Importer publikacji przerywa pracę, gdy dane źródłowe nie zawierają roku
publikacji. Przykład: DOI `10.1007/0-306-46843-3_60` (rozdział książki,
Kluwer/Springer). CrossRef nie zwraca dla niego roku publikacji — wszystkie
realne pola dat są puste:

- `published`, `published-print`, `published-online` → `None`
- `issued` → `{'date-parts': [[None]]}` (jawnie puste)
- `created` → 2006, `deposited` → 2021 — to znaczniki **metadanych**, nie rok
  publikacji; nie wolno ich traktować jako roku wydania.

`session.normalized_data["year"]` jest pojedynczym źródłem prawdy o roku i
czytają go co najmniej: sugestia punktacji, punktacja źródła
(`Punktacja_Zrodla` wg roku), **auto-dopasowanie dyscyplin autorów**
(`Autor_Dyscyplina` wg roku), pole `miejsce_i_rok` oraz tworzenie rekordu
(`_create_publication` rzuca `ValidationError` bez roku).

Obecny komunikat radzi operatorowi „uzupełnij rok w źródle
(BibTeX/CrossRef/PBN)" — dla CrossRef to zewnętrzne API, którego operator nie
edytuje. Ślepy zaułek.

## Rozwiązanie

Rok staje się edytowalnym, **wymaganym** polem na kroku **Weryfikacja** —
zawsze widocznym, prefillowanym wartością pobraną ze źródła (o ile jest).
Operator może zarówno uzupełnić brakujący rok, jak i **poprawić** błędny.

Krok Weryfikacja jest najwcześniejszym edytowalnym krokiem po pobraniu danych,
więc ustawienie roku tutaj sprawia, że działają wszystkie kroki zależne od roku
(źródło, autorzy/dyscypliny, punktacja, tworzenie rekordu).

### Zmiany

1. **`src/importer_publikacji/forms.py` — `VerifyForm`**
   Dodać pole:
   ```python
   rok = forms.IntegerField(
       label="Rok publikacji",
       required=True,
       min_value=1900,
       max_value=2100,
   )
   ```

2. **`src/importer_publikacji/views/steps.py` — `_verify_context`**
   Prefill: `initial["rok"] = session.normalized_data.get("year")`.

3. **`src/importer_publikacji/views/wizard.py` — `VerifyView.post`**
   Po `form.is_valid()` zapisać rok do jedynego źródła prawdy przed
   `session.save()`:
   ```python
   session.normalized_data["year"] = form.cleaned_data["rok"]
   ```

4. **`src/importer_publikacji/templates/.../partials/step_verify.html`**
   Dodać input `rok` do siatki formularza (obok języka/charakteru). Usunąć
   nadmiarowy wiersz „Rok" (tylko-do-odczytu) z tabeli danych źródłowych —
   edytowalne pole go zastępuje.

### Zachowane jako zabezpieczenia (nie usuwane)

- Gałąź `RodzajBraku.BRAK_ROKU` w `_oblicz_sugestie`.
- `ValidationError("Brak roku publikacji…")` w `_create_publication`.

Sesja może nadal mieć pusty rok (starsze sesje, inne ścieżki), więc guardy
zostają jako backstop; w nowym przepływie stają się nieosiągalne.

## Testy (TDD)

- **Repro:** sesja bez `year` w `normalized_data` → `VerifyForm` nieważny bez
  `rok`; POST z `rok` ustawia `normalized_data["year"]` i przechodzi do kroku
  źródła.
- **Prefill:** sesja z rokiem → initial formularza/kontekst zawiera rok.
- **Korekta:** POST z innym `rok` nadpisuje `normalized_data["year"]`.

## Poza zakresem (YAGNI)

- Brak nowego statusu/kroku sesji.
- Brak dynamicznego „bieżącego roku" jako `max_value`.
- Brak migracji/backfillu istniejących sesji.
