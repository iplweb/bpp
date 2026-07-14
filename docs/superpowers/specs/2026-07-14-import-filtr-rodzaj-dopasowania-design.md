# Filtr „Rodzaj dopasowania" na `/rezultaty/` importu pracowników

Data: 2026-07-14
Branch: `feat/import-filtr-rodzaj-dopasowania`
Moduł: `src/import_pracownikow/`

## Problem

Ostrzeżenie finalizacji importu osób (na stronie przeglądu, Krok 2) mówi:

> „Wiersze bez dopasowania zostaną pominięte przy zapisie: 4. Te osoby nie
> trafią do bazy. Wróć do tabeli i dla każdej wybierz „Utwórz nowego autora"
> albo „Dopasuj do istniejącego", jeśli mają zostać zaimportowane."

Ale na `/rezultaty/` **nie da się odnaleźć** tych wierszy. Pasek filtrów
filtruje wyłącznie po **stanie pól** (jednostka / e-mail / tytuł / … →
wszystkie / zmienione / zgodne / brak) oraz po tekście (nazwisko / jednostka).
Nie ma filtra po **rodzaju dopasowania autora** (`confidence`), mimo że kolumna
„Pewność" ten rodzaj pokazuje. Operator nie ma jak wyizolować wierszy „do
pominięcia" spośród dziesiątek/setek poprawnie dopasowanych.

## Kontekst techniczny (stan obecny)

- Widok: `ImportPracownikowResultsView` (`views.py`), template
  `importpracownikowrow_list.html`. Tabela + pasek filtrów renderują się gdy
  `parent_object.finished_successfully` (analiza dry-run zakończona OK — także
  w edytowalnym podglądzie, gdzie pada ostrzeżenie).
- Filtrowanie jest **w 100% po stronie JS** (inline `<script>` w
  `importpracownikowrow_list.html`). Nie ma round-tripu do serwera: JS chowa
  `<tbody data-rekord>` na podstawie `data-diff-*` na pierwszym `<tr>` karty
  oraz tekstu z elementów `[data-szukaj]`. Po każdej akcji HTMX
  (`htmx:afterSettle`) filtr jest ponawiany, a `data-diff-*` są świeże, bo
  HTMX swapuje `innerHTML` `<tbody>` (partial `_wiersz_preview_kom.html`).
- Rejestr pól: `roznice.py::POLA_ROZNIC`. Widok dzieli je na `pola_glowne` /
  `pola_dodatkowe` i podaje do template (radia z `_filtr_pole.html`).
- Statusy `confidence` (`pewnosc.py`): `twardy`, `zgadywanie`, `wielu`,
  `brak`, `reczny`, `dedup`. Mapowanie na plakietkę: `STATUS_DISPLAY` /
  `row.confidence_badge`. Etykiety w `CONFIDENCE_CHOICES`.
- Kolumna „Pewność" w `_wiersz_preview_kom.html` (pierwszy `<tr>`) renderuje
  `row.confidence_badge`. Pierwszy `<tr>` ma już pętlę
  `data-diff-{klucz}="{stan}"` z `row.stany_pol`.

### Kluczowy niuans: „do pominięcia" ≠ tylko `brak`

`ImportPracownikow.liczba_wierszy_do_pominiecia()` liczy wiersze z
`autor IS NULL AND utworz_nowego=False` (brak decyzji operatora). `autor` jest
`NULL` przy **dwóch** statusach:

- `brak` — zero kandydatów,
- `wielu` — kilku kandydatów, auto-match wstrzymany (operator musi wybrać).

(`twardy` / `zgadywanie` / `reczny` / `dedup` mają autora ustawionego.)

Dlatego zbiór „do pominięcia" = `{brak, wielu}` **bez** `utworz_nowego`.
Filtr sztywno po `confidence=brak` **przeoczyłby** wiersze `wielu`, które też
zostaną pominięte, i licznik z ostrzeżenia (4) nie zgodziłby się z tym, co
widać. Ponadto wiersz `brak` z ręcznie ustawionym „Utwórz nowego" **nie** jest
już pomijany — więc filtr po samym statusie jest nieprecyzyjny.

Wniosek: potrzebny osobny, **wyliczany na żywo** predykat „do pominięcia"
(`autor IS NULL AND NOT utworz_nowego`), niezależny od czystego statusu.

## Rozwiązanie

Wyłącznie **template + widok + JS + testy**. Bez migracji (`confidence`,
`utworz_nowego` już istnieją).

### 1. Atrybuty na wierszu (`_wiersz_preview_kom.html`)

Na pierwszym `<tr>` karty (obok istniejącej pętli `data-diff-*`) dokładamy:

- `data-confidence="{{ row.confidence|default:'' }}"` — do filtra po statusie.
- `data-do-pominiecia="1"` **tylko** gdy wiersz zostanie pominięty. Predykat:
  `row.autor_id is None and not row.utworz_nowego`. Wyliczany przez nową
  właściwość modelu `row.do_pominiecia` (jedno źródło prawdy z
  `liczba_wierszy_do_pominiecia`, patrz niżej), renderowany warunkowo, żeby
  atrybut po prostu nie istniał, gdy wiersz ma decyzję.

Oba atrybuty żyją na **swapowanej** treści (`_wiersz_preview_kom.html`), więc
po akcji HTMX (np. „Utwórz nowego" / „Dopasuj autora") przeliczają się i filtr
po `htmx:afterSettle` pokazuje aktualny obraz (naprawiony wiersz znika z „do
pominięcia").

### 2. Model: właściwość `ImportPracownikowRow.do_pominiecia`

```python
@property
def do_pominiecia(self):
    """Czy wiersz zostanie PO CICHU pominięty przy zapisie osób — brak
    dopasowanego autora i bez „Utwórz nowego". Jedno źródło prawdy z
    ``ImportPracownikow.liczba_wierszy_do_pominiecia`` (ten sam predykat:
    ``autor IS NULL AND utworz_nowego=False``); używane przez atrybut
    filtra ``data-do-pominiecia`` w podglądzie."""
    return self.autor_id is None and not self.utworz_nowego
```

`liczba_wierszy_do_pominiecia` zostaje na wersji queryset (`.filter(...).count()`
— jeden SQL), ale komentarz podkreśla, że predykat jest identyczny z
`row.do_pominiecia` (żeby nie zdryfowały). Nie refaktoryzujemy zliczania do
Pythona (N+1).

### 3. Kontrolka filtra (`importpracownikowrow_list.html`)

`<select id="filtr-rodzaj" name="filtr-rodzaj">` jako **pierwsza, wyróżniona**
kontrolka w `<form id="filtr-roznic">` (przed polami stanu — mapuje się na
najważniejszą kolumnę „Pewność"). `<select>` zamiast radiów, bo 8 opcji z
długimi etykietami rozjechałoby pasek poziomo.

Opcje (label + value):

- `wszystkie` → „wszystkie" (domyślnie zaznaczone, gdy brak/niepoprawny
  query-param)
- `do-pominiecia` → „⚠ do pominięcia (bez decyzji)" — celuje w zbiór z
  ostrzeżenia
- separator: jedna `<option disabled>──────</option>` (prościej niż
  `<optgroup>`, który przy jednej grupie renderuje się dziwnie)
- `twardy` → „twardy match"
- `zgadywanie` → „zgadywanie"
- `wielu` → „wielu kandydatów"
- `brak` → „brak dopasowania"
- `reczny` → „ręczny (wybór użytkownika)"
- `dedup` → „rekord główny (deduplikacja)"

Etykiety statusów bierzemy z jednego źródła — nowa lista w kontekście widoku
zbudowana z `CONFIDENCE_CHOICES` (żeby template nie hardkodował). Opcja
`selected` ustawiana serwerowo z `wybrany_rodzaj` (patrz pkt 5), żeby
pre-selekcja działała także przed wykonaniem JS.

**Decyzja o etykietach**: świadomie używamy `CONFIDENCE_CHOICES` (opisowe:
„ręczny (wybór użytkownika)", „rekord główny (deduplikacja)"), a NIE etykiet
plakietek z `STATUS_DISPLAY` (terse: „wybór użytkownika", „rekord główny").
Filtr-dropdown zyskuje na jednoznaczności; drobna kosmetyczna rozbieżność z
kolumną „Pewność" jest akceptowalna.

**Obsługa `confidence=None` (stare wiersze)**: renderujemy
`data-confidence=""`, które NIE zrówna się z żadnym statusem — taki wiersz jest
osiągalny tylko przez „wszystkie" oraz (jeśli bez decyzji) „do pominięcia".
Świadomie NIE koalescujemy `None → brak` w atrybucie: plakietka pokazuje wtedy
„—" (nie „brak dopasowania"), więc koalescencja kłamałaby względem kolumny.
Niska szkodliwość — nowa analiza zawsze ustawia `confidence`.

**Semantyka po integracji**: pasek renderuje się też po pełnym commicie
(`finished_successfully` zostaje `True`, widok audytu). Predykat „do pominięcia"
przeżywa commit (integracja tworzy autorów tylko dla `utworz_nowego=True`), więc
filtr dalej działa — tyle że po integracji znaczy „ZOSTAŁY pominięte" (historia),
a nie „zostaną". Kopia opcji („do pominięcia") jest akceptowalna w obu fazach;
nie komplikujemy jej wariantami zależnymi od stanu (YAGNI).

### 4. JS — rozszerzenie `filtruj()`

Istniejący inline `<script>` dostaje odczyt `<select>` i AND-uje go z filtrami
pól + tekstem. Minimalny dopisek (bez ruszania generycznej maszynerii radiów):

```js
function wyborRodzaj() {
    var el = document.getElementById('filtr-rodzaj');
    return el ? el.value : 'wszystkie';
}
function okRodzaj(tbody) {
    var w = wyborRodzaj();
    if (w === 'wszystkie') return true;
    var tr = tbody.querySelector(':scope > tr[data-confidence]');
    if (!tr) return false;
    if (w === 'do-pominiecia')
        return tr.getAttribute('data-do-pominiecia') === '1';
    return tr.getAttribute('data-confidence') === w;
}
```

W `filtruj()`: `var pokaz = okStany && okTekst && okRodzaj(tbody);`.
`<select>` jest w tym samym `<form>`, więc istniejące
`form.addEventListener('change'/'input', filtruj)` już go obsłużą. `filtruj()`
odpalany na starcie (respektuje serwerową pre-selekcję) i po
`htmx:afterSettle`.

### 5. Widok — walidacja i pre-selekcja `?rodzaj=`

W `ImportPracownikowResultsView.get_context_data`:

```python
DOZWOLONE_RODZAJE = {"do-pominiecia"} | {k for k, _ in CONFIDENCE_CHOICES}
rodzaj = self.request.GET.get("rodzaj", "")
ctx["wybrany_rodzaj"] = rodzaj if rodzaj in DOZWOLONE_RODZAJE else ""
ctx["rodzaje_confidence"] = list(CONFIDENCE_CHOICES)  # (value, label) do <select>
```

Śmieciowy / nieznany `?rodzaj=` → `wybrany_rodzaj = ""` (traktowane jak
„wszystkie", brak `selected` na opcjach innych niż „wszystkie"). Template
oznacza `selected` na opcji, której `value == wybrany_rodzaj` (dla `""` →
„wszystkie").

### 6. Deep-link z ostrzeżenia (`_ostrzezenie_brak_dopasowania.html`)

Goły tekst „Wróć do tabeli…" dostaje przycisk/link:

```django
<a href="{% url "import_pracownikow:importpracownikow-results" parent_object.pk %}?rodzaj=do-pominiecia"
   class="button primary">
    <span class="fi-magnifying-glass"></span> Pokaż wiersze do pominięcia
</a>
```

Partial jest include'owany z kontekstem huba — wymaga `parent_object` (jest
dostępny w `przeglad.html`). Ścieżka operatora: ostrzeżenie → jeden klik →
`/rezultaty/?rodzaj=do-pominiecia` → tabela odfiltrowana dokładnie do wierszy z
ostrzeżenia; licznik „Pokazano N z M" pokazuje N = liczbie z ostrzeżenia.

## Testy (TDD, pytest + `model_bakery`)

Plik: `src/import_pracownikow/tests/test_filtr_rodzaj.py` (nowy).

**Warunki wstępne scaffoldingu (zweryfikowane w review — WPROST w testach):**

- Testy tworzą `ImportPracownikowRow` **bezpośrednio** przez `objects.create`
  (NIE przez pipeline `analyze`) — dzięki temu nie dotyczy ich pułapka
  `icontains`-ambient (dopasuj_jednostke) pod xdist. `create` wymaga jawnego
  `zmiany_potrzebne=...` (BooleanField bez defaultu — wzorzec
  `test_views_preview_render.py`).
- Testy **widoku wyników** muszą ustawić `finished_successfully=True` na
  rodzicu (`ImportPracownikow.objects.filter(pk=...).update(...)`), inaczej
  pasek/tabela się nie wyrenderują (bramka
  `{% if parent_object.finished_successfully %}`).
- Test deep-linku (#9) renderuje **stronę przeglądu**: wymaga
  `stan=STAN_STRUKTURA_ZINTEGROWANA` ORAZ braku nierozstrzygniętych słowników
  (ostrzeżenie żyje w gałęzi `{% else %}` po
  `{% if slowniki_wymagaja_rozstrzygniecia %}`). Wzorzec:
  `test_przeglad.py::test_hub_ostrzega_o_wierszach_do_pominiecia`.
- NIE fabrykujemy kombinacji `confidence=wielu` + `utworz_nowego=True` — jest
  nieosiągalna przez UI (guard w `PrzelaczUtworzNowegoView` zwraca 400 dla
  nie-`brak`). Dla „ma decyzję" używamy `confidence=brak` + `utworz_nowego=True`.

1. **`test_wiersz_ma_data_confidence`** — render karty ma
   `data-confidence="brak"` dla wiersza `confidence=brak` (i analogicznie dla
   innego statusu).
2. **`test_data_do_pominiecia_gdy_brak_decyzji`** — wiersz `autor=None`,
   `utworz_nowego=False` → `data-do-pominiecia="1"` w HTML.
3. **`test_brak_data_do_pominiecia_gdy_utworz_nowego`** — ten sam wiersz z
   `utworz_nowego=True` → **brak** `data-do-pominiecia` w HTML.
4. **`test_brak_data_do_pominiecia_gdy_autor_dopasowany`** — wiersz z autorem →
   brak atrybutu.
5. **`test_model_do_pominiecia_property`** — `row.do_pominiecia` zwraca True/False
   zgodnie z predykatem (i pokrywa się z `liczba_wierszy_do_pominiecia`).
6. **`test_select_rodzaj_ma_wszystkie_opcje`** — `<select id="filtr-rodzaj">`
   zawiera opcje: `do-pominiecia`, `twardy`, `zgadywanie`, `wielu`, `brak`,
   `reczny`, `dedup`.
7. **`test_query_param_preselekcja`** — GET `?rodzaj=do-pominiecia` → opcja
   `do-pominiecia` ma `selected` (asercja luźna/regex — NIE dokładny string
   `<option value="do-pominiecia" selected>`, bo kolejność atrybutów zależy od
   zapisu template).
8. **`test_query_param_smieciowy_ignorowany`** — GET `?rodzaj=XXX` → żadna
   opcja poza „wszystkie" nie ma `selected` (fallback bezpieczny).
9. **`test_ostrzezenie_ma_link_do_filtra`** — na stronie przeglądu (Krok 2 z
   wierszami do pominięcia) ostrzeżenie zawiera link
   `...?rodzaj=do-pominiecia`.

Filtrowanie samo (chowanie wierszy) jest w JS — nie testujemy Playwrightem
(YAGNI); testujemy kontrakt HTML/atrybutów, na którym JS operuje.

## Poza zakresem (YAGNI)

- Brak filtrowania server-side / paginacji (tabela jest w całości w DOM, filtr
  JS wystarcza — spójne z istniejącym paskiem).
- Brak zapisu wybranego filtra w sesji / cookie.
- Brak testu Playwright samego chowania wierszy.

## Pliki

- `src/import_pracownikow/models.py` — `+ do_pominiecia` property.
- `src/import_pracownikow/views.py` — kontekst `wybrany_rodzaj`,
  `rodzaje_confidence`, walidacja `?rodzaj=`.
- `.../templates/import_pracownikow/importpracownikowrow_list.html` — `<select>`
  + rozszerzenie JS.
- `.../partials/_wiersz_preview_kom.html` — `data-confidence`,
  `data-do-pominiecia`.
- `.../partials/_ostrzezenie_brak_dopasowania.html` — link deep-link.
- `src/import_pracownikow/tests/test_filtr_rodzaj.py` — testy.
- `src/bpp/newsfragments/<slug>.feature.rst` — newsfragment.
